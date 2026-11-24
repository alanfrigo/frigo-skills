"""Read-only sampled QA for the evaluated animation of a Blender armature."""

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix


def nonnegative(text):
    value = float(text)
    if not math.isfinite(value) or value < 0:
        raise argparse.ArgumentTypeError("expected a finite nonnegative number")
    return value


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rig", required=True, help="Armature object name in the active scene")
    parser.add_argument("--root", help="Pose bone for root motion; defaults to the armature object")
    parser.add_argument("--frames", nargs=2, type=int, metavar=("START", "END"),
                        help="Inclusive sample range; defaults to the scene playback bounds")
    parser.add_argument("--samples-per-frame", type=int, default=1,
                        help="Use >1 to include uniformly spaced subframes")
    parser.add_argument("--meters-per-unit", type=nonnegative,
                        help="Override scene unit scale (unitless scenes default to 1 m per BU)")
    parser.add_argument("--contact", nargs=3, action="append", default=[],
                        metavar=("BONE", "START", "END"), help="Repeat for each inclusive plant window")
    parser.add_argument("--contact-point", choices=("head", "tail"), default="head")
    parser.add_argument("--max-contact-drift", type=nonnegative, default=0.02, metavar="METERS",
                        help="Maximum 3D displacement from the first sample of each window")
    parser.add_argument("--max-root-step", type=nonnegative, metavar="METERS",
                        help="Maximum root translation between consecutive samples")
    parser.add_argument("--max-root-distance", type=nonnegative, metavar="METERS",
                        help="Maximum net translation from the first to last root position")
    parser.add_argument("--loop", action="store_true", help="Check pose closure at the range endpoints")
    parser.add_argument("--loop-bone", action="append", default=[], metavar="BONE",
                        help="Repeat to replace the default selection of all deform bones except the root")
    parser.add_argument("--allow-root-cycle", action="store_true",
                        help="Compare endpoint poses relative to root translation and rotation")
    parser.add_argument("--max-loop-position", type=nonnegative, default=0.01, metavar="METERS")
    parser.add_argument("--max-loop-angle", type=nonnegative, default=2.0, metavar="DEGREES")
    parser.add_argument("--max-loop-scale", type=nonnegative, default=0.01,
                        help="Maximum absolute scale change on any axis at the seam")
    parser.add_argument("--json", type=Path, metavar="FILE", help="Also write JSON to this path")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    if args.samples_per_frame < 1:
        parser.error("--samples-per-frame must be positive")
    if args.meters_per_unit == 0:
        parser.error("--meters-per-unit must be positive")
    if not args.loop and (args.loop_bone or args.allow_root_cycle):
        parser.error("--loop-bone and --allow-root-cycle require --loop")
    return parser, args


def rotation_delta(a, b):
    angle = a.rotation_difference(b).angle
    return math.degrees(min(angle, abs(math.tau - angle)))


def transform_delta(a, b, meters):
    pa, qa, sa = a.decompose()
    pb, qb, sb = b.decompose()
    return {
        "position_m": (pb - pa).length * meters,
        "rotation_deg": rotation_delta(qa, qb),
        "max_axis_scale_delta": max(abs(x - y) for x, y in zip(sa, sb)),
    }


def collect(parser, args):
    scene = bpy.context.scene
    rig = scene.objects.get(args.rig)
    if rig is None or rig.type != "ARMATURE" or rig.name not in bpy.context.view_layer.objects:
        parser.error(f"active view layer has no armature named {args.rig!r}")
    bones = rig.pose.bones
    if args.root and args.root not in bones:
        parser.error(f"missing root bone {args.root!r}")
    first, last = args.frames if args.frames else (scene.frame_start, scene.frame_end)
    if first >= last:
        parser.error("frame range must contain at least two frames")
    contacts = []
    for bone, start, end in args.contact:
        if bone not in bones:
            parser.error(f"missing contact marker bone {bone!r}")
        try:
            start, end = int(start), int(end)
        except ValueError:
            parser.error("contact window bounds must be integer frames")
        if not first <= start < end <= last:
            parser.error(f"contact window {bone!r} {start}:{end} must span at least two frames inside {first}:{last}")
        contacts.append({"bone": bone, "frames": [start, end], "samples": 0,
                         "max_drift_m": 0.0, "max_drift_frame": start, "max_xy_drift_m": 0.0,
                         "max_vertical_drift_m": 0.0})
    loop_bones = []
    if args.loop:
        loop_bones = list(dict.fromkeys(args.loop_bone)) if args.loop_bone else [
            bone.name for bone in rig.data.bones if bone.use_deform and bone.name != args.root
        ]
        if not loop_bones:
            parser.error("no loop bones: choose pose bones explicitly with --loop-bone")
        for bone in loop_bones:
            if bone not in bones or bone == args.root:
                parser.error(f"loop bone {bone!r} must exist and must not be the selected root")
    meters = args.meters_per_unit
    if meters is None:
        meters = scene.unit_settings.scale_length if scene.unit_settings.system != "NONE" else 1.0
    fps = scene.render.fps / scene.render.fps_base
    return scene, rig, first, last, contacts, loop_bones, meters, fps


def sample(args, scene, rig, first, last, contacts, loop_bones, meters, fps):
    intervals = (last - first) * args.samples_per_frame
    root_first = root_last = previous_position = None
    max_step = path_length = 0.0
    max_step_frame = first
    endpoints = []
    old_frame, old_subframe = scene.frame_current, scene.frame_subframe
    try:
        for index in range(intervals + 1):
            whole, fraction = divmod(index, args.samples_per_frame)
            subframe = fraction / args.samples_per_frame
            frame = first + whole + subframe
            scene.frame_set(first + whole, subframe=subframe)
            evaluated = rig.evaluated_get(bpy.context.evaluated_depsgraph_get())
            world = evaluated.matrix_world
            pose = evaluated.pose.bones
            root = world @ pose[args.root].matrix if args.root else world
            if not all(math.isfinite(value) for row in root for value in row):
                raise ValueError(f"nonfinite evaluated root matrix at frame {frame:g}")
            position = root.translation
            if previous_position is not None:
                step = (position - previous_position).length * meters
                path_length += step
                if step > max_step:
                    max_step, max_step_frame = step, frame
            previous_position = position
            if index == 0:
                root_first = root.copy()
            if index == intervals:
                root_last = root.copy()
            if args.loop and index in (0, intervals):
                if args.allow_root_cycle:
                    offset, orient, _ = root.decompose()
                    world = Matrix.LocRotScale(offset, orient, None).inverted() @ world
                endpoints.append({bone: world @ pose[bone].matrix for bone in loop_bones})
            for contact in contacts:
                start, end = contact["frames"]
                if not start <= frame <= end:
                    continue
                marker = evaluated.matrix_world @ getattr(pose[contact["bone"]], args.contact_point)
                if not all(math.isfinite(value) for value in marker):
                    raise ValueError(f"nonfinite contact marker {contact['bone']!r} at frame {frame:g}")
                if not contact["samples"]:
                    contact["anchor_m"] = list(marker * meters)
                    contact["anchor"] = marker
                contact["samples"] += 1
                delta = marker - contact["anchor"]
                drift = delta.length * meters
                if drift > contact["max_drift_m"]:
                    contact["max_drift_m"], contact["max_drift_frame"] = drift, frame
                contact["max_xy_drift_m"] = max(contact["max_xy_drift_m"], math.hypot(delta.x, delta.y) * meters)
                contact["max_vertical_drift_m"] = max(contact["max_vertical_drift_m"], abs(delta.z) * meters)
    finally:
        scene.frame_set(old_frame, subframe=old_subframe)

    root_report = transform_delta(root_first, root_last, meters)
    root_report.update({
        "source": args.root or "armature_object",
        "start_m": list(root_first.translation * meters),
        "end_m": list(root_last.translation * meters),
        "delta_world_m": list((root_last.translation - root_first.translation) * meters),
        "path_length_m": path_length,
        "max_step_m": max_step,
        "max_step_frame": max_step_frame,
        "mean_net_speed_m_per_s": root_report["position_m"] * fps / (last - first),
    })
    loop_report = None
    if args.loop:
        a, b = endpoints
        loop_report = {"space": "root_relative" if args.allow_root_cycle else "world",
                       "bones": {name: transform_delta(a[name], b[name], meters) for name in loop_bones}}
    for contact in contacts:
        del contact["anchor"]
    return root_report, loop_report


def main():
    parser, args = parse_args()
    scene, rig, first, last, contacts, loop_bones, meters, fps = collect(parser, args)
    root, loop = sample(args, scene, rig, first, last, contacts, loop_bones, meters, fps)
    failures = []
    limits = {"contact_drift_m": args.max_contact_drift, "root_step_m": args.max_root_step,
              "root_distance_m": args.max_root_distance,
              "loop_position_m": args.max_loop_position if args.loop else None,
              "loop_rotation_deg": args.max_loop_angle if args.loop else None,
              "loop_scale_delta": args.max_loop_scale if args.loop else None}

    def gate(check, subject, value, limit):
        if not math.isfinite(value) or (limit is not None and value > limit):
            failures.append({"check": check, "subject": subject, "value": value, "limit": limit})

    for contact in contacts:
        start, end = contact["frames"]
        gate("contact_drift_m", f"{contact['bone']}:{start}-{end}", contact["max_drift_m"], args.max_contact_drift)
    gate("root_step_m", root["source"], root["max_step_m"], args.max_root_step)
    gate("root_distance_m", root["source"], root["position_m"], args.max_root_distance)
    if loop:
        for name, metrics in loop["bones"].items():
            gate("loop_position_m", name, metrics["position_m"], args.max_loop_position)
            gate("loop_rotation_deg", name, metrics["rotation_deg"], args.max_loop_angle)
            gate("loop_scale_delta", name, metrics["max_axis_scale_delta"], args.max_loop_scale)
        if not args.allow_root_cycle:
            gate("loop_position_m", root["source"], root["position_m"], args.max_loop_position)
            gate("loop_rotation_deg", root["source"], root["rotation_deg"], args.max_loop_angle)
        gate("loop_scale_delta", root["source"], root["max_axis_scale_delta"], args.max_loop_scale)

    report = {
        "passed": not failures, "rig": rig.name, "frames": [first, last], "fps": fps,
        "samples_per_frame": args.samples_per_frame, "meters_per_unit": meters,
        "contact_point": args.contact_point, "contacts": contacts, "root": root, "loop": loop,
        "limits": limits, "failures": failures,
    }
    text = json.dumps(report, indent=2, allow_nan=False)
    if args.json:
        args.json.write_text(text + "\n", encoding="utf-8")
    print(text, flush=True)
    if failures:
        raise RuntimeError(f"animation QA failed {len(failures)} threshold check(s)")


if __name__ == "__main__":
    main()
