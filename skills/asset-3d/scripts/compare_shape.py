"""Compare two meshes with symmetric area-sampled surface distance in Blender."""

import argparse
from bisect import bisect
import json
import math
import random
import statistics
import sys
from itertools import accumulate
from pathlib import Path

import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
from blender_asset import load_source, mesh_objects, positive_int, save_report  # noqa: E402


def surface(path, yaw):
    scene = load_source(path, False)
    depsgraph = bpy.context.evaluated_depsgraph_get()
    verts, tris = [], []
    rotation = Matrix.Rotation(math.radians(yaw), 4, "Z")
    for obj in mesh_objects(scene):
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        try:
            matrix = rotation @ evaluated.matrix_world
            start = len(verts)
            verts.extend(matrix @ v.co for v in mesh.vertices)
            tris.extend(tuple(start + i for i in t.vertices) for t in mesh.loop_triangles if t.area > 0)
        finally:
            evaluated.to_mesh_clear()
    if not tris:
        raise ValueError(f"No positive-area triangles in {path}")
    # Loose vertices do not belong to the sampled surface and must not set its scale.
    used = {i for tri in tris for i in tri}
    lo = Vector(tuple(min(verts[i][axis] for i in used) for axis in range(3)))
    hi = Vector(tuple(max(verts[i][axis] for i in used) for axis in range(3)))
    center, extent = (lo + hi) * 0.5, max(hi - lo)
    if extent <= 0 or not math.isfinite(extent):
        raise ValueError(f"Invalid bounds in {path}")
    verts = [(v - center) / extent for v in verts]
    areas = list(accumulate((verts[b] - verts[a]).cross(verts[c] - verts[a]).length / 2 for a, b, c in tris))
    if not areas[-1] > 0 or not math.isfinite(areas[-1]):
        raise ValueError(f"Invalid world-space area in {path}")
    return verts, tris, areas, list(hi - lo)


def directed(source, target, count, seed):
    verts, tris, areas, _ = source
    bvh = BVHTree.FromPolygons(target[0], target[1], all_triangles=True)
    rng = random.Random(seed)
    distances = []
    for _ in range(count):
        a, b, c = tris[min(bisect(areas, rng.random() * areas[-1]), len(tris) - 1)]
        u, v = math.sqrt(rng.random()), rng.random()
        point = verts[a] * (1 - u) + verts[b] * (u * (1 - v)) + verts[c] * (u * v)
        _, _, _, distance = bvh.find_nearest(point)
        distances.append(distance)
    distances.sort()
    return {"mean": statistics.fmean(distances), "p95": distances[math.ceil(count * 0.95) - 1],
            "max_sampled": distances[-1]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=lambda p: Path(p).resolve())
    parser.add_argument("candidate", type=lambda p: Path(p).resolve())
    parser.add_argument("--yaw-deg", type=float, default=0, help="Explicit candidate rotation around Blender +Z before normalization")
    parser.add_argument("--samples", type=positive_int, default=8192, help="Number of points in each direction")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    if not math.isfinite(args.yaw_deg):
        parser.error("--yaw-deg must be finite")
    ref, candidate = surface(args.reference, 0), surface(args.candidate, args.yaw_deg)
    forward = directed(ref, candidate, args.samples, args.seed)
    reverse = directed(candidate, ref, args.samples, args.seed + 1)
    result = {"method": "independent AABB midpoint and longest-side normalization; unsquared nearest triangle distance",
              "reference_blender_bounds_size": ref[3], "candidate_blender_bounds_size_after_yaw": candidate[3],
              "candidate_yaw_deg": args.yaw_deg, "samples_per_direction": args.samples, "seed": args.seed,
              "reference_to_candidate": forward, "candidate_to_reference": reverse,
              "symmetric_mean": (forward["mean"] + reverse["mean"]) / 2}
    if args.out:
        save_report(args.out, result)
    print(json.dumps(result, allow_nan=False))


if __name__ == "__main__":
    main()
