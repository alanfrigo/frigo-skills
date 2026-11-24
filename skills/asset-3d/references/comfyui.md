# Local ComfyUI image-to-mesh

Run from the repository root, or replace `skills/asset-3d` with the path to the installed skill. The client needs Python 3.9+ and only uses its standard library; ComfyUI, models and a working compute stack are installed separately. Once the weights are in place, these workflows do not need an account, internet access, Comfy Cloud or paid partner nodes.

## Pick the right pipeline

| Pipeline | Input | Output | Use it when |
| --- | --- | --- | --- |
| `trellis2` | One image | Triangle mesh with generated base color and metallic/roughness UV textures, or geometry only | You need a textured starting point and have no camera data. |
| `pixal3d` | One image plus fixed or estimated horizontal FOV | Same output types as TRELLIS.2 | Alignment to the input view is important; inspect the result from other views too. |
| `hunyuan-mv` | Front, optionally separate left/back/right views | Untextured triangle mesh | Consistent views exist and silhouette/geometry matters more than generated appearance. The native Hunyuan3D-2mv graph is not the Hunyuan3D 3.0 partner API or a Hunyuan paint graph. |

These are starting meshes, not production topology. Before accepting a result, inspect the front and unobserved sides, silhouettes, holes, disconnected parts, shading, seams and UV stretch in Blender. Plan retopology and material work if the destination requires deformation, manifold geometry, lightmap UVs or a strict texture/triangle budget. An input image does not determine hidden surfaces.

## Install and preflight

Use a recent [ComfyUI core](https://github.com/Comfy-Org/ComfyUI) build; the graphs target the native node spellings and model formats exposed by 0.46.3. A backend can start while individual 3D nodes fail to import. Check `/object_info` with `inspect`, not the browser template picker alone. For Linux/NVIDIA, install working PyTorch/CUDA builds according to the ComfyUI installation docs. The [native integration](https://blog.comfy.org/p/trellis2-and-pixal3d-are-now-native) replaces the upstream projects' custom compiled 3D dependencies with native PyTorch/SciPy implementations. No legacy TRELLIS/Pixal custom packs, `nvdiffrast`, `nvdiffrec`, or separately compiled O-Voxel/CuMesh extensions are needed for these graphs. CUDA is the recommended path for sparse generation and GPU mesh operations; a node appearing in preflight does not establish CPU/MPS/other backend compatibility or available VRAM.

With ComfyUI's Python environment active, a new native-only backend can be started from its install directory:

```sh
python main.py --listen 127.0.0.1 --port 8188 --offline --disable-all-custom-nodes
```

Recent releases support `--cuda-device 1` to select one physical GPU; check `main.py --help` for your version. Two 12 GiB cards are not a 24 GiB device: a regular graph works on the server's selected compute device. Avoid competing jobs on that device. For an already-running backend use its actual port, e.g. `--server http://127.0.0.1:8189`. `--offline` disables partner nodes and restricts frontend connectivity; it is not an OS sandbox. Use only a trusted local server and weights. The CLI also restricts connections to loopback without redirects/proxies and accepts only native non-partner nodes for the selected output and its dependencies.

Use these exact repackaged filenames (or change the relevant model nodes in your own API graph):

| Required by | ComfyUI directory | Filename / official source |
| --- | --- | --- |
| TRELLIS.2 | `models/diffusion_models/` | [`trellis_2_int8_convrot.safetensors`](https://huggingface.co/Comfy-Org/TRELLIS.2/tree/main/diffusion_models) |
| Pixal3D single view | `models/diffusion_models/` | [`pixal3d_int8_convrot.safetensors`](https://huggingface.co/Comfy-Org/Pixal3D/tree/main/diffusion_models) (not the turnaround-sheet checkpoint) |
| Both | `models/vae/` | [`trellis_2_shape_vae_bf16.safetensors`, `trellis_2_texture_vae_bf16.safetensors`](https://huggingface.co/Comfy-Org/TRELLIS.2/tree/main/vae); no texture VAE needed under `--geometry-only` |
| Both | `models/clip_vision/` | [`dino_v3_L_naf_fp32.safetensors`](https://huggingface.co/Comfy-Org/Pixal3D/tree/main/clip_vision) |
| Both, default mask | `models/background_removal/` | [`birefnet.safetensors`](https://huggingface.co/Comfy-Org/BiRefNet/tree/main/background_removal) |
| Pixal3D, `--fov auto` only | `models/geometry_estimation/` | [`moge_2_vitl_normal_fp16.safetensors`](https://huggingface.co/Comfy-Org/MoGe/tree/main/geometry_estimation) |
| Hunyuan multiview | `models/checkpoints/` | [`hunyuan3d-dit-v2-mv_fp16.safetensors`](https://huggingface.co/Comfy-Org/hunyuan3D_2.0_repackaged/tree/main/split_files); includes image encoder and geometry VAE |

```sh
python3 skills/asset-3d/scripts/comfy_3d.py inspect --pipeline trellis2 --profile quick
python3 skills/asset-3d/scripts/comfy_3d.py inspect --pipeline pixal3d --profile detail --fov auto
python3 skills/asset-3d/scripts/comfy_3d.py inspect --pipeline hunyuan-mv
```

`inspect` is read-only: it reports server version/devices, model filenames, active nodes, configured settings and required upload nodes. It checks basic node/slot contracts and model availability, not model-byte integrity, driver health or GPU memory at execution time. Use the same options as for `run` (image paths may be omitted during inspection). An absent class means check the core branch and startup errors; an unavailable model filename means check its exact name and configured model search paths. `/prompt` additionally validates the fully bound graph before it queues.

## Run and tune

```sh
python3 skills/asset-3d/scripts/comfy_3d.py run --pipeline trellis2 \
  --image prop.png --profile quick --seed 42 --out-dir runs
python3 skills/asset-3d/scripts/comfy_3d.py run --pipeline pixal3d \
  --image prop.png --fov auto --profile detail --map-size 1024 --normal-size 1024 \
  --ao-size 1024 --triangles 120000 --seed 42 --timeout 1800 --out-dir runs
python3 skills/asset-3d/scripts/comfy_3d.py run --pipeline hunyuan-mv \
  --front front.png --left left.png --back back.png --right right.png --out-dir runs
```

- Upload PNG, JPEG or WebP (32 MiB max each). Use one object with clear boundaries, no annotations or scene clutter. TRELLIS/Pixal use BiRefNet followed by a centered 1024×1024 crop on black. If a real alpha matte is available, use `--mask alpha` with an explicit alpha channel in a PNG or WebP; this bypasses BiRefNet and inverts ComfyUI's transparency mask to get the foreground. The client checks for an alpha channel, not whether its pixels form a useful matte. Pixal3D's default is the conditioning node's 49.13° horizontal FOV; supply `--fov DEGREES` for the cropped/framed input or `--fov auto` to estimate it via MoGe after cropping.
- Hunyuan's `front` input is required by the CLI; the other three are optional. Omit missing views instead of duplicating the front. Inputs are separate images, not a contact sheet. Keep consistent scale, framing and perspective; remove clutter/background before upload. Encoders use crop `none`. `--octree-resolution` tunes geometric extraction; there is no native texture or atlas option in this graph.
- `quick` (the default) uses **512 shape resolution**, no cascade, 6 steps each for structure/shape/texture, a 512² texture atlas and a 35,000-triangle decimation target for TRELLIS/Pixal. Start here on a 12 GiB GPU. `detail` uses **1024 shape resolution** via cascade, 12/20/12/12 steps for structure/shape/refinement/texture, a 1024² atlas and a 150,000-triangle target. Hunyuan uses 12 steps/128 octree in `quick` and 20 steps/256 octree in `detail`, with no decimation unless requested.
- `--resolution 512|1024|1536` sets the shape resolution for TRELLIS/Pixal, not the image or atlas size. `--steps N` sets every active sampler's step count. Lower steps trade detail and possibly coherence for time. `--triangles N` sets a decimation target (0 disables it), not an engine budget guarantee. The output manifest reports the observed triangle count. `--geometry-only` skips texture diffusion, UV unwrap and baking for a faster shape check.
- `--solid-remesh N` (32–512, TRELLIS/Pixal only) opts into the upstream template's solid dual-contouring settings before decimation; the decoded shape remains the texture/normal/AO reference. Try 192 or 256 on a copy and compare silhouette, gaps and thin parts. The global solid reconstruction can close unwanted cracks or double shells, but can also close intended openings, lose thin/detail geometry and change the silhouette. Higher grids cost more GPU/CPU memory and time. The default skips remeshing.
- `--map-size` sets the common base-color and metallic/roughness atlas dimension (square; multiples of 256). `--normal-size` and `--ao-size` opt into extra geometry-derived bakes, which are disabled in both profiles. AO must match the main atlas dimension for packed glTF ORM (R=ambient occlusion, G=roughness, B=metallic). The tangent-space normal map is separate (OpenGL/+Y), in `normalTexture`. Base color is color data; ORM and normals are non-color data. The generated maps are not guaranteed physically measured, free of baked lighting, or suitable for layering as-is. Don't assume emission, transparency or ambient occlusion unless the asset and graph actually supply it.
- The CLI sets each active bundled sampler to the same fixed seed (42 unless overridden); it records the graph and input SHA-256s. Fixed seeds are not a promise of byte-identical GLBs across GPUs, backend builds or preprocessing implementations. Compare runs on the same hardware/software with the same input bytes and record cache state. If a 12 GiB card fails on a dense asset, try `quick`, `--geometry-only`, fewer triangles or a smaller atlas before increasing the timeout; a larger timeout does not fix OOM.

## Result provenance and troubleshooting

Each invocation gets `OUT_DIR/<name>-<uuid>/`. It uploads under `asset-3d/<name>-<uuid>/` in ComfyUI's input directory and sets the save prefix `asset-3d/<name>-<uuid>/mesh` in the output directory. It writes `workflow-api.json` before POSTing `/prompt`. It polls only `/history/<returned prompt_id>` and reads the selected save node's `outputs[save_node]["3d"]` entries, requiring `type=output`, the exact run subfolder and a GLB name generated from the run prefix. It downloads those exact entries via `/view` and verifies the GLB 2.0 container, triangle mesh, and expected embedded material maps. It does not scan the server's output tree or pick the newest file. A valid GLB is not a guarantee of decent geometry or materials.

On success, stdout is JSON with `artifact` (the first validated GLB), `artifacts` (all confirmed GLBs), and paths to `manifest.json`, `workflow-api.json` and `history.json`. The manifest records uploaded inputs, settings, model filenames, checksums, queue identity and timings. `timings.server.queue_s` and `timings.server.execution_s` are separate when server history contains their millisecond timestamps. `timings.poll_s` includes both queue and execution and the polling interval; `download_and_verify_s` and `total_s` are client-side wall times. For an accepted run that later fails, stderr names the prompt ID and manifest; terminal history is retained when fetched. HTTP errors include validation details when available. The default 900-second client wait is bounded by `--timeout`; expiry or interruption does **not** cancel a shared server's queue. Check the exact ID before submitting another run. Uploaded inputs and generated outputs remain in the server's own directories; remove them through your normal data-retention process.

### Your own native API graph

The three JSONs in `workflows/` are ComfyUI **API** graphs (node IDs mapped to `class_type` and `inputs`), not UI canvas JSON. Use the linked upstream templates if you want a UI graph. To adapt a UI graph for this client, use ComfyUI's **Save (API Format)** option and choose a `SaveGLB` (UI label **Save 3D Model**) or `Save3DAdvanced` output that writes a GLB. `--save-node` is required if there is more than one supported save node. The runner keeps that node and its upstream dependencies only. Stale API graphs may need to be re-exported from the current ComfyUI build. No custom/partner nodes or remote API authentication are supported, even if you supply your own graph.

```sh
python3 skills/asset-3d/scripts/comfy_3d.py inspect --workflow local-mesh-api.json \
  --image-node 1=prop.png --set '24.target_face_count=25000' --save-node 30
python3 skills/asset-3d/scripts/comfy_3d.py run --workflow local-mesh-api.json \
  --image-node 1=prop.png --set '24.target_face_count=25000' --seed 42 --save-node 30 --out-dir runs
```

Use node IDs from your graph. `--set NODE.FIELD=JSON` accepts numbers, quoted JSON strings, booleans and link arrays (e.g. `--set '4.images=["1",0]'`). `--image-node NODE=PATH` uploads into a native `LoadImage`; without it, the selected node's existing image name must be available to that server. With a generic graph, `--seed` overwrites literal `seed`/`noise_seed` inputs; otherwise original values remain. The per-run save prefix is managed by the client. A graph that writes OBJ/STL instead of GLB fails artifact verification even if ComfyUI reports successful execution.

## Sources and licensing

- Adapted from Comfy Org's [Pixal3D/TRELLIS.2 workflow](https://github.com/Comfy-Org/workflow_templates/blob/e0f557447323530e50be99fc3b2208a275d9ae78/templates/3d_pixal3d_trellis2_image_to_model.json) and [Hunyuan3D multiview workflow](https://github.com/Comfy-Org/workflow_templates/blob/e7cd011d4ded3411c2f481200544f0be6fdc962e/templates/3d_hunyuan3d_multiview_to_model.json). See the official [TRELLIS.2](https://docs.comfy.org/tutorials/3d/trellis2), [Pixal3D](https://docs.comfy.org/tutorials/3d/pixal3d), [Hunyuan 2.x](https://docs.comfy.org/tutorials/3d/hunyuan3D-2) and [HTTP API](https://docs.comfy.org/development/comfyui-server/comms_routes) guides.
- No weights, binaries or reference images are bundled. Review the license and notices of the exact model files and any input asset before production use or redistribution. [TRELLIS.2](https://github.com/microsoft/TRELLIS.2/blob/main/LICENSE) and [Pixal3D](https://huggingface.co/TencentARC/Pixal3D) are MIT at the project/model-card level; [Pixal3D's NOTICE](https://github.com/TencentARC/Pixal3D/blob/master/NOTICE) and [DINOv3's own license](https://github.com/facebookresearch/dinov3/blob/main/LICENSE.md) still matter. Check the [BiRefNet](https://huggingface.co/Comfy-Org/BiRefNet) and [MoGe](https://huggingface.co/Comfy-Org/MoGe) repositories if used. Hunyuan3D-2mv uses [Tencent's community license](https://huggingface.co/tencent/Hunyuan3D-2mv/blob/main/LICENSE), not MIT; check geography, commercial and redistribution terms. The workflow license is not a grant to use a model, input image or third-party design.

### Upstream workflow MIT notice

```text
MIT License

Copyright (c) 2023-present Comfy Org

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
