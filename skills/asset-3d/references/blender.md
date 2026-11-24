# Blender QA and delivery

Blender 4.5+ on PATH or supply its absolute executable. `bpy` is Blender's Python; run these in Blender, not system Python. Open only trusted files, disable auto-execution for review, and keep edits in new work directories. The helpers inspect the active scene's mesh objects; isolate the asset in its own scene/file when environment geometry, collision, or multiple LODs would skew results.

```sh
S=/absolute/path/to/asset-3d/scripts
blender -b --factory-startup --disable-autoexec --python-exit-code 1 \
  --python "$S/blender_asset.py" -- inspect raw.glb --out raw-report.json
blender -b --factory-startup --disable-autoexec --python-exit-code 1 \
  --python "$S/blender_asset.py" -- preview raw.glb --out raw-clay --mode solid
blender -b --factory-startup --disable-autoexec --python-exit-code 1 \
  --python "$S/blender_asset.py" -- preview raw.glb --out raw-pbr --mode material
```

`inspect` reports evaluated triangles, vertices, world-axis bounds in Blender units, scene unit scale, material count via the used material names, UV layers, texture-node inventory with dimensions and edge topology. `--max-triangles`, `--max-materials`, `--max-texture`, `--require-uv` and `--watertight` are opt-in gates; a failed gate returns nonzero and preserves the inspect report. `--watertight` measures boundary, wire, inconsistent winding and >2-face edges plus loose vertices and zero-area triangles; it is not proof of closed volume, correct orientation across components, thickness or absence of self-intersection. Enable only for closed-shell use cases. glTF exporters can split a Blender vertex at UV/normal boundaries; report the default import for cost proxies and separately use `--merge-vertices` for compatible topology welds. Treat counts accordingly; neither is necessarily the vertex count seen by every engine renderer. Texture inventory reports image nodes, not reachable material branches, bake fidelity, GPU residency, UV overlap or file-format validity. Cycles material views use CPU; solid uses Workbench. Both use fixed orthographic directions (`front` is Blender −Y), not the delivered engine camera. Override `--views` and `--size` for focused review. Separately open alpha/material settings in the engine.

## Static delivery

This helper is for incoming **static** `.glb`, `.gltf`, `.fbx` and `.obj` files only. It saves a new `.blend` with packed supported images, exports `.glb` and writes a JSON report. For non-static `.blend`/armatures, use project's authored export path; this helper intentionally rejects animated/skinned/shape-keyed mesh inputs instead of silently flattening them. `--extent-m` is longest AABB dimension in metres; without it, prefer the imported dimensions in its scene unit scale. `--ground` recentres XY bounds and moves the base to Z=0 relative to a new `AssetPivot`. Omit it when an authored axis, hinge or socket origin is required. Axes are Blender's; don't rotate again to compensate for glTF's exporter conversion. Select project axes explicitly in Blender if generator orientation is wrong.

```sh
blender -b --factory-startup --disable-autoexec --python-exit-code 1 \
  --python "$S/blender_asset.py" -- prepare raw.glb --out delivery-r01 \
  --extent-m 0.28 --ground --decimate --max-triangles 10000 --max-texture 1024 --require-uv
blender -b --factory-startup --disable-autoexec --python-exit-code 1 \
  --python "$S/blender_asset.py" -- inspect delivery-r01/asset.glb \
  --out runtime-report.json --max-triangles 10000 --max-texture 1024 --require-uv
```

Budget values above are examples, not defaults. `--decimate` is destructive to topology in the **export**, non-destructive to the new `.blend`; it is approximate and opt-in with a hard post-check. If it misses the budget, don't loosen the target silently. Compare clay, UV/material and target-size silhouette with the original. For hand-authored retopo use Blender snap/shrinkwrap and proper seam/loop flow, rebake the source detail, and record the authored LOD separately. Do not use auto-remesh or welding blindly on cloth, split normals, baked maps or deformation-critical joints. Materials with procedural shading or unsupported nodes need a bake to supported glTF maps, not merely packing into `.blend`.

## Runtime gate

1. Reimport the just-exported file into a clean scene. Check triangle counts, expected UVs and textures, origin/extent and orientation. Check the original axis against a familiar camera; the same AABB can hide a backwards asset.
2. Validate compatibility per [Blender glTF manual](https://docs.blender.org/manual/en/4.5/addons/import_export/scene_gltf2.html); optionally run the [Khronos glTF Validator](https://github.com/KhronosGroup/glTF-Validator) without uploading sensitive content. Use the intended environment (e.g. [Godot scene format guidance](https://docs.godotengine.org/en/stable/tutorials/assets_pipeline/importing_3d_scenes/available_formats.html)), standard package paths and its importer settings. Loading only in Blender does not cover runtime.
3. Place the asset next to an engine scale reference; rotate around the pivot, check sockets/collisions and LOD transitions, inspect at player camera distance. If it animates, play the clip in engine, including loop/transition and root handling. For web use the application's actual loader and decompression dependencies; verify on the target device. Use project FBX conventions where glTF is not the runtime contract; FBX export isn't handled by the static helper.
4. Inspect labeled views, not just metadata. For batches, build a small in-engine gallery with stable IDs. Report `pass / fail / not assessed` for visual, topology, budget, engine, deformation and licensing gates separately. Keep original files and reviewed derivatives; don't label unresolved visual failures game-ready.
