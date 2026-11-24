---
name: asset-3d
description: Create, reconstruct, clean up, optimize or validate 3D assets for games, web, cinematics and visualization. Use for text/image-to-3D, single or multiview references, local ComfyUI with TRELLIS.2, Pixal3D or Hunyuan3D and Blender, procedural hard-surface and low-poly modeling, detailed PBR assets, photogrammetry, Meshy/Tripo/Rodin, retopology, baking, LOD or GLB/FBX delivery. Para criar, reconstruir, refinar e exportar modelos 3D. For motion and clip authoring, use animation-3d.
compatibility: Shell-capable Agent Skills harness. Static tools require Blender 4.5+; local AI requires Python 3.9+, a running ComfyUI instance, and installed model weights. The workflow also supports other authorized tools and manual production.
---

# 3D asset production

A plausible front render is not evidence of a good asset. Deliver a model that satisfies the brief from all important views and survives import and real use. The agent directs, measures and iterates; a Blender connection does not turn it into a sculptor. Match the user's language.

## 1. Establish the acceptance contract

Read the project's existing assets and import conventions first. Record the subject, visual anchors, target camera/role, physical scale and pivot, runtime/format, triangle/material/texture budgets, and whether it must deform, collide, tile, or have LODs. Keep a distinction between concept, source and runtime budgets. If a material tradeoff cannot be inferred (e.g. a rig-ready hero vs a background prop), ask once; otherwise state assumptions and start. Never silently upload references or spend credits.

## 2. Pick the route that controls the hardest constraint

| Input and goal | Start here | Reject or switch when |
|---|---|---|
| Exact hard-surface, stylized low-poly props, modular kits | Procedural/hand-authored Blender from dimensions and silhouette guides; use scripts for repeatable forms | Shapes need freeform sculpting; build a blockout first, then sculpt or reconstruct |
| Detailed or organic design from one image, local | Prepare a clean reference, then A/B TRELLIS.2 and Pixal3D in ComfyUI; use Blender for edits and delivery | Ambiguous rear, fused appendages, or fake lighting demand a better input, multiview, or authored geometry |
| Same subject in several consistent views | Actual multiview reconstruction: Pixal3D multi-view for an approved sheet or Hunyuan3D 2mv for geometry from named views | Views disagree; fix them before generation. Do not stack views for a single-image node |
| A real object to reproduce faithfully | Licensed scan or overlapping calibrated photos → photogrammetry → clean/retopo/bake | Transparent, shiny, moving or occluded parts need a capture change or authored replacement |
| Exact topology, humanoid/creature hero, facial animation | Retopologize/rebuild from a generation or sculpt; licensed base mesh if available | Automated decimation or a successful rig call does not prove good deformation |
| Local model unavailable, provider explicitly authorized | Compare existing licensed assets or an official Meshy, Tripo or Rodin tool/API; import the result into the same Blender gates | Plan/export terms, data permissions, credit costs or quality fail the brief |

If starting from text, generate or sketch a controlled 2D concept first unless precise procedural geometry or an explicit text-to-3D evaluation makes more sense. For prompt refinement, reference preparation, route details and production steps, read [production.md](references/production.md). For local installs, workflows, preflight, exact API commands and troubleshooting, read [comfyui.md](references/comfyui.md).

## 3. Produce candidates, then spend time on the winner

1. Write named invariants (dimensions, silhouette landmarks, asymmetry, readable colors, joint clearance). Lock an approved reference and save original inputs, prompt, model/version, seed, workflow and license/provenance. Save new runs in separate directories.
2. Create the cheapest candidate that can answer the silhouette question. Review front, back, sides and 3/4 in flat clay before judging the textured render. When a silhouette or major part fails, fix inputs or route first; don't spend on 4K or try to hide it with paint. A face in a texture is not facial geometry.
3. Change one variable per iteration. For low poly, preserve the contour and hard edges with intentional topology and face normals; static collapse is a candidate, not an approval. For detailed assets, keep the high source and bake normal/AO/detail to a purpose-built low mesh. Use consistent texel density, matched tangents, a sane cage and correct color spaces. For skinning, prioritize joint/facial loop layout and extreme poses over absolute face count.
4. Inspect the actual deliverable, not only the imported source. A failed numerical gate blocks delivery; a passed gate is not a visual or deformation verdict. Compare the cleaned and original renders at target screen sizes. Read the images; don't assume that writing a screenshot equals seeing the asset.

For local closed props with cracks or chaotic triangles after decimation, A/B a quick `--solid-remesh 192` before raising resolution. Keep the no-remesh control; inspect whether the remesh erased intentional openings or thin parts.

## 4. Verify and hand off

Use [Blender QA and delivery](references/blender.md) for exact commands. The offline Blender helper evaluates mesh, runs explicit budgets and edge checks, renders fixed views and prepares a *static* editable `.blend` plus GLB. Do not use it to simplify or flatten rigs. For animation, use `animation-3d` with the approved deformable mesh, rest pose, metre scale, forward axis, named socket/bone requirements and constraints.

Open the exported asset in the target engine/viewer; verify orientation, pivot, scale, shading, textures, collision and clip/rig behavior as applicable. Reimport in a clean Blender scene if no target is available and mark the engine gate unverified; a structural validator is not an engine substitute. Deliver immutable input/raw generation, editable source, runtime files, multi-view evidence, metrics and an explicit defects/rights/import status. Keep revisions, compute cost, and manual cleanup time distinguishable. See [benchmark.md](references/benchmark.md) for a controlled test and observed limits.
