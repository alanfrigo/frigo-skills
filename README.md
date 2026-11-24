# frigo-skills

Alan Frigo's personal collection of [Claude Code](https://docs.claude.com/en/docs/claude-code)
[Agent Skills](https://docs.claude.com/en/docs/claude-code/skills), packaged as a
single installable **plugin** and served from a **marketplace** — so you can add
the marketplace once and pick up every skill, with new ones dropping in over time.

## Skills

| Skill | What it does | Triggers on |
|-------|--------------|-------------|
| **`drone-skill`** | Author and debug Drone CI/CD `.drone.yml` pipelines and drive the `drone` CLI. | `.drone.yml`, `drone exec`, Drone builds/secrets/crons/promotions. |
| **`azure-databricks`** | Work with Azure Databricks: the `databricks` CLI, Databricks Apps, and Declarative Automation Bundles (DAB). | `databricks` CLI, `.databrickscfg`, `databricks.yml`, Databricks Apps, `app.yaml`, `adb-*.azuredatabricks.net`. |
| **[`asset-3d`](skills/asset-3d/SKILL.md)** | Create and validate low-poly or detailed 3D assets. Local ComfyUI + Blender, procedural modeling, licensed sources, and authorized hosted backends. | Image/text-to-3D, TRELLIS.2, Pixal3D, Hunyuan3D, retopology, GLB/PBR/LOD. |
| **[`animation-3d`](skills/animation-3d/SKILL.md)** | Rig, choreograph, retarget and validate 3D animation using Richard Williams as the performance reference. | Keyframe animation, mocap, MotionBricks, feet/contact, clip loops, root motion. |

Each skill provides workflow knowledge; the 3D skills also ship runnable helpers.
The local asset route needs a running ComfyUI with model weights plus Blender.
Blender is sufficient for the offline reference scenes, export and QA. See the
[asset benchmark](skills/asset-3d/references/benchmark.md) and
[animation QA benchmark](skills/animation-3d/references/qa.md#observed-on-the-reference-fixture)
for reproducible commands and measured results.

## Install

This repo is a Claude Code marketplace named `frigo-skills` that ships one plugin
(also `frigo-skills`) containing all the skills.

```
# 1. Add the marketplace (from GitHub once published)
/plugin marketplace add alanfrigo/frigo-skills

# 2. Install the plugin (brings every skill)
/plugin install frigo-skills@frigo-skills
```

Once installed, Claude auto-invokes the matching skill, or you can invoke one
directly with `/frigo-skills:asset-3d` or `/frigo-skills:animation-3d`. Use the
full skill directories (not just `SKILL.md`) in other Agent Skills harnesses.

### Local development (before publishing)

Point Claude Code at the working copy without going through GitHub:

```
# Add this repo as a local marketplace
/plugin marketplace add ./
/plugin install frigo-skills@frigo-skills

# …or load it directly for a single session
claude --plugin-dir .
```

For Codex or another harness supported by the [Skills CLI](https://github.com/vercel-labs/skills),
run from the destination project and point at this checkout:

```sh
npx skills add /path/to/frigo-skills --skill asset-3d animation-3d -a codex
```

## Repository structure

```
frigo-skills/
├── .claude-plugin/
│   ├── plugin.json          # the frigo-skills plugin manifest
│   └── marketplace.json     # marketplace listing (one plugin, source ".")
├── skills/
│   ├── drone-skill/
│   │   ├── SKILL.md
│   │   ├── references/       # pipeline-yaml.md, cli-reference.md, concepts.md
│   │   └── evals/evals.json
│   ├── azure-databricks/
│   │   ├── SKILL.md
│   │   ├── references/       # cli.md, apps.md, bundles.md
│   │   └── evals/evals.json
│   ├── asset-3d/             # modeling, local workflow graphs and asset QA
│   └── animation-3d/         # animation workflow, sample rig and clip QA
├── README.md
└── LICENSE
```

Each skill reads its `SKILL.md` first, then loads a `references/*.md` file only when
the task needs it — keeping token usage low until the detail is actually required.

## Adding a new skill

Drop a new folder under `skills/`:

```
skills/<your-skill>/
├── SKILL.md          # YAML frontmatter: name + a pushy, disambiguated description
├── references/       # optional deep-dive docs, loaded on demand
├── scripts/           # optional executable helpers
└── evals/evals.json  # optional test cases
```

The plugin auto-discovers everything in `skills/`, so no manifest edit is needed to
register it — reinstall/update the plugin and the new skill is available. Keep the
folder name aligned with the `name:` in its `SKILL.md`.

## Contributing

Issues and pull requests welcome — command-syntax corrections, new examples, or new
skills. Reference material is compiled from official docs; when a tool changes,
cite the relevant doc page in your PR so it can be verified.

## Disclaimer & attribution

Unofficial, community-maintained skills. Not affiliated with or endorsed by
Harness/Drone, Microsoft, or Databricks. Command and configuration details derive
from the official documentation, which remains authoritative — always confirm
against the version of the tool you run.

## License

Released under the [MIT License](LICENSE). Drone and Databricks are trademarks of
their respective owners.
