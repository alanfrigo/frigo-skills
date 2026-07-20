# Drone CI/CD Concepts

Background on how Drone is put together and the features that shape how you write
pipelines and run the CLI. For exact YAML keys see `pipeline-yaml.md`; for exact
commands see `cli-reference.md`.

## Table of contents

- [Architecture](#architecture) — server, runners, pipelines
- [Pipeline types](#pipeline-types)
- [Secrets](#secrets)
- [Plugins](#plugins)
- [Promote (deployments)](#promote-deployments)
- [Cron](#cron)
- [Templates](#templates)
- [Signatures](#signatures)
- [API](#api)

---

## Architecture

Drone is a container-native CI/CD platform with two moving parts:

- **Server** — the control plane. It connects to your source control provider,
  receives webhooks, stores builds/secrets/config, and exposes the UI and REST
  API. Supported providers: GitHub, GitHub Enterprise, Gitea, Gitee, GitLab,
  Gogs, Bitbucket Cloud, Bitbucket Server.
- **Runner(s)** — standalone daemons that poll the server for pending pipelines
  and execute them. You install one or many, of one or more types.

A code change fires a webhook → the server matches the repo's `.drone.yml` → a
runner picks up the work → steps execute in containers → status reports back.

Server upgrades are done by replacing the Docker image (`docker pull
drone/drone:2`, then restart); database migrations run automatically and
backward compatibility is maintained across releases.

### Runner types

Docker (general purpose, the default), Exec, SSH, Digital Ocean, VM (Amazon,
Anka, Azure, Digital Ocean, Google drivers), and Macstadium (macOS).

The **Docker runner** executes each step in an ephemeral container. Great for
anything that builds/tests inside a stateless container. Not suited to OSes Docker
can't run (e.g. macOS → use a VM/Macstadium runner) or pipelines that need
persistent host state between runs.

Secret extensions available to runners: AWS Secrets, Vault, Kubernetes.

---

## Pipeline types

`type:` in the pipeline document selects the runtime. Variants: **Docker**,
**Kubernetes**, **Exec**, **SSH**, **Digital Ocean**, **MacStadium**. Not every
installation supports every type — check with your admin. This skill focuses on
Docker pipelines (the most common); other types share the same overall structure
but differ in step execution.

---

## Secrets

Store sensitive values (tokens, passwords, SSH keys) outside plain-text config.
Four kinds:

- **Per repository** — scoped to one repo. Push/admin access to manage. Manage via
  the repo settings UI or `drone secret …`.
- **Per organization** — shared across an org's repos. Admin access to manage.
  `drone orgsecret …`.
- **Encrypted** — an encrypted string embedded in the YAML (`drone encrypt`).
- **External** — pulled from Vault, Kubernetes, or AWS Secrets via an extension.

Reference a named secret in YAML with `from_secret` (see `pipeline-yaml.md`).

**Pull-request gotcha:** by default secrets are **not** exposed to pull requests,
which stops a malicious PR from printing them. Enabling "Allow Pull Requests"
(`--allow-pull-request`) overrides this and carries real risk — only do it
deliberately.

---

## Plugins

Plugins are Docker containers that perform a predefined task (publish an artifact,
deploy, send a notification) and are configured as a step via `settings`. You do
not write shell commands for a plugin — you set its parameters.

```yaml
steps:
- name: publish
  image: plugins/docker
  settings:
    username: kevinbacon
    password:
      from_secret: docker_password
    repo: foo/bar
    tags:
    - 1.0.0
    - 1.0
```

Key facts:

- The plugin automatically receives the mounted source code and runs from the
  repo root — no clone step needed.
- Each `settings` value becomes an env var prefixed `PLUGIN_`, uppercased. Above:
  `PLUGIN_USERNAME`, `PLUGIN_PASSWORD`, `PLUGIN_REPO`, and lists join with commas
  → `PLUGIN_TAGS=1.0.0,1.0`.
- Plugins ship as Docker images on public/private registries; browse the Plugin
  Registry or build your own.

---

## Promote (deployments)

Promotion re-runs a specific, already-built commit against a target environment,
identified by build number. Promoting creates a **new build** with event type
`promote` and target set to your environment name (freeform). Benefits: repeatable
deploys, an audit trail, separation of duties, and keeping developers out of the
server environment directly.

Three ways to wire it up:

```yaml
# 1. A pipeline that only runs on promotion to a target
trigger:
  event:
  - promote
  target:
  - production
```

```yaml
# 2. A step that only runs on promotion to a target
when:
  event:
  - promote
  target:
  - production
```

3. A separate, dedicated promotion pipeline document keyed on the `promote` event.

Trigger it from the CLI:

```
drone build promote octocat/hello-world 42 staging
drone build promote octocat/hello-world 42 production
```

Environment variables available in a promotion build:
`DRONE_BUILD_PARENT` (the parent build number) and `DRONE_DEPLOY_TO` (the target).

---

## Cron

Run a pipeline on a time schedule. **Self-hosted only — cron is disabled on Drone
Cloud.** Manage via the settings UI or `drone cron …`.

### The seconds gotcha (important)

Drone cron expressions have **six** space-separated fields, and the first is
**seconds**:

```
┌─ seconds (0-59)
│ ┌─ minutes (0-59)
│ │ ┌─ hours (0-23)
│ │ │ ┌─ day of month (1-31)
│ │ │ │ ┌─ month (1-12 or JAN-DEC)
│ │ │ │ │ ┌─ day of week (0-6 or SUN-SAT)
│ │ │ │ │ │
0 0 0 * * *
```

Most cron examples on the internet use **five** fields (no seconds). Copying a
5-field expression into Drone shifts every field and produces the wrong schedule.

Predefined schedules avoid the trap:

| Entry | Expression | When |
|-------|-----------|------|
| `@yearly` | `0 0 0 1 1 *` | Jan 1, midnight |
| `@monthly` | `0 0 0 1 * *` | 1st of month, midnight |
| `@weekly` | `0 0 0 * * 0` | Sunday, midnight |
| `@daily` | `0 0 0 * * *` | every day, midnight |
| `@hourly` | `0 0 * * * *` | top of every hour |

Other gotchas: schedules are evaluated in **UTC**, and the scheduler runs in
hourly batches — a job can fire up to an hour after its nominal time, and runs at
most once per hour.

In YAML, gate steps/pipelines on a named cron with `event: cron` + `cron: <name>`
(see `pipeline-yaml.md`).

---

## Templates

Organization-level, reusable pipeline configurations, so many similar repos don't
each maintain a full `.drone.yml`. A template is stored once per org and a repo
references it with per-project data. Engines: **Jsonnet**, **Starlark**, **YAML**,
plus a **Variables** mechanism for parameterization. Templates use Go templating
syntax. Manage via `drone template …`.

---

## Signatures

A signature verifies a YAML config hasn't been tampered with — valuable for public
repos where a malicious PR could rewrite the pipeline. Enable **Protected** mode in
repo settings to enforce it; unsigned/unauthorized changes block the pipeline
pending manual approval.

The signature is stored as its own resource inside the YAML:

```yaml
---
kind: signature
hmac: F10E2821BBBEA527EA02200352313BC059445190
```

The HMAC is computed with a 256-bit per-repository key that never leaves the
server. Generate/update it with `drone sign <repo/name> --save`. **Re-sign every
time you change the configuration**, or the pipeline is blocked. Only YAML can be
signed — not Starlark or Jsonnet.

---

## API

The server exposes a REST API. Authenticate with a bearer token (from your profile
in the UI):

```
Authorization: Bearer <token>
```

```bash
curl -X GET "http://localhost:8080/api/user" \
  -H "Authorization: Bearer <token>"
```

Endpoint categories mirror the CLI: builds, cron jobs, repositories, secrets,
templates, users. Official client libraries: `drone/drone-go`, `drone/drone-js`,
`drone/drone-node`; community libraries exist for Python, Dart, and Java.
