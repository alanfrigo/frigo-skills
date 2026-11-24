"""Blender 4.5+ CLI: inspect, prepare a static delivery, or render review views."""

import argparse
import json
import math
import sys
import time
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector


def load_source(path, merge_vertices):
    suffix = path.suffix.lower()
    if not path.is_file():
        raise ValueError(f"Source does not exist: {path}")
    if suffix == ".blend":
        bpy.ops.wm.open_mainfile(filepath=str(path), use_scripts=False)
    else:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        if suffix in {".glb", ".gltf"}:
            bpy.ops.import_scene.gltf(filepath=str(path), merge_vertices=merge_vertices)
        elif suffix == ".obj":
            bpy.ops.wm.obj_import(filepath=str(path))
        elif suffix == ".fbx":
            bpy.ops.import_scene.fbx(filepath=str(path), use_anim=True)
        else:
            raise ValueError(f"Unsupported source format: {suffix}")
    if bpy.context.object and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    return bpy.context.scene


def mesh_objects(scene):
    meshes = [obj for obj in scene.objects if obj.type == "MESH"]
    if not meshes:
        raise ValueError("Active scene has no mesh objects")
    return meshes


def extend_bounds(lo, hi, obj, mesh):
    if not mesh.vertices:
        return
    coords = np.empty(len(mesh.vertices) * 3, dtype=np.float32)
    mesh.vertices.foreach_get("co", coords)
    coords = coords.reshape(-1, 3)
    matrix = np.asarray(obj.matrix_world, dtype=np.float64)
    for axis, row in enumerate(matrix):
        if axis == 3:
            break
        values = coords @ row[:3] + row[3]
        if not np.isfinite(values).all():
            raise ValueError(f"{obj.name}: non-finite evaluated mesh coordinate")
        lo[axis] = min(lo[axis], float(values.min()))
        hi[axis] = max(hi[axis], float(values.max()))


def topology(mesh):
    bm = bmesh.new()
    try:
        bm.from_mesh(mesh)
        return {
            "boundary_edges": sum(edge.is_boundary for edge in bm.edges),
            "wire_edges": sum(edge.is_wire for edge in bm.edges),
            "edges_with_more_than_two_faces": sum(len(edge.link_faces) > 2 for edge in bm.edges),
            "inconsistent_winding_edges": sum(edge.is_manifold and not edge.is_contiguous for edge in bm.edges),
            "loose_vertices": sum(not vert.link_edges for vert in bm.verts),
        }
    finally:
        bm.free()


def inventory_images(tree, visited, images):
    if tree is None or tree in visited:
        return
    visited.add(tree)
    for node in tree.nodes:
        if node.type == "TEX_IMAGE" and node.image:
            image = node.image
            images[image.name] = {
                "size": list(image.size), "color_space": image.colorspace_settings.name,
                "source": image.source, "packed_in_blend": bool(image.packed_file),
            }
        elif node.type == "GROUP":
            inventory_images(node.node_tree, visited, images)


def measure(scene, meshes, *, full):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    lo, hi = [math.inf] * 3, [-math.inf] * 3
    objects, materials = [], set()
    for source in meshes:
        obj = source.evaluated_get(depsgraph)
        mesh = obj.to_mesh()
        try:
            triangles = mesh.loop_triangles
            extend_bounds(lo, hi, obj, mesh)
            row = {"name": obj.name, "vertices": len(mesh.vertices), "triangles": len(triangles)}
            if full:
                for polygon in mesh.polygons:
                    i = polygon.material_index
                    if i < len(obj.material_slots) and obj.material_slots[i].material:
                        materials.add(obj.material_slots[i].material)
                row.update(topology(mesh))
                row.update(uv_layers=list(mesh.uv_layers.keys()),
                           zero_area_triangles=sum(tri.area == 0 for tri in triangles))
            objects.append(row)
        finally:
            obj.to_mesh_clear()
    totals = {key: sum(obj[key] for obj in objects) for key, val in objects[0].items() if isinstance(val, int)}
    if not totals["triangles"]:
        raise ValueError("Active scene contains no evaluated mesh triangles")
    bounds = {"min": lo, "max": hi, "size": [b - a for a, b in zip(lo, hi)]}
    result = {"bounds_blender_units": bounds, "totals": totals, "meshes": objects}
    if full:
        images, visited = {}, set()
        for material in materials:
            inventory_images(material.node_tree, visited, images)
        result.update(
            scene=scene.name, frame=scene.frame_current, meters_per_blender_unit=scene.unit_settings.scale_length,
            materials=sorted(material.name for material in materials), image_nodes=images,
            armatures=sorted(obj.name for obj in scene.objects if obj.type == "ARMATURE"),
        )
    return result


def gates(result, args):
    totals = result["totals"]
    failures = []
    if args.max_triangles and totals["triangles"] > args.max_triangles:
        failures.append(f'{totals["triangles"]} triangles exceeds {args.max_triangles}')
    if args.max_materials and len(result["materials"]) > args.max_materials:
        failures.append(f'{len(result["materials"])} materials exceeds {args.max_materials}')
    if args.max_texture:
        for name, image in result["image_nodes"].items():
            if max(image["size"]) > args.max_texture:
                failures.append(f'{name}: {image["size"]} exceeds {args.max_texture} px')
            if not min(image["size"]):
                failures.append(f"{name}: cannot read image dimensions")
    if args.require_uv:
        failures.extend(f'{row["name"]}: no UV layer' for row in result["meshes"]
                        if row["triangles"] and not row["uv_layers"])
    if args.watertight:
        # Edge topology is necessary, not proof of a closed volume (no self-intersection test).
        for key in ("boundary_edges", "edges_with_more_than_two_faces", "wire_edges",
                    "inconsistent_winding_edges", "loose_vertices", "zero_area_triangles"):
            if totals[key]:
                failures.append(f"{key}: {totals[key]}")
    return failures


def prepare(scene, meshes, args):
    scope = set(meshes)
    for obj in meshes:
        while obj.parent:
            obj = obj.parent
            scope.add(obj)
    if any(obj.type not in {"MESH", "EMPTY"} or obj.animation_data or obj.constraints or
           (obj.type == "MESH" and (obj.data.shape_keys or any(mod.type == "ARMATURE" for mod in obj.modifiers)))
           for obj in scope) or any(obj.type == "ARMATURE" for obj in scene.objects):
        raise ValueError("prepare is static-only; use the authored Blender rig/export pipeline for this input")
    start = time.monotonic()
    original = measure(scene, meshes, full=False)
    working = original
    if args.decimate and original["totals"]["triangles"] > args.max_triangles:
        ratio = args.max_triangles / original["totals"]["triangles"]
        for obj in meshes:
            mod = obj.modifiers.new("Static budget reduction", "DECIMATE")
            mod.ratio = ratio
            mod.use_collapse_triangulate = True
        bpy.context.view_layer.update()
        if args.ground or args.extent_m:
            working = measure(scene, meshes, full=False)
    bounds = working["bounds_blender_units"]
    scale = args.extent_m / max(bounds["size"]) if args.extent_m else scene.unit_settings.scale_length
    offset = Vector((0, 0, 0))
    if args.ground:
        offset = Vector(((bounds["min"][0] + bounds["max"][0]) / 2,
                         (bounds["min"][1] + bounds["max"][1]) / 2, bounds["min"][2]))
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    if args.ground or scale != 1.0:
        root = bpy.data.objects.new("AssetPivot", None)
        scene.collection.objects.link(root)
        shift = Matrix.Translation(-offset)
        for obj in sorted(scope, key=lambda obj: obj.name):
            if obj.parent is None:
                world = obj.matrix_world.copy()
                obj.parent = root
                obj.matrix_world = shift @ world
        root.scale = (scale, scale, scale)
        scope.add(root)
    bpy.context.view_layer.update()
    result = measure(scene, meshes, full=True)
    result["source_triangles"] = original["totals"]["triangles"]
    result["failures"] = gates(result, args)
    if result["failures"]:
        return result
    args.out.mkdir(parents=True, exist_ok=False)
    bpy.ops.file.pack_all()
    bpy.ops.object.select_all(action="DESELECT")
    for obj in scope:
        obj.select_set(True)
        if not obj.select_get():
            raise ValueError(f"{obj.name}: cannot select for export")
    bpy.ops.wm.save_as_mainfile(filepath=str(args.out / "source.blend"))
    status = bpy.ops.export_scene.gltf(
        filepath=str(args.out / "asset.glb"), export_format="GLB", use_selection=True,
        export_apply=True, export_animations=False, export_cameras=False, export_lights=False,
    )
    if status != {"FINISHED"} or not (args.out / "asset.glb").is_file():
        raise ValueError(f"GLB export failed: {status}")
    result["glb_bytes"] = (args.out / "asset.glb").stat().st_size
    result["prepare_seconds"] = round(time.monotonic() - start, 3)
    save_report(args.out / "report.json", result)
    return result


VIEWS = {
    "front": (0, -1, 0), "right": (1, 0, 0), "rear": (0, 1, 0),
    "left": (-1, 0, 0), "three-quarter": (1, -1, 0.65), "top": (0, 0, 1),
}


def preview(scene, meshes, out, mode, size, views, transparent):
    bounds = measure(scene, meshes, full=False)["bounds_blender_units"]
    center = (Vector(bounds["min"]) + Vector(bounds["max"])) * 0.5
    diameter = Vector(bounds["size"]).length
    for obj in scene.objects:
        if obj.type != "MESH":
            obj.hide_render = True
    camera = bpy.data.objects.new("ReviewCamera", bpy.data.cameras.new("ReviewCamera"))
    scene.collection.objects.link(camera)
    scene.camera = camera
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = diameter * 1.10
    camera.data.clip_start = max(diameter * 0.001, 0.000001)
    camera.data.clip_end = diameter * 10
    scene.render.resolution_x = scene.render.resolution_y = size
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA" if transparent else "RGB"
    scene.render.film_transparent = transparent
    scene.render.use_sequencer = False
    if mode == "solid":
        scene.render.engine = "BLENDER_WORKBENCH"
        shading = scene.display.shading
        shading.light = "STUDIO"
        shading.color_type = "SINGLE"
        shading.single_color = (0.62, 0.62, 0.62)
        shading.show_cavity = True
    else:
        scene.render.engine = "CYCLES"
        scene.cycles.device = "CPU"
        scene.cycles.samples = 12
        scene.cycles.use_denoising = True
        scene.world = bpy.data.worlds.new("ReviewWorld")
        scene.world.use_nodes = True
        background = next(n for n in scene.world.node_tree.nodes if n.type == "BACKGROUND")
        background.inputs[0].default_value = (0.32, 0.32, 0.32, 1)
        scene.view_settings.view_transform = "AgX"
        for i, (direction, power) in enumerate([((-2, -3, 4), 140), ((3, -1, 2), 85), ((1, 4, 3), 170)]):
            data = bpy.data.lights.new(f"ReviewArea{i}", "AREA")
            light = bpy.data.objects.new(data.name, data)
            scene.collection.objects.link(light)
            light.location = center + Vector(direction).normalized() * diameter * 1.6
            light.rotation_euler = (center - light.location).to_track_quat("-Z", "Y").to_euler()
            data.energy = power * diameter * diameter
            data.shape = "DISK"
            data.size = diameter
    out.mkdir(parents=True, exist_ok=False)
    for name in views:
        camera.location = center + Vector(VIEWS[name]).normalized() * diameter * 2
        camera.rotation_euler = (center - camera.location).to_track_quat("-Z", "Y").to_euler()
        scene.render.filepath = str(out / f"{name}.png")
        if bpy.ops.render.render(write_still=True) != {"FINISHED"}:
            raise ValueError(f"Render failed for {name}")


def save_report(path, result):
    with path.open("x", encoding="utf-8") as file:
        json.dump(result, file, allow_nan=False, indent=2)
        file.write("\n")


def positive_int(raw):
    value = int(raw)
    if value < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return value


def positive_float(raw):
    value = float(raw)
    if not math.isfinite(value) or value <= 0:
        raise argparse.ArgumentTypeError("must be finite and positive")
    return value


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("inspect", "prepare", "preview"):
        cmd = sub.add_parser(name)
        cmd.add_argument("source", type=lambda p: Path(p).resolve())
        cmd.add_argument("--out", type=lambda p: Path(p).resolve(), required=name != "inspect")
        cmd.add_argument("--merge-vertices", action="store_true", help="glTF only: merge compatible import vertices")
        if name != "preview":
            cmd.add_argument("--max-triangles", type=positive_int)
            cmd.add_argument("--max-materials", type=positive_int)
            cmd.add_argument("--max-texture", type=positive_int, help="Limit either image dimension, in pixels")
            cmd.add_argument("--require-uv", action="store_true")
            cmd.add_argument("--watertight", action="store_true", help="Gate closed edge topology, not self-intersections")
        if name == "prepare":
            cmd.add_argument("--extent-m", type=positive_float, help="Set longest world-space dimension in metres")
            cmd.add_argument("--ground", action="store_true", help="Place an asset root at XY bounds centre and base Z")
            cmd.add_argument("--decimate", action="store_true", help="Opt in to static collapse decimation up to --max-triangles")
        if name == "preview":
            cmd.add_argument("--mode", choices=("solid", "material"), default="solid")
            cmd.add_argument("--size", type=positive_int, default=512)
            cmd.add_argument("--views", nargs="+", choices=tuple(VIEWS), default=tuple(VIEWS))
            cmd.add_argument("--transparent", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "prepare":
        if args.source.suffix.lower() == ".blend":
            parser.error("prepare expects an interchange mesh; inspect or preview editable .blend sources")
        if args.decimate and not args.max_triangles:
            parser.error("--decimate requires --max-triangles")
    return args


def main(argv):
    args = parse_args(argv)
    if args.out and args.out.exists():
        raise ValueError(f"Refusing to overwrite {args.out}")
    start = time.monotonic()
    scene = load_source(args.source, args.merge_vertices)
    meshes = mesh_objects(scene)
    if args.command == "preview":
        preview(scene, meshes, args.out, args.mode, args.size, args.views, args.transparent)
        print(json.dumps({"views": args.views, "mode": args.mode, "seconds": round(time.monotonic() - start, 3)}))
        return 0
    if args.command == "inspect":
        result = measure(scene, meshes, full=True)
        result["source_bytes"] = args.source.stat().st_size
        result["failures"] = gates(result, args)
        result["inspect_seconds"] = round(time.monotonic() - start, 3)
        if args.out:
            save_report(args.out, result)
    else:
        result = prepare(scene, meshes, args)
    print(json.dumps(result, allow_nan=False))
    return 2 if result["failures"] else 0


if __name__ == "__main__":
    try:
        sys.stdout.flush()
        status = main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        status = 1
    sys.stdout.flush()
    sys.stderr.flush()
    sys.exit(status)
