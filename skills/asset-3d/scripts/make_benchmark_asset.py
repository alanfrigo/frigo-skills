"""Make a reference GLB and fixed input views for the local 3D benchmark."""

import argparse
import math
import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from blender_asset import mesh_objects, preview  # noqa: E402


def material(name, color, roughness, metallic=0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.diffuse_color = (*color, 1)
    shader = next(node for node in mat.node_tree.nodes if node.type == "BSDF_PRINCIPLED")
    shader.inputs["Base Color"].default_value = (*color, 1)
    shader.inputs["Roughness"].default_value = roughness
    shader.inputs["Metallic"].default_value = metallic
    return mat


def decorate(obj, name, mat, bevel):
    obj.name = name
    obj.data.materials.append(mat)
    if bevel:
        mod = obj.modifiers.new("Machined edges", "BEVEL")
        mod.width, mod.segments = bevel, 3
        mod.harden_normals = True
        for face in obj.data.polygons:
            face.use_smooth = True
        normal = obj.modifiers.new("Face normals", "WEIGHTED_NORMAL")
        normal.keep_sharp = True
    return obj


def box(name, xyz, size, mat, bevel=0.004):
    bpy.ops.mesh.primitive_cube_add(size=1, location=xyz)
    obj = bpy.context.object
    obj.scale = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    decorate(obj, name, mat, bevel)


def cylinder(name, xyz, radius, depth, mat, *, front=False, sides=24):
    bpy.ops.mesh.primitive_cylinder_add(vertices=sides, radius=radius, depth=depth, location=xyz,
                                        rotation=(math.pi / 2, 0, 0) if front else (0, 0, 0))
    decorate(bpy.context.object, name, mat, 0.0015)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=lambda p: Path(p).resolve())
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    args.out.mkdir(parents=True, exist_ok=False)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    orange = material("Saffron polymer", (0.72, 0.16, 0.035), 0.46)
    black = material("Graphite rubber", (0.022, 0.029, 0.036), 0.72)
    grey = material("Cast aluminium", (0.21, 0.27, 0.29), 0.39, 0.65)
    glass = material("Sea glass", (0.025, 0.21, 0.20), 0.25, 0.12)
    mint = material("LCD mint", (0.34, 0.9, 0.63), 0.43)
    box("Moulded housing", (0, 0, 0.098), (0.275, 0.110, 0.168), orange, 0.018)
    box("Front faceplate", (0, -0.054, 0.098), (0.248, 0.017, 0.141), black, 0.009)
    for x in (-0.103, 0.103):
        box(f"Foot {x}", (x, 0, 0.012), (0.048, 0.093, 0.024), black)
    box("Screen bezel", (-0.044, -0.064, 0.131), (0.119, 0.011, 0.049), grey)
    box("Screen glass", (-0.044, -0.070, 0.131), (0.106, 0.005, 0.037), glass, 0.002)
    for i, height in enumerate((0.007, 0.012, 0.018, 0.024)):
        box(f"Signal bar {i}", (-0.070 + 0.014*i, -0.073, 0.119 + height/2),
            (0.008, 0.002, height), mint, 0.0008)
    for i in range(4):
        box(f"Speaker louvre {i}", (-0.046, -0.065, 0.052 + i*0.012), (0.104, 0.009, 0.0046), grey, 0.002)
    cylinder("Dial base", (0.074, -0.069, 0.117), 0.031, 0.019, grey, front=True)
    cylinder("Tuning dial", (0.074, -0.083, 0.117), 0.025, 0.017, orange, front=True, sides=12)
    box("Dial index", (0.074, -0.092, 0.130), (0.005, 0.002, 0.014), black, 0.001)
    cylinder("Power switch", (0.080, -0.069, 0.056), 0.012, 0.016, grey, front=True)
    box("Battery door", (-0.026, 0.056, 0.075), (0.140, 0.013, 0.085), black, 0.005)
    for i in range(3):
        box(f"Battery latch {i}", (-0.052 + i*0.025, 0.064, 0.092), (0.013, 0.006, 0.008), grey, 0.002)
    cylinder("Antenna socket", (0.093, 0.020, 0.180), 0.014, 0.021, grey)
    cylinder("Antenna mast", (0.093, 0.020, 0.226), 0.007, 0.088, black)
    cylinder("Antenna tip", (0.093, 0.020, 0.273), 0.009, 0.020, black)
    bpy.ops.wm.save_as_mainfile(filepath=str(args.out / "reference.blend"))
    if bpy.ops.export_scene.gltf(filepath=str(args.out / "reference.glb"), export_format="GLB",
                                 export_apply=True, export_animations=False) != {"FINISHED"}:
        raise RuntimeError("Fixture GLB export failed")
    preview(scene, mesh_objects(scene), args.out / "views", "material", 640,
            ("front", "left", "rear", "right", "three-quarter"), True)


if __name__ == "__main__":
    main()
