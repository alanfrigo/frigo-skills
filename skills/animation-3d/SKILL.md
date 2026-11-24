---
name: animation-3d
description: Create, repair, retarget, review, test, or export character, creature, mechanical, or prop animation for 3D games and cinematics. Use for Blender keyframes, blocking, skinning and rig controls, acting and timing, locomotion cycles, mocap cleanup, foot sliding, root motion, playblasts, skeletal GLB/FBX handoff, and experimental NVIDIA MotionBricks inbetweening. Treat Richard Williams' The Animator’s Survival Kit as the primary authority for performance decisions. For static models, textures, materials, and initial asset authoring, use asset-3d instead.
---

# 3D animation for games and cinematics

**Richard Williams, _The Animator’s Survival Kit_, governs performance choices.** His timing, spacing, phrasing, weight, and testing principles apply whether keys are authored, captured, or generated. Blender and engine docs govern software behavior, not acting. Do not let a spline, solver, or model decide which story beat matters.

## Work the shot or clip

1. **Set the brief.** Record the audience/camera, one sentence of intent, the dominant action, frame rate and range, target rig, units and facing, and the destination. For games, name the clip, specify in-place versus root motion, transition partners, and contact/event frames. For cinematics, fix the shot camera, cut, and any dialogue cue before polish. If missing details don't block work, use reversible defaults and state them. Keep source and deliverable separate.
2. **Choose the base.** Hand-key stylized acting, hero shots, or hard frame/pose constraints. Use properly licensed mocap for real performance and fast realistic coverage; retarget then edit. Use [MotionBricks](references/motionbricks.md) only when its rig, timing, hardware, and licensing fit an experiment. Keep the original source or capture untouched.
3. **Block what must read.** Start with the storytelling poses; add extremes such as contact and anticipation, then choose expressive breakdowns, rather than accepting the mathematical midpoint (Williams pp. 48–49, 57–59, 61–65). Use stepped playback to approve intent, silhouette and beat timing. Design the root and support transfer before embellishing. On the intended camera, decide what the viewer should notice first and where.
4. **Change spacing deliberately.** Spline only after the beats work. Review travel between frames, using motion paths for head, wrist, pelvis and toe. Shape ease, speed and holds without moving an approved impact; an arc is a choice, not a rule for a mechanical stop. Layer follow-through, eyes and extremities after the dominant motion reads (pp. 35–39, 88–92, 218–224, 320–325). Use character-specific effort and recovery, not identical ease on every channel.
5. **Lock contacts and test early.** Evaluate the actual pose, not just key values. At a held point check world-space drift; distinguish flat plant, heel rock, toe pivot and free swing. Play at speed from the shot/game camera, then inspect in an orthographic side or front view and frame-step contacts, fast arcs and transitions. Review several repeats for cycles and compare an earlier playblast after any large change (pp. 68–70).
6. **Deliver and verify.** Keep editable controls, actions and retarget data in source `.blend`; export a deliberately baked clip/rig with the target's axis and root convention. Test the imported animation, not only Blender playback. Record the actual artifacts, versions, tolerances and checks; mark anything you could not inspect. An attractive still or valid file header does not verify motion.

## Open the relevant reference

- [Williams in a 3D workflow](references/performance.md) — verified printed-page map, pose/timing procedure, and how to diagnose unreadable acting, weak weight, and poor spacing.
- [Rig, retarget and ship](references/production.md) — deformation poses, FK/IK handoff, mocap cleanup, root and loop conventions, game/cinematic export, and runtime review.
- [MotionBricks](references/motionbricks.md) — official runtime contract, evaluation trial, licensing boundaries, and criteria for adoption.
- [Runnable Blender QA and sample](references/qa.md) — generate editable `.blend`, animated `.glb` and rendered frames; test clean and slipping variants; configure a real clip's root/contacts/loop.

Use the [asset-3d skill](../asset-3d/SKILL.md) when mesh cleanup, pivot/scale, skin-ready topology, textures or materials are upstream dependencies. Return to this skill once the rig or animated deliverables are in scope.

## Starting prompts

- “Block a 48-frame shot at 24 fps: the courier notices the case is much heavier than expected. Give a frame-indexed beat sheet, two different spacings for the lift with the same frame of clearance, and a camera/readability check before spline.”
- “Repair `Walk_Fwd` on rig `Hero`: keep the root displacement and facing; measure `Toe.L` over frames 4–11 and `Toe.R` over 16–23. Fix the sliding on a copied action, compare at full speed, and test the imported engine loop and start/stop blends.”
- “Evaluate whether MotionBricks improves the stand-to-sit bridge on SOMA versus a manual pass. Keep the chair contact and performance beats fixed; report license status, cold and warm local time, post-retarget drift and manual cleanup time. Don't ship the demo's samples.”
