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

All skills are knowledge, not code — they teach the agent accurate, up-to-date
syntax instead of guessing from memory. They have no runtime dependencies; running
what they suggest requires the relevant CLI (`drone`, `databricks`) in your
environment.

## Install

This repo is a Claude Code marketplace named `frigo-skills` that ships one plugin
(also `frigo-skills`) containing all the skills.

```
# 1. Add the marketplace (from GitHub once published)
/plugin marketplace add alanfrigo/frigo-skills

# 2. Install the plugin (brings every skill)
/plugin install frigo-skills@frigo-skills
```

Once installed, Claude auto-invokes whichever skill matches your task — ask about a
`.drone.yml` and it uses `drone-skill`; ask to set up the Databricks CLI on Azure
and it uses `azure-databricks`. Their descriptions are disambiguated so they don't
cross-trigger.

### Local development (before publishing)

Point Claude Code at the working copy without going through GitHub:

```
# Add this repo as a local marketplace
/plugin marketplace add ./
/plugin install frigo-skills@frigo-skills

# …or load it directly for a single session
claude --plugin-dir .
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
│   └── azure-databricks/
│       ├── SKILL.md
│       ├── references/       # cli.md, apps.md, bundles.md
│       └── evals/evals.json
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
