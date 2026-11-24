# Runnable Blender QA and sample

These scripts use Blender 5.x's bundled Python and glTF tooling; no pip packages, external models or paid services. The original sample is a small skinned inspection robot that notices a marked pad, shifts its weight to its left shoe, taps with the right shoe, recoils and settles. The project saves the pose keys, stage, fixed camera, and frame-labelled beats. Its GLB is just the robot's skin and `TapRecovery` animation, not the stage or editable Blender controls.

## Reproduce the positive and negative cases

Run from the repository root, or set `scripts` to the installed skill's `scripts` directory. Work in a new output directory rather than inside the skill. The clean command writes `sample.blend`, `sample.glb` and PNG stills at frames 1, 7, 11, 15, 19 and 25 (720×540). The second command skips rendering.

```sh
scripts=skills/animation-3d/scripts
out=$(mktemp -d)

blender -b --factory-startup --python-exit-code 1 --python "$scripts/make_sample.py" -- \
  --out-dir "$out/clean" --variant clean
blender -b --factory-startup --python-exit-code 1 --python "$scripts/make_sample.py" -- \
  --out-dir "$out/slipping" --variant slipping --no-render

check_sample() {
  blender -b "$1/sample.blend" --python-exit-code 1 --python "$scripts/check_animation.py" -- \
    --rig SampleRig --root Root --frames 1 25 \
    --contact Toe.L 1 25 --contact Toe.R 1 6 --contact Toe.R 21 25 \
    --max-contact-drift 0.01 --max-root-distance 0.01 --loop --json "$1/qa.json"
}

check_sample "$out/clean"     # expect exit 0 and passed: true
check_sample "$out/slipping"  # expect exit 1 and a Toe.L contact_drift_m failure in qa.json
```

Both files show the same intended beat timing and close at frame 25 (one second between endpoints at 24 fps). The slipping variant shifts the left support foot horizontally and returns it; design target is **0.08 m at frame 13**. It should fail the plant gate, not the seam. A start/end-only check would miss it. The clean sample's left shoe stays between the amber brackets; the right shoe swings toward the teal bracket and has a short fixed tap at 15–16, another valid window if you want to check it. In Blender the `Toe.L` and `Toe.R` heads are near the bottom of the shoes, about 0.015 m above the stage surface (world `Z = 0`), rather than at the ankle. The marker height is not a collision or floor tolerance: the tool measures changes from the start of each fixed interval in **world space**.

Review frames 1 (ready), 7 (load beginning), 11 (outward travel), 15 (tap), 19 (recovery) and 25 (closure) against the stage marks; also watch in real time. Optional full-speed playblast with Blender and FFmpeg (exclude the duplicate terminal frame from the preview):

```sh
mkdir -p "$out/sequence"
blender -b "$out/clean/sample.blend" -o "$out/sequence/frame_####" -s 1 -e 24 -a
ffmpeg -framerate 24 -i "$out/sequence/frame_%04d.png" -pix_fmt yuv420p "$out/playblast.mp4"
```

For an engine smoke check, import `sample.glb` with animations enabled and create an instance in a test scene with floor and light. In Godot 4, find `TapRecovery` on `AnimationPlayer`, check approximately one second and advance playback to verify the skinned pose changes while `Root` stays still. Set looping in the consumer and observe multiple repeats. Check front-facing orientation, stage-relative scale, no unexpected rotations or missing skin/bones and readability during motion; a floor reference has to be added in the game scene because it isn't in the GLB. Record imported duration, clip/track names, model/rig counts, any actual measurements and whether the check was human playback or programmatic sampling. The rendered stills don't prove the import.

## Use the checker on a production clip

`check_animation.py` evaluates the active scene and view layer as opened, including enabled NLA, drivers and constraints. Isolate the intended action first; load that scene and pick the armature object name, not its data name. It does not select an action, modify rigs, or save the source. Choose marker bones bound to the geometry that actually touches; use `--contact-point tail` only if the applicable markers were authored at their tails. For a world-fixed floor mark, pass one or more inclusive windows `--contact BONE START END` (at least two frames each). Select separate windows for each full plant or isolated pivot. Do not include free swing or moving-surface contact unless the motion has been transformed into a static reference frame first.

| Option / report | How to interpret |
|---|---|
| `--frames START END`, `--samples-per-frame N` | Samples inclusive endpoints and uniformly spaced subframes (`N=1` by default). Turn up sampling for short overshoots; measurement cannot detect changes between sampled times. Avoid dependent simulations unless their caches are baked. |
| `--meters-per-unit` | Defaults to scene scale length for configured units, otherwise 1 m per Blender unit. Override only when the scene's world scale contract differs. Report includes the applied factor. |
| `--max-contact-drift` | Hard limit on maximum 3D offset of the sampled point from its first position in the window (2 cm default), not average or cumulative distance. Report includes worst frame, separate XY and vertical displacement magnitudes, and the world-space anchor in meters. Check absolute clearance/penetration separately. |
| `--root BONE` | Uses a named evaluated root; if omitted, uses the armature object transform. Reports world displacement, path length, peak consecutive step, orientation/scale difference and mean net speed. `--max-root-step` and `--max-root-distance` add optional hard limits; step depends on sampling rate. A root sidestep that returns to start has zero net distance, so inspect path and peak step too. |
| `--loop` | Compares endpoint transforms on all deform bones except the named root, or replace that set with repeatable `--loop-bone`. In-place additionally gates the root's world translation and rotation; `--allow-root-cycle` instead removes root translation/rotation before comparing bones and still checks root scale drift. Root limits remain independently active. Defaults: 1 cm position, 2 degrees orientational difference, 0.01 max scale change on any axis. Checks only sampled endpoint closure, not seam velocity or smoothness. |
| `--json FILE` | Writes detailed JSON (parent directory must exist) with the exact limits and failed gates; JSON is also printed. Always use the Blender CLI flag `--python-exit-code 1` **before** `--python` so a failed threshold fails the command. Log stderr for Blender/setup errors as well. |

For world-moving cycles, enable `--allow-root-cycle`, choose the correct root and verify measured travel and turning against the desired per-cycle stride; don't apply a stationary root net-distance limit to a traveling loop. For in-place locomotion, compose the actual gameplay displacement before measuring world-space foot drift. Explicitly separate numerical checks from camera timing, acting, deformations, clearance, seams in motion, and engine integration.

## Report comparable benchmark numbers

Keep generated artifacts outside version control. Record the Blender version, machine, renderer, frame count, GPU/CPU if relevant, and elapsed times for generation/baking, rendering and checking separately (use `--no-render` for a bake-only measure). Compare fixture outputs with their expected clean/negative statuses and actual measured maximum drift/frame. Include frame paths for visual proof and the destination engine's version/clip test. Don't treat expected values or timings from a different system as measured results.

### Observed on the reference fixture

Blender 5.3.0 evaluated the authored scene at 24 fps (25 inclusive samples,
frames 1–25). The tested contact threshold was 0.01 m.

| Case | Worst planted-marker drift | Endpoint position and rotation delta | QA |
|---|---:|---:|---|
| Clean | 0.00000030 m | 0 m / 0° | Pass |
| Slipping | 0.08000003 m at frame 13, `Toe.L` | 0 m / 0° | Fail: contact drift |

Six Cycles stills were inspected for preparation, load, tap and recovery.
A real-time 24-frame, 24 fps preview was also rendered. Godot 4.7.2's runtime
glTF loader instantiated one skinned mesh and one skeleton from the clean GLB;
seeking `TapRecovery` from 0 to 0.4 s changed 13 bone transforms (clip duration:
1.0 s). That check did not certify collision, in-game transitions, or MotionBricks
performance. The fixture is a mechanical character, not a benchmark of organic
deformation or arbitrary retargeted motion.
