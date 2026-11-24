# Williams in a 3D workflow

**Primary source:** Richard Williams, *The Animator’s Survival Kit*. References below are to the book's **printed** page numbers, checked against the printed numbers and chapter headings of the consulted scan. PDF viewer numbers are not interchangeable with them; the offset changes within the file. Pagination may differ in other editions. The instructions below are original 3D applications, not transcriptions or copied diagrams.

| Decision | Printed pages | What to do in 3D |
|---|---:|---|
| What happens when, and how fast it travels between beats | 35–39 | Mark impact, departure, hold and arrival frames on a beat sheet. Keep them fixed for a comparison pass; change spacing around them. Compare per-frame displacements or projected screen spacing, not just curve shape. |
| Story keys, extremes, and breakdowns | 48–49, 57–59, 61–65 | Pose the story first. Add extremes such as heel contact and anticipation; choose the path and character of the transition with a breakdown. A DCC keyframe can hold any of these roles; a story key is not every keyed channel. |
| Test while changes are cheap | 68–70 | Capture timed tests with frame/clip labels. Compare them from the final camera, then frame-step transitions in another view. Do not wait for lighting or finalized textures. |
| Arcs and bad inbetweens | 88–92 | Track positions of the dominant wrist, eyes or head, toe and prop tip, preferably also through the shot camera. Remove accidental kinks or detours. Retain purposeful straight paths and sharp mechanical actions. |
| Weight through support and movement | 107–111, 136–138, 146–147, 256–259 | Block contact, down/load, passing and up/push; mark when hips transfer over the support leg. Preserve the difference between first touch and taking weight. Use cost of preparation, whole-body pressure and recovery to contrast a heavy object with a light one. |
| Breakdowns, overlap, readability | 218–224, 251 | Decide which part leads an action and which lags. Choose screen-space silhouettes and stagger the layers. Don't add a fanciful breakdown where direct action reads better. |
| Anticipation and accents | 273–275, 305–307, 310–314 | Make intention legible before the main action (sometimes via a small glance or shift). Mark the phrase or physical accent; don't spread it into uniform activity. Preview dialogue without audio as well as with sync. |
| Acting and attention | 320–325 | Reveal a change of thought where it can be seen; give it a separate beat if a broad move masks it. Break accidental symmetry, time eyes and head deliberately, and keep purposeful moments of symmetry for emphasis. |

## Practical pass order

1. **Observe and plan.** Set the shot camera or one real gameplay camera first; put a crude rig, stage and prop there. Observe reference with known usage rights, prioritize what the audience must read, and thumbnail several ideas in silhouette. Note physical contacts, shot or gameplay timing, and which body mass initiates the action. Draw up a short beat sheet with frame number, intent, support, and accent.
2. **Block sparse stepped poses.** Pitch two clear alternatives for the most important key when useful. Test without audio or effects, then with editorial/audio. Add the few necessary contacts, directional extremes and transitional breakdowns. If a pose is opaque, adjust line of action, silhouette, framing or pose itself; don't polish tangents trying to rescue the meaning.
3. **Give adjacent beats different spacing.** Use a relatively tight hold before a fast accent, a shallow settle after a hit, or a measured approach with a release. These are options, not presets. Check trajectories in world space and on camera; a smooth 3D curve can collapse or make a tangent with scenery on screen. Use a held pose or residual motion appropriate to intent, never random noise to keep a hold alive.
4. **Build supported motion.** Follow where mass travels from, to, and over. In locomotion, block a few progressing steps to see the weight and gait before extracting an in-place cycle (p. 111). Inspect ground engagement at heel first touch, the loading pose over the stance leg, toe-off and swing clearances. For grabs and lifts, animate a true attach/release beat and show the load in torso and hips, not just in fingers.
5. **Layer the rest.** Revisit the breakdowns for counter-rotation and overlap, then lips/eyes, cloth or secondary mechanisms. Rerun the playblast at delivery speed; a secondary shouldn't obscure the primary accent. Compare old and new over the same frame range and camera rather than trusting memory.

## Example: the heavy-case discovery

At 24 fps, start with the courier relaxed (f1), looking toward the handle (f8), making hand contact (f13), loading legs with the case still down (f17), failing to lift at first (f22), re-bracing (f28), clearing the floor (f34), and settling the load against the torso (f48). These are original starting points, not canonical timings. Use one hand/prop constraint while held and put the change of thought before or after the hardest exertion so it's readable. Try one spacing with near-still effort until f32 then quick clearance; compare another with motion starting earlier but nearly returning to ground before f34. Keep f34 fixed and choose by the apparent strain and clarity of support. Frame-step to inspect grip and floor clearance, then watch at normal speed to judge the acting.

## Diagnose by the observed failure

| Symptom | Inspect first | Change and recheck |
|---|---|---|
| Even but lifeless | Compare accents and screen travel frame by frame; check simultaneous changes on multiple channels. | Keep useful keys, redesign the strongest breakdown and vary spacing. Recheck with no secondary motion. |
| Weightless footfall | Compare contact vs. weight reception, pelvis trajectory, push-off and support. | Constrain the correct ground marker through true plant, then rework pelvis settle and toe pivot. Recheck with the full body visible. |
| Busy and unreadable | Watch in silhouette at the actual camera size; freeze the intended storytelling frame. | Separate dominant shapes, remove competing motion, move the thought change to visible frames. |
| Stiff hands/head, snaking elbows | Compare wrist/elbow paths and poles in world and camera views. | Move the passing pose or IK pole; stagger wrists and fingers only where it supports the beat. |
| Cycle looks assembled | Watch three repeats and blend into and out of the loop. | Match pose and incoming/outgoing velocity through the seam, preserve contacts through the blend, and layer any intentionally independent torso/head variation separately. |
