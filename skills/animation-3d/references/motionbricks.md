# MotionBricks: evaluate targeted inbetweening, not automatic animation delivery

Use [NVIDIA's official repository](https://github.com/NVlabs/motionbricks), [Runtime API](https://github.com/NVlabs/motionbricks/blob/main/docs/runtime_api.md), [guided tutorial](https://github.com/NVlabs/motionbricks/blob/main/docs/guided_tutorial.md), and [paper](https://arxiv.org/abs/2604.24833) for this tool. This is a motion model with a runtime and demos, not a Blender add-on, text prompt-to-animation service, general retargeter, or replacement for Williams' performance choices.

## Contract and caveats

- At **30 Hz**, a generation takes the **four latest context poses** and **one to four target poses**. One target specifies a stopping pose; multiple target poses inform arriving motion. The root module predicts path and duration; other modules predict and decode motion. It can choose transition length; the documented raw 24–64 samples become 18–58 valid samples after boundary removal. This is not arbitrary precision for a shot frame. The API allows constraining token counts, which sets a discrete number of samples, not arbitrary artist-authored spacing. Convert by time when working at 24, 25 or 60 fps; preserve important frame commitments after retiming.
- **SOMA human:** local joint translations and XYZW quaternions, root first, model Y up with XZ ground. The model uses the documented 30 SOMA joints and proportions; it does not generate arbitrary finger/facial animation. **Unitree G1:** 36 joint coordinates (XYZ, XYZW and 29 joint angles), model Z up and +X forward; different pose layout. Runtime space is configurable. Neither is a general input for random production skeletons. Retarget SOMA to a different character and fix contacts after retargeting.
- The NVIDIA GPU runtime uses Python, Warp and TensorRT, with Newton in the examples. Upstream reports Windows/Linux x86-64 demos tested with an RTX 4090; an available CUDA device or enough nominal VRAM does not guarantee local TensorRT compatibility. First launch builds a plan and caches it by configuration; time it separately from warm generation. Precision can change outputs. If chaining, record the poses actually played **after** corrections and use the last four 30 Hz samples for the next context, not unplayed generated frames.
- Predicted heel/toe contacts are confidences, not plant guarantees. Smart Primitives arrange authored target poses around interactions; SOMA target IK pins can help with precise placement but don't establish load, floor or collision correctness. Author the intention, anticipation, contacts, recovery and important breakdowns yourself; reject generations that undermine them.

## Local experiment

Use a separate workspace and pinned upstream revision; no dependency, model, third-party binary, or vendor clip ships with this skill. Setup downloads from upstream and dependency registries, so review licenses/disk use and keep ordinary project work offline. Start with the documented examples before building a custom integration. From the official clone root after installing [Git LFS](https://git-lfs.com/) and [uv](https://docs.astral.sh/uv/getting-started/installation/):

```sh
git lfs pull
uv sync
uv run python -m app.inbetweener_demo
# Or smoke-test without a viewer; these examples load upstream evaluation clips.
uv run python docs/examples/generate_once.py
uv run python docs/examples/locomotion_loop.py --model unitree_g1
```

The apps use the supplied ONNX models; the separate SafeTensors checkpoints are for workflows such as re-export or alternative runtime builds. See the [example source and model settings](https://github.com/NVlabs/motionbricks/tree/main/docs/examples) rather than assuming a generic BVH exporter or custom-rig `--prompt` CLI. Use the Runtime API `model_to_runtime` conversion, feed authorized poses, sample outputs by time, and bake evaluated data onto the actual target rig before normal production QA. Use artist-defined placements and transition reference when selecting targets.

## Licensing gate

- **Code** uses the upstream [Apache 2.0 license](https://github.com/NVlabs/motionbricks/blob/main/LICENSE); documentation/media have their own terms. The **ONNX models and checkpoint weights** use the separate [NVIDIA Open Model Agreement](https://www.nvidia.com/en-us/agreements/enterprise-software/nvidia-open-model-agreement/). Check the terms of the specific pinned release, model, dependencies and assets; code or model licenses don't blanket-cover source motions or rig assets.
- The listed SOMA BVH and G1 CSV **sample clips** are covered by the [NVIDIA Sample Data Evaluation License](https://github.com/NVlabs/motionbricks/blob/main/assets/motions/LICENSE.txt), limited to internal evaluation/testing of NVIDIA technologies and restricting distribution of the clips and their derivatives. See the [sample-data notice](https://github.com/NVlabs/motionbricks/blob/main/assets/motions/README.md) for file coverage. Don't ship, publish or treat derivatives of those clips as a library. Use original or properly licensed poses/capture for anything intended to leave the approved evaluation context; when provenance is ambiguous, stop the distribution, not the ability to use manual animation.

## Production acceptance

Compare one narrowly defined transition with an animator-authored baseline using the same character, target frames, contacts and camera, plus an imported runtime build if relevant. Record revision, model/precision, GPU and driver, cold plan time, warm p50/p95 generation time and trial count, final frame counts, target error, worst planted drift after retarget, root heading/path, cleanup minutes, visual outcome at speed and provenance. Keep export/retarget/physics/viewer time distinct from inference time. Use [Blender QA](qa.md) with artist-confirmed marker windows, not inferred contacts as ground truth. If timing, acting, similarity to reference, stability in play, licensing or total artist time loses to hand-key or properly licensed mocap, ship the manual/mocap clip. A successfully launched demo is not a production proof.
