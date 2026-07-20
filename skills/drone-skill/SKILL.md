---
name: drone-skill
description: >-
  Work with Drone CI/CD — the open-source, container-native continuous
  integration and delivery platform at drone.io — and its `drone` command-line
  tool. Use this whenever the user mentions Drone pipelines, a `.drone.yml` file,
  `drone exec`, Drone builds, promotions, secrets, cron jobs, templates, runners,
  or a Drone server, or asks to set up / write / debug CI/CD "on Drone" — even if
  they don't say the word "skill." This includes authoring or fixing pipeline
  YAML, running pipelines locally, wiring up secrets and plugins, and driving the
  CLI to manage repos, builds, and schedules. IMPORTANT: this is Drone the CI/CD
  software, NOT physical flying drones — do not use this skill for UAVs,
  quadcopters, DJI, aerial photography, or flight controllers.
---

# Drone CI/CD

Drone is a container-native CI/CD platform. This skill helps you author pipelines
(`.drone.yml`) and operate a Drone server through the `drone` CLI.

## Mental model (read this first)

Two moving parts:

- **Server** — receives webhooks from your Git provider (GitHub, GitLab, Gitea,
  Bitbucket, …), stores config/secrets/builds, exposes the UI and REST API.
- **Runners** — daemons that poll the server and execute pipeline steps in
  containers.

Flow: push code → webhook → server reads the repo's `.drone.yml` → a runner runs
the steps in containers → status reports back.

Two kinds of work you'll do, covered below:

1. **Author a pipeline** — write/fix a `.drone.yml`.
2. **Operate via CLI** — trigger builds, manage secrets/crons/repos.

## Before running any CLI command: configuration

The `drone` CLI is a REST client. Every command except `drone exec` needs two
environment variables pointing at a server:

```
export DRONE_SERVER=https://drone.mycompany.com
export DRONE_TOKEN=<personal token from the UI: avatar → account settings>
```

If a command errors with an auth/connection failure, check these first. `drone
exec` is the exception — it runs a pipeline locally and needs neither.

Not sure the CLI is installed? `drone --version`. Install steps are in
`references/cli-reference.md`.

## Authoring a pipeline

A minimal, correct Docker pipeline — the shape to start from:

```yaml
kind: pipeline
type: docker
name: default

steps:
- name: build
  image: golang:1.21
  commands:
  - go build
  - go test
```

Notes that trip people up:

- `kind`, `type`, `name` are all required. `type: docker` is the common runtime.
- `commands` run as a shell script with `set -e` — the step fails on the first
  non-zero exit. They run in the repo root; the workspace is shared across steps.
- Steps run **sequentially** by default. Use `depends_on` to run them in parallel
  as a graph.
- Multiple pipelines go in one file separated by `---`.

Test it locally before committing — this is the fastest feedback loop and needs
no server:

```
drone exec .drone.yml
```

### Building a pipeline for a real request

Work up from the minimal skeleton, adding only what the request needs. Common
additions, each detailed with exact keys and examples in
`references/pipeline-yaml.md`:

| The user wants… | Reach for |
|-----------------|-----------|
| A database/cache for tests | `services:` (reachable by service name, not `localhost`) |
| A credential (registry, API token) | a named secret + `from_secret:` |
| Run a step only on some branches/events | step-level `when:` |
| Run the whole pipeline only sometimes | pipeline-level `trigger:` |
| Parallel steps / fan-in | `depends_on:` on each step |
| Publish/deploy/notify | a **plugin** (`image: plugins/...` + `settings:`) |
| A deploy gated on manual promotion | `event: promote` + `target:` |
| Scheduled runs | a cron job (self-hosted only) |
| Per-version test spread | `matrix:` |

Two rules worth stating up front because they cause silent breakage:

- **Secrets never go in the YAML as plain text.** Store them on the server
  (`drone secret add` / org secrets) and pull them in with `from_secret`. Encrypted
  inline secrets (`drone encrypt`) are the alternative. See the secrets section of
  `references/concepts.md`.
- **Services are reached by their `name` as a hostname**, and their startup is not
  awaited — have the step wait for readiness (e.g. poll the port) before using it.

Read `references/pipeline-yaml.md` before writing anything beyond the skeleton —
it has the authoritative keys for `when`/`trigger` conditions, `services`,
`clone`, `platform`, `depends_on`, and `matrix`, with a working example for each.

### Plugins vs commands

If the task is "publish a Docker image", "deploy to S3", "post to Slack", it's
almost certainly a **plugin**: set `image: plugins/<x>` and pass `settings:`, do
not hand-write the shell. Each `settings` value is exposed to the plugin as
`PLUGIN_<NAME>`. See the plugins section of `references/concepts.md`.

## Operating via the CLI

Once `DRONE_SERVER`/`DRONE_TOKEN` are set, the CLI manages the server. The most
common commands (full reference, flags, and privilege requirements in
`references/cli-reference.md`):

```
# Builds
drone build ls octocat/hello-world             # history (filter: --branch --event --status)
drone build info octocat/hello-world 42        # one build
drone build restart octocat/hello-world 42     # re-run (new build number)
drone build stop octocat/hello-world 42
drone build promote octocat/hello-world 42 production   # deploy build 42 to "production"

# Secrets (reference in YAML with from_secret)
drone secret add --name docker_password --data <value> octocat/hello-world
drone secret ls octocat/hello-world
drone orgsecret add acme shared_token <value>  # org-wide (admin)

# Repositories
drone repo ls
drone repo enable octocat/hello-world          # activate + create webhooks
drone repo update octocat/hello-world --trusted=true

# Cron (self-hosted only)
drone cron add octocat/hello-world nightly "0 0 0 * * *"   # 6 fields — see below
```

## Gotchas to check before you hand something over

These are the mistakes that pass a glance but fail at runtime:

1. **Cron expressions have six fields, and the first is _seconds_.** A copied
   5-field crontab line (`0 0 * * *`) is wrong on Drone. Use six fields or a
   predefined schedule (`@daily`, `@hourly`, …). Cron is UTC and disabled on Drone
   Cloud. Details in `references/concepts.md`.
2. **Secrets are hidden from pull requests by default.** That's a safety feature;
   only override it (`--allow-pull-request`) deliberately, and never for repos that
   accept PRs from untrusted forks.
3. **`when`/`trigger` use glob matching, not regex.** `feature/*`, not
   `feature/.*`.
4. **`depends_on` is all-or-nothing for ordering.** Once one step declares it, the
   graph is only correct if every step's ordering is expressed.
5. **`privileged` / host volumes need a trusted repo** (`drone repo update
   --trusted`) or `drone exec --trusted` locally.
6. **Signed configs must be re-signed after every edit** (`drone sign <repo>
   --save`) or the pipeline is blocked. Only YAML can be signed — not
   Starlark/Jsonnet.

## Reference files

Load the one that matches the task — don't guess syntax from memory:

- **`references/pipeline-yaml.md`** — the `.drone.yml` spec: every root and step
  key, `services`, `when`/`trigger` conditions, `from_secret`, `clone`,
  `workspace`, `platform`, `node`, `depends_on`, `matrix`. Read before writing
  non-trivial YAML.
- **`references/cli-reference.md`** — every `drone` subcommand with flags,
  arguments, examples, and required privileges. Read before constructing a CLI
  command you're unsure of.
- **`references/concepts.md`** — how the pieces fit: architecture, pipeline types,
  the secrets model, plugins, promotion/deployments, cron scheduling, templates,
  signatures, and the REST API.

When something isn't covered here, the authoritative docs are
<https://docs.drone.io/> and the CLI docs at <https://docs.drone.io/cli/install/>.
