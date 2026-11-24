# Reproduce the asset benchmark

The fixture is an original field radio with visible feet, a thin off-centre antenna, several exact front details and a separate rear panel. It has reference geometry, materials and matched-angle PNGs; no external dataset, source images or license downloads are needed for the fixture. This compares reconstruction and static processing on one stylized hard-surface asset, not a survey of art styles or hero-character quality.

## Method

[3DCodeBench](https://github.com/gaoypeng/3dcodebench) separates Blender execution, multi-view appearance and geometric scoring. Follow that separation here and add the engine check. Successful cases retain raw GLBs, exact Comfy prompt, seed, input hash, profile, measured time, review images and geometry report. Failures stay in the total, without invented appearance or shape scores. For broader comparisons, repeat at three or more fixed seeds, across a rigid prop, thin/concave organic prop and bind-pose character; report success count, median and spread, human A/B at target camera, plus minutes of cleanup. Compare equivalent conditioning and budgets; multiview and single-image cases are not a fair model-only A/B.

`compare_shape.py` samples each mesh proportionally to triangle area and finds the closest point on continuous triangles of the other model. It reports unsigned means and p95 in both directions and their mean. Distances are fractions of the longest AABB dimension after independently centring and uniformly normalizing each mesh. If necessary, determine an explicit Z-axis yaw from fixed clay views before running it; yaw 0 is default. Save the selected angle; there is no automatic pose fit or mirroring. This is **not the original 3DCodeBench Chamfer metric** (theirs uses sampled point clouds); neither evaluates material, dimensions in metres, symmetry correctness, rig readiness, scale/orientation delivery, or hairline detail reliably. Use those gates separately. Use the original repo's metrics/data and its sandbox requirements for leaderboard comparisons, not this fixture.

## Commands

```sh
S="$PWD/skills/asset-3d/scripts"
B="$(mktemp -d)"
bl() { blender -b -t 4 --factory-startup --disable-autoexec --python-exit-code 1 --python "$@"; }
bl "$S/make_benchmark_asset.py" -- --out "$B/fixture"
bl "$S/blender_asset.py" -- prepare "$B/fixture/reference.glb" --merge-vertices \
  --out "$B/low-radio" --extent-m .4 --ground --decimate --max-triangles 3200 --require-uv
bl "$S/blender_asset.py" -- inspect "$B/low-radio/asset.glb" \
  --out "$B/low-radio-roundtrip.json" --max-triangles 3200 --require-uv
bl "$S/compare_shape.py" -- "$B/fixture/reference.glb" "$B/low-radio/asset.glb" \
  --samples 8192 --seed 42 --out "$B/low-radio-shape.json"
bl "$S/blender_asset.py" -- preview "$B/low-radio/asset.glb" --out "$B/low-radio-clay"
```

Local generative runs assume the core models in [comfyui.md](comfyui.md) and an otherwise idle server. Use that server's loopback URL; `8188` is the CLI default. Run the jobs sequentially on the same GPU. Preserve full stdout as the run report.

```sh
for model in trellis2 pixal3d; do
  python3 "$S/comfy_3d.py" inspect --pipeline "$model" --profile quick
  python3 "$S/comfy_3d.py" run --pipeline "$model" --profile quick --seed 42 \
    --image "$B/fixture/views/three-quarter.png" --out-dir "$B/ai" > "$B/$model.json"
done
python3 "$S/comfy_3d.py" run --pipeline hunyuan-mv --profile quick --seed 42 \
  --front "$B/fixture/views/front.png" --left "$B/fixture/views/left.png" \
  --back "$B/fixture/views/rear.png" --right "$B/fixture/views/right.png" \
  --out-dir "$B/ai" > "$B/hunyuan-mv.json"
```

```sh
for model in trellis2 pixal3d; do
  python3 "$S/comfy_3d.py" run --pipeline "$model" --profile quick --seed 42 \
    --solid-remesh 192 --image "$B/fixture/views/three-quarter.png" \
    --out-dir "$B/ai" > "$B/$model-solid.json"
done
python3 "$S/comfy_3d.py" run --pipeline trellis2 --profile detail --seed 42 \
  --normal-size 1024 --ao-size 1024 --image "$B/fixture/views/three-quarter.png" \
  --out-dir "$B/ai" > "$B/trellis-detail.json"
```

Read `.artifact` from each successful result (`jq -r .artifact "$B/trellis2.json"` for example) and pass it to `inspect`, `preview` in solid and material modes, and `compare_shape.py`. For two texture-capable models, compare the same target triangles, atlas, source and seed first. Switch profiles on the winner only if it addresses an observed failure. Inspect both the raw image material and clay: painted details can inflate an impression of fidelity without adding geometry.

## Measured results

Linux x86-64, one RTX 3060 12 GiB selected, ComfyUI 0.46.3 with
PyTorch 2.12.1+cu130, Blender 5.3.0, Godot 4.7.2. Each row is one run,
seed 42. Execution is the server's `execution_start` to `execution_success`
interval; it excludes queue and transfer, but includes model loads/cache effects.
Times are not throughput estimates. Size is exact GLB bytes. Triangle counts use
Blender's imported mesh (the detailed file advertises 145,697 in GLB accessors
and Blender imported 145,688). Shape is the symmetric normalized mean, lower is
closer, **native orientation with yaw 0**. The Pixal poses are not registered to
the reference and their raw numbers combine pose and shape error.

| Case | Execution (s) | Imported triangles | GLB bytes | Shape |
|---|---:|---:|---:|---:|
| TRELLIS.2 quick | 34.818 | 31,902 | 2,056,912 | 0.00706 |
| Pixal3D quick | 32.409 | 28,870 | 2,427,244 | 0.08282 |
| Hunyuan3D 2mv quick, four views, geometry only | 42.994 | 47,644 | 849,088 | 0.01536 |
| TRELLIS.2 detail + normal/AO bakes | 152.816 | 145,688 | 9,152,828 | 0.00917 |
| TRELLIS.2 quick + solid remesh 192 | 28.689 | 35,000 | 1,447,568 | 0.01308 |
| Pixal3D quick + solid remesh 192 | 30.056 | 34,996 | 1,223,344 | 0.09522 |

- **Mechanical fidelity:** prefer the procedural radio when dimensions and rear detail matter. The authored reference has 5,660 triangles; Blender exported and reimported 3,190 under a 3,200 cap, at 0.400000 m extent and on the ground; the normalized mean vs reference was 0.000382. Its 133,384-byte GLB and the generated variants instantiated in Godot. The negative check with a one-triangle budget rejected the same asset with exit 2.
- **Single-view candidate:** TRELLIS.2 quick + solid 192 was the preferred textured starting point on this closed prop. The control and quick Pixal had triangular tears. The raw TRELLIS.2 geometry-only diagnostic (no reduction, 4,590,654 triangles) showed cleaner form and visible double-surface noise; this is not a deployable substitute. Solid remesh removed visible tears in both textured variants and reduced inconsistent winding to zero on the Blender imports. Their surface-distance scores got worse, illustrating why that metric cannot replace clay and material review. Pixal still tilted the body in its native coordinate frame. Neither single-view backend reproduced the exact rear battery hatch.
- **Multiview for occluded features:** Hunyuan's supplied rear view preserved the battery hatch and latch shapes in clay. It did not produce materials and its mesh still had more-than-two-face edges. It was a geometry starting point, not a verified watertight delivery.
- **Detailed output:** increased steps/resolution yielded a cleaner dial, antenna and speaker than unremeshed quick TRELLIS.2, but edge noise and missing rear detail remained. GLB verified base color, metallic/roughness, normal and AO (three embedded 1024² images with packed ORM). Device-wide VRAM sampled every 250 ms peaked at 11,430 MiB with 7,780 MiB resident before the run; neither value is a minimum VRAM requirement.
- **Textured static delivery:** the 31,902-triangle quick TRELLIS mesh was reduced to 7,999 triangles on Blender GLB reimport with both 512² textures, 0.283000 m extent, and a Godot runtime load of its textured surface. The underlying tears remained; reducing bytes and triangles did not make it production-ready.
- **Additional smoke checks:** both remeshed GLBs passed Blender's closed-edge gate after compatible vertex merging (`--merge-vertices --watertight`); this does not check self-intersections. A Pixal3D run with `--fov auto --mask alpha --solid-remesh 192` delivered a textured 35,000-triangle GLB (31.120 s server execution); it was an option compatibility check, not an A/B. Replaying the exact saved TRELLIS geometry prompt through generic `--workflow`, binding a new image and setting `24.target_face_count=15000`, delivered 13,667 triangles.

The fixture demonstrates working generation, measurable budgets and checks that
reject defects, not near-perfect reconstruction across styles. It does not
benchmark paid services, organic skinning, runtime frame time or game collision.
See the separate [animation validation](../../animation-3d/references/qa.md) for
a known-good and deliberately slipping clip.
