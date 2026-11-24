"""Generate an original skinned robot, a one-second loop, and preview frames in Blender."""

import argparse
import math
import sys
from pathlib import Path

import bpy
from bpy_extras.anim_utils import action_get_channelbag_for_slot
from mathutils import Euler, Matrix, Vector

FIRST, LAST, FPS = 1, 25, 24
PREVIEW_FRAMES = (1, 7, 11, 15, 19, 25)
THIGH_LENGTH = 0.54
SIDES = (("L", 1), ("R", -1))


def knee_position(hip, ankle):
    """Equal-length two-link solution, bending toward the robot's forward (-Y)."""
    reach = ankle - hip
    direction = reach.normalized()
    forward = Vector((0, -1, 0))
    pole = (forward - direction * forward.dot(direction)).normalized()
    offset = math.sqrt(THIGH_LENGTH ** 2 - reach.length_squared / 4)
    return (hip + ankle) / 2 + pole * offset


def make_rig():
    data = bpy.data.armatures.new("Field Tester Skeleton")
    rig = bpy.data.objects.new("SampleRig", data)
    bpy.context.collection.objects.link(rig)
    bpy.context.view_layer.objects.active = rig
    rig.select_set(True)
    rig.show_in_front = True
    data.display_type = "STICK"
    bpy.ops.object.mode_set(mode="EDIT")

    def bone(name, head, tail, parent=None, deform=True):
        entry = data.edit_bones.new(name)
        entry.head, entry.tail = head, tail
        if parent:
            entry.parent = data.edit_bones[parent]
        entry.use_deform = deform

    bone("Root", (0, 0, 0), (0, 0, 0.27), deform=False)
    bone("Pelvis", (0, 0, 1.00), (0, 0, 1.16), "Root")
    bone("Torso", (0, 0, 1.16), (0, 0, 1.65), "Pelvis")
    bone("Head", (0, 0, 1.65), (0, 0, 1.96), "Torso")
    for side, sign in SIDES:
        x = sign * 0.24
        hip, ankle = Vector((x, 0, 1.00)), Vector((x, 0, 0.15))
        knee = knee_position(hip, ankle)
        toe = (x, -0.24, 0.015)
        bone(f"Thigh.{side}", hip, knee, "Pelvis")
        bone(f"Shin.{side}", knee, ankle, f"Thigh.{side}")
        bone(f"Foot.{side}", ankle, (x, -0.20, 0.08), f"Shin.{side}")
        bone(f"Toe.{side}", toe, (x, -0.33, 0.015), f"Foot.{side}", deform=False)
        shoulder = (sign * 0.35, 0, 1.50)
        elbow = (sign * 0.48, -0.015, 1.22)
        wrist = (sign * 0.54, -0.10, 0.99)
        bone(f"UpperArm.{side}", shoulder, elbow, "Torso")
        bone(f"Forearm.{side}", elbow, wrist, f"UpperArm.{side}")

    bpy.ops.object.mode_set(mode="OBJECT")
    return rig


def material(name, color, *, metallic=0.0, roughness=0.43, emission=0.0):
    mat = bpy.data.materials.new(name)
    rgba = (*color, 1)
    mat.diffuse_color = rgba
    mat.use_nodes = True
    shader = mat.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = rgba
    shader.inputs["Metallic"].default_value = metallic
    shader.inputs["Roughness"].default_value = roughness
    if emission:
        shader.inputs["Emission Color"].default_value = rgba
        shader.inputs["Emission Strength"].default_value = emission
    return mat


def finish(name, mat):
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(mat)
    obj.color = mat.diffuse_color
    return obj


def box(name, center, dimensions, mat, *, bevel=0.0, direction=None):
    bpy.ops.mesh.primitive_cube_add(size=1, location=center)
    obj = finish(name, mat)
    obj.data.transform(Matrix.Diagonal((*dimensions, 1)))
    if direction is not None:
        obj.rotation_mode = "QUATERNION"
        obj.rotation_quaternion = direction.to_track_quat("Z", "Y")
    if bevel:
        modifier = obj.modifiers.new("Machined Edges", "BEVEL")
        modifier.width, modifier.segments = bevel, 3
        bpy.ops.object.modifier_apply(modifier=modifier.name)
    return obj


def ball(name, center, radii, mat):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=20, ring_count=12, radius=1, location=center)
    obj = finish(name, mat)
    obj.data.transform(Matrix.Diagonal((*radii, 1)))
    for face in obj.data.polygons:
        face.use_smooth = True
    return obj


def make_skin(rig):
    gold = material("01 · Ochre enamel", (0.90, 0.33, 0.044), metallic=0.36)
    cream = material("02 · Porcelain trim", (0.85, 0.78, 0.55), metallic=0.15)
    rubber = material("03 · Carbon polymer", (0.016, 0.026, 0.035), roughness=0.63)
    enamel = material("04 · Teal enamel", (0.018, 0.29, 0.29), metallic=0.36)
    lamp = material("05 · Aqua lenses", (0.22, 0.91, 0.67), emission=0.45)
    parts = []

    def bind(obj, bone):
        group = obj.vertex_groups.new(name=bone)
        group.add(range(len(obj.data.vertices)), 1.0, "REPLACE")
        parts.append(obj)

    bind(box("Hip Housing", (0, 0, 1.04), (0.56, 0.32, 0.19), rubber, bevel=0.045), "Pelvis")
    bind(box("Chest Casting", (0, 0, 1.36), (0.65, 0.43, 0.47), gold, bevel=0.10), "Torso")
    bind(box("Chest Inset", (0, -0.217, 1.36), (0.33, 0.06, 0.20), enamel, bevel=0.025), "Torso")
    for i in range(3):
        bind(box(f"Status Bar {i + 1}", (0.043, -0.25, 1.315 + 0.047 * i),
                 (0.16 - 0.02 * i, 0.012, 0.014), lamp, bevel=0.004), "Torso")
    bind(ball("Neck Bearing", (0, 0, 1.62), (0.11, 0.10, 0.10), rubber), "Head")
    bind(box("Sensor Housing", (0, -0.015, 1.80), (0.59, 0.39, 0.31), cream, bevel=0.095), "Head")
    bind(box("Sensor Visor", (0, -0.205, 1.82), (0.49, 0.10, 0.16), rubber, bevel=0.047), "Head")
    for x in (-0.12, 0.12):
        bind(ball("Eye Lens", (x, -0.259, 1.82), (0.045, 0.015, 0.038), lamp), "Head")
    bind(box("Antenna Stem", (0.17, 0.045, 1.996), (0.022, 0.022, 0.16), rubber, bevel=0.006), "Head")
    bind(ball("Antenna Tip", (0.17, 0.045, 2.075), (0.045, 0.045, 0.038), gold), "Head")

    for side, sign in SIDES:
        accent = gold if side == "L" else enamel
        for name, width, depth in (("Thigh", 0.18, 0.17), ("Shin", 0.15, 0.15),
                                   ("UpperArm", 0.16, 0.16), ("Forearm", 0.17, 0.15)):
            joint = f"{name}.{side}"
            rest = rig.data.bones[joint]
            a, b = rest.head_local, rest.tail_local
            axis = b - a
            bind(ball(f"{joint} bearing", a, (width * 0.61,) * 3, rubber), joint)
            bind(box(f"{joint} shell", a.lerp(b, 0.55), (width, depth, axis.length * 0.73),
                     accent, bevel=0.029, direction=axis), joint)
        x = sign * 0.24
        bind(box(f"Sole.{side}", (x, -0.083, 0.035), (0.245, 0.41, 0.06), rubber, bevel=0.02), f"Foot.{side}")
        bind(box(f"Boot.{side}", (x, -0.068, 0.109), (0.235, 0.36, 0.135), accent, bevel=0.047), f"Foot.{side}")
        bind(box(f"Toe Stripe.{side}", (x, -0.257, 0.062), (0.14, 0.034, 0.035), cream, bevel=0.012), f"Foot.{side}")
        for finger in (-1, 1):
            bind(box(f"Gripper.{side}", (sign * 0.54 + finger * 0.04, -0.11, 0.955),
                     (0.052, 0.09, 0.11), rubber, bevel=0.016), f"Forearm.{side}")

    bpy.ops.object.select_all(action="DESELECT")
    for obj in parts:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    skin = bpy.context.object
    skin.name = "Field Tester · Skinned Mesh"
    skin.data.transform(skin.matrix_world.copy())
    skin.matrix_world = Matrix.Identity(4)
    skin.parent = rig
    modifier = skin.modifiers.new("Field Tester Skin", "ARMATURE")
    modifier.object = rig
    return skin


def curve(frame, keys):
    for (start, a), (end, b) in zip(keys, keys[1:]):
        if frame <= end:
            t = (frame - start) / (end - start)
            ease = t * t * (3 - 2 * t)
            return tuple(x + (y - x) * ease for x, y in zip(a, b))
    return keys[-1][1]


def rotate_at(matrix, angles):
    pivot = matrix.translation
    rotation = Euler(angles, "XYZ").to_matrix().to_4x4()
    return Matrix.Translation(pivot) @ rotation @ Matrix.Translation(-pivot) @ matrix


def animate(scene, rig, slipping):
    rests = {bone.name: bone.matrix_local.copy() for bone in rig.data.bones}
    inv_rests = {name: rest.inverted() for name, rest in rests.items()}
    previous = {}

    def inherit(targets, bone, angles):
        parent = rig.pose.bones[bone].parent.name
        targets[bone] = targets[parent] @ inv_rests[parent] @ rotate_at(rests[bone], angles)

    def point(bone, start, end):
        rest = rig.data.bones[bone]
        original_direction = rest.tail_local - rest.head_local
        rotation = original_direction.rotation_difference(end - start) @ rests[bone].to_quaternion()
        return Matrix.LocRotScale(start, rotation, None)

    for frame in range(FIRST, LAST + 1):
        # The weight transfer leads the right shoe; head and forearms settle at different times.
        shift, drop, hip_yaw = curve(frame, (
            (1, (0, 0, 0)), (4, (-0.025, -0.04, 0.04)), (8, (0.22, -0.085, -0.05)),
            (13, (0.24, -0.045, -0.09)), (16, (0.21, -0.085, -0.02)),
            (20, (0.17, -0.028, 0.03)), (23, (0.023, -0.022, -0.02)), (25, (0, 0, 0)),
        ))
        x, z = curve(frame, (
            (1, (-0.24, 0.15)), (6, (-0.24, 0.15)), (10, (-0.51, 0.30)),
            (15, (-0.72, 0.15)), (16, (-0.72, 0.15)), (19, (-0.47, 0.27)),
            (21, (-0.24, 0.15)), (25, (-0.24, 0.15)),
        ))
        lean, twist = curve(frame, (
            (1, (0, 0)), (6, (0.21, -0.10)), (12, (0.26, 0.12)), (16, (0.16, 0.22)),
            (19, (0.21, 0.02)), (23, (-0.045, 0.02)), (25, (0, 0)),
        ))
        nod, glance = curve(frame, (
            (1, (0, 0)), (4, (0.22, -0.30)), (8, (0.32, -0.39)), (14, (0.31, -0.49)),
            (16, (0.40, -0.38)), (20, (-0.09, 0.08)), (22, (0.07, 0.05)), (25, (0, 0)),
        ))
        reach, bend = curve(frame, (
            (1, (0, 0)), (5, (0.16, 0.15)), (10, (0.77, 0.35)), (14, (1, 0.62)),
            (17, (0.71, 0.82)), (21, (0.30, 0.31)), (25, (0, 0)),
        ))
        slide = 0.0
        if slipping and 6 < frame < 20:
            slide = 0.08 * math.sin(math.pi * (frame - 6) / 14) ** 2
        targets = {"Root": rests["Root"],
                   "Pelvis": Matrix.Translation((shift, 0, drop)) @ rotate_at(rests["Pelvis"], (0, 0, hip_yaw))}
        inherit(targets, "Torso", (0.08 * reach, lean, twist))
        inherit(targets, "Head", (nod, -0.45 * lean, glance))
        ankles = {"L": Vector((0.24 + slide, 0, 0.15)), "R": Vector((x, 0, z))}
        pelvis_delta = targets["Pelvis"] @ inv_rests["Pelvis"]
        for side, sign in SIDES:
            thigh, shin, foot = (f"{part}.{side}" for part in ("Thigh", "Shin", "Foot"))
            hip = pelvis_delta @ rests[thigh].translation
            ankle = ankles[side]
            knee = knee_position(hip, ankle)
            targets[thigh] = point(thigh, hip, knee)
            targets[shin] = point(shin, knee, ankle)
            targets[foot] = Matrix.Translation(ankle - rests[foot].translation) @ rests[foot]
            inherit(targets, f"UpperArm.{side}", (-0.21 * sign * reach, -sign * 0.82 * reach, 0.1 * reach))
            inherit(targets, f"Forearm.{side}", (sign * 0.29 * bend, sign * 0.43 * bend, 0.24 * bend))

        for name, matrix in targets.items():
            pb = rig.pose.bones[name]
            kwargs = {}
            if pb.parent:
                kwargs = {"parent_matrix": targets[pb.parent.name], "parent_matrix_local": rests[pb.parent.name]}
            basis = pb.bone.convert_local_to_pose(matrix, rests[name], invert=True, **kwargs)
            location, rotation, _ = basis.decompose()
            if name in previous:
                rotation.make_compatible(previous[name])
            previous[name] = rotation
            pb.rotation_mode = "QUATERNION"
            pb.location, pb.rotation_quaternion = location, rotation
            pb.keyframe_insert("location", frame=frame, group=name)
            pb.keyframe_insert("rotation_quaternion", frame=frame, group=name)

    animation = rig.animation_data
    animation.action.name = "TapRecovery"
    channelbag = action_get_channelbag_for_slot(animation.action, animation.action_slot)
    for fcurve in channelbag.fcurves:
        for key in fcurve.keyframe_points:
            key.interpolation = "LINEAR"
    for frame, label in ((1, "Ready"), (4, "Notice / coil"), (8, "Weight over plant"),
                         (11, "Swing breakdown"), (15, "Tap accent"), (19, "Recoil"),
                         (21, "Replace foot"), (25, "Loop endpoint")):
        scene.timeline_markers.new(label, frame=frame)


def aim(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()


def make_stage(scene):
    graphite = material("Stage · graphite", (0.041, 0.059, 0.083), metallic=0.24)
    base = material("Stage · backdrop", (0.014, 0.029, 0.042), roughness=0.65)
    teal = material("Stage · tap mark", (0.042, 0.45, 0.42), emission=0.15)
    amber = material("Stage · plant mark", (0.90, 0.41, 0.068), emission=0.10)
    box("Studio Floor", (0, 0, -0.25), (200, 200, 0.12), base)
    bpy.ops.mesh.primitive_cylinder_add(vertices=96, radius=1.20, depth=0.18, location=(0, 0, -0.09))
    finish("Test Platform", graphite)
    for direction in (-1, 1):
        box("Tap pad bracket", (-0.72 + 0.14 * direction, -0.071, 0.001), (0.018, 0.44, 0.002), teal, bevel=0.001)
        box("Plant pad bracket", (0.24 + 0.14 * direction, -0.071, 0.001), (0.018, 0.44, 0.002), amber, bevel=0.001)
    for i in range(9):
        longer = i in (0, 4, 8)
        box("Floor scale tick", (-0.72 + 0.12 * i, -0.58, 0.001),
            (0.011, 0.085 if longer else 0.045, 0.002), teal if i < 4 else amber)

    world = bpy.data.worlds.new("Blue Hour")
    world.use_nodes = True
    world.node_tree.nodes.get("Background").inputs["Color"].default_value = (0.19, 0.27, 0.42, 1)
    world.node_tree.nodes.get("Background").inputs["Strength"].default_value = 0.30
    scene.world = world

    for name, xyz, watts, color, size in (
        ("Soft Key", (-3.2, -4.0, 5.1), 440, (1.0, 0.83, 0.65), 3.0),
        ("Cool Fill", (3.0, -2.2, 2.5), 195, (0.57, 0.79, 1.0), 2.0),
        ("Edge Light", (1.0, 3.4, 4.2), 620, (0.48, 0.89, 1.0), 2.4),
    ):
        data = bpy.data.lights.new(name, "AREA")
        data.energy, data.color, data.size = watts, color, size
        obj = bpy.data.objects.new(name, data)
        bpy.context.collection.objects.link(obj)
        obj.location = xyz
        aim(obj, (0, 0, 1.0))
    data = bpy.data.cameras.new("Sample Camera")
    data.type, data.ortho_scale = "ORTHO", 3.16
    camera = bpy.data.objects.new("Sample Camera", data)
    bpy.context.collection.objects.link(camera)
    camera.location = (2.8, -7.4, 3.35)
    aim(camera, (0, 0, 0.97))
    scene.camera = camera
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == "VIEW_3D":
                area.spaces.active.region_3d.view_perspective = "CAMERA"
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 12
    scene.cycles.use_denoising = True
    scene.render.resolution_x, scene.render.resolution_y = 720, 540
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--variant", choices=("clean", "slipping"), default="clean")
    parser.add_argument("--no-render", action="store_true", help="Only save the .blend and .glb")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    out = args.out_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.frame_start, scene.frame_end = FIRST, LAST
    scene.render.fps, scene.render.fps_base = FPS, 1
    scene.unit_settings.system = "METRIC"
    rig = make_rig()
    skin = make_skin(rig)
    animate(scene, rig, args.variant == "slipping")
    make_stage(scene)
    scene.frame_set(FIRST)
    scene.render.filepath = "//frame_"
    bpy.ops.object.select_all(action="DESELECT")
    rig.select_set(True)
    skin.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(out / "sample.blend"))
    bpy.ops.export_scene.gltf(
        filepath=str(out / "sample.glb"), export_format="GLB", use_selection=True,
        export_animations=True, export_animation_mode="ACTIONS", export_force_sampling=True,
        export_frame_range=True, export_anim_slide_to_zero=True,
    )
    if not args.no_render:
        for frame in PREVIEW_FRAMES:
            scene.frame_set(frame)
            scene.render.filepath = str(out / f"frame_{frame:03d}.png")
            bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    main()
