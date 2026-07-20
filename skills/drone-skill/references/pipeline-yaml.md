# Drone Pipeline YAML Reference (`.drone.yml`)

The pipeline is defined in a `.drone.yml` file at the repository root. This
reference covers the **Docker** pipeline type (the default and most common). A
single file may hold multiple pipeline documents separated by `---`.

## Table of contents

- [Pipeline object](#pipeline-object) — `kind` / `type` / `name`
- [Steps](#steps)
- [Environment variables](#environment-variables)
- [Referencing secrets (`from_secret`)](#referencing-secrets-from_secret)
- [Services](#services)
- [Workspace](#workspace)
- [Cloning](#cloning)
- [Conditions (`when`)](#conditions-when) — step-level
- [Trigger](#trigger) — pipeline-level
- [Platform](#platform)
- [Node](#node)
- [Parallelism (`depends_on`)](#parallelism-depends_on)
- [Pipeline dependencies](#pipeline-dependencies)
- [Matrix builds](#matrix-builds)

---

## Pipeline object

Every document is a resource with three required keys: `kind` declares it a
pipeline, `type` selects the runtime (`docker`), `name` is unique within the file.

**Root keys:** `kind`, `type`, `name`, `platform`, `workspace`, `clone`, `steps`,
`services`, `volumes`, `node`, `trigger`, `depends_on`, `environment`,
`image_pull_secrets`

```yaml
kind: pipeline
type: docker
name: default

steps:
- name: build
  image: golang
  commands:
  - go build
  - go test
```

---

## Steps

A step runs a list of shell commands inside a Docker image, in the repository
root. The workspace is shared across steps, so files persist between them.
Commands are assembled into a script run with `set -e` and `set -x`, so the step
fails on the first command that returns a non-zero exit code.

**Step keys:**

| Key | Meaning |
|-----|---------|
| `name` | unique step identifier |
| `image` | Docker image the commands run in |
| `commands` | list of shell commands (overrides the image entrypoint) |
| `environment` | step-scoped environment variables |
| `settings` | configuration passed to a plugin (see `concepts.md`) |
| `pull` | image pull policy: `always`, `never`, `if-not-exists` |
| `detach` | run in the background; a detached step cannot fail the pipeline |
| `privileged` | escalated privileges (trusted repositories only) |
| `failure` | failure handling, e.g. `ignore` |
| `when` | conditionally run the step (see [Conditions](#conditions-when)) |
| `depends_on` | steps that must finish first (see [Parallelism](#parallelism-depends_on)) |

```yaml
kind: pipeline
type: docker
name: default

steps:
- name: backend
  image: golang
  environment:
    GOOS: linux
    GOARCH: amd64
  commands:
  - go build
  - go test

- name: frontend
  image: node
  commands:
  - npm install
  - npm test

- name: notify
  image: plugins/slack
  settings:
    webhook: https://hooks.slack.com/services/...
  when:
    status:
    - failure
    - success
```

---

## Environment variables

Scope variables to one step with a step `environment` block, or to the whole
pipeline with a root-level `environment` block. This section takes literal
key/value pairs only — it **cannot** expand variables or evaluate shell
expressions. Build dynamic values inside `commands` instead.

```yaml
# Step-level
steps:
- name: build
  image: golang
  environment:
    GOOS: linux
    GOARCH: amd64
  commands:
  - go build
```

```yaml
# Pipeline-level (applies to every step)
environment:
  GOOS: linux
  GOARCH: amd64

steps:
- name: build
  image: golang
  commands:
  - go build
```

---

## Referencing secrets (`from_secret`)

Pull a named secret (stored on the server, see `cli-reference.md`) into a step at
runtime with `from_secret`. Works for environment variables and plugin settings.
Never hard-code credentials in YAML. When echoed, secret values are masked.

```yaml
# As environment variables
steps:
- name: build
  image: docker
  commands:
  - docker login -u $USERNAME -p $PASSWORD
  - docker build -t hello-world .
  environment:
    USERNAME:
      from_secret: docker_username
    PASSWORD:
      from_secret: docker_password
```

```yaml
# As plugin settings
steps:
- name: notify
  image: plugins/slack
  settings:
    webhook:
      from_secret: slack_webhook
```

---

## Services

Detached "sidecar" containers started alongside the pipeline — typically a
database or cache your tests need. A service is reachable at a hostname equal to
its `name`. Notes/gotchas: the service exit code is ignored (it cannot fail the
pipeline); you **cannot** reach it via `localhost`/`127.0.0.1`; it may need a few
seconds before it accepts connections, so wait for it.

```yaml
kind: pipeline
type: docker
name: default

steps:
- name: ping
  image: redis
  commands:
  - redis-cli -h cache ping     # host = the service name

services:
- name: cache
  image: redis
```

```yaml
# Service with config + a readiness wait
kind: pipeline
type: docker
name: default

steps:
- name: test
  image: mysql:5.7
  commands:
  - while ! mysqladmin ping -h mysql-server -u drone -pdrone --silent; do sleep 1; done
  - echo "database ready"

services:
- name: mysql-server
  image: mysql:5.7
  environment:
    MYSQL_ALLOW_EMPTY_PASSWORD: yes
    MYSQL_DATABASE: drone_db
    MYSQL_USER: drone
    MYSQL_PASSWORD: drone
```

---

## Workspace

Drone creates an ephemeral volume — the workspace — clones your repo into it, and
uses it as the working directory for every step. It is created at pipeline start
and destroyed at completion. Default path `/drone/src`.

```yaml
kind: pipeline
type: docker
name: default

workspace:
  path: /drone/src

steps:
- name: build
  image: golang:latest
  commands:
  - go build
```

---

## Cloning

Drone clones the repository automatically before the first step. The `clone`
section customizes that.

- `disable` — turn off automatic cloning (do it yourself)
- `depth` — shallow-clone depth (git `--depth`)
- `retries` — retry count for failing git commands

```yaml
clone:
  depth: 50
```

```yaml
# Disable auto-clone and clone manually
kind: pipeline
type: docker
name: default

clone:
  disable: true

steps:
- name: clone
  image: alpine/git
  commands:
  - git clone https://github.com/octocat/hello-world.git .
  - git checkout $DRONE_COMMIT
```

---

## Conditions (`when`)

`when` limits whether a single **step** runs. Combined keys are AND-ed (all must
match). Matching uses **glob** patterns, not regular expressions. Each key takes
either a plain list or `include` / `exclude` sub-keys.

**Keys:** `branch`, `event`, `ref`, `repo`, `instance`, `status`, `target`,
`cron`, `paths`

- `event` — `push`, `pull_request`, `tag`, `promote`, `rollback`, `cron`
- `status` — `success`, `failure` (by default a step runs only on success of prior steps; use this to run on failure/always)
- `target` — deployment target, for `promote` / `rollback` events
- `cron` — named cron job, paired with `event: cron`
- `branch` — cannot be combined with tag events

```yaml
when:
  branch:
  - master
  - feature/*
  event:
  - push
  - pull_request
```

```yaml
# include / exclude form
when:
  branch:
    include:
    - master
    - feature/*
  event:
    exclude:
    - pull_request
```

```yaml
# run only when a prior step failed (e.g. a notifier)
when:
  status:
  - failure
```

---

## Trigger

`trigger` limits whether the **entire pipeline** runs in response to a webhook.
Same condition keys and glob matching as `when`; combined keys are AND-ed.

**Keys:** `branch`, `event`, `ref`, `repo`, `status`, `target`, `cron`, `action`,
`instance` — each supporting `include` / `exclude`.

```yaml
kind: pipeline
type: docker
name: default

steps:
- name: build
  image: golang
  commands:
  - go build

trigger:
  branch:
  - master
  event:
  - push
```

```yaml
trigger:
  branch:
    exclude:
    - master
```

---

## Platform

Sets the target OS/architecture, routing the pipeline to a matching runner.
Defaults to `linux`/`amd64`. Windows pipelines need a `version` and are
self-hosted only.

- `os` — `linux`, `windows`
- `arch` — `amd64`, `arm64`, `arm`
- `version` — Windows only (e.g. `1809`, `1903`)

```yaml
platform:
  os: linux
  arch: arm64
```

---

## Node

Routes the pipeline to runners advertising matching labels (key/value). The
pipeline schedules only onto a runner whose labels satisfy every `node` entry.

```yaml
node:
  region: east
  instance: gpu
```

---

## Parallelism (`depends_on`)

Steps run sequentially by default. Add `depends_on` to a step to build a directed
acyclic graph: steps that share no dependency run in parallel, and a step waits
for every step it lists. **Once you use `depends_on`, configure it on all steps**
so the full graph is defined. The scheduler auto-corrects the graph for skipped
(conditional) steps.

```yaml
kind: pipeline
type: docker
name: default

steps:
- name: backend
  image: golang
  commands:
  - go build

- name: frontend
  image: node
  commands:
  - npm test

- name: notify
  image: plugins/slack
  settings:
    webhook:
      from_secret: slack_webhook
  depends_on:
  - backend
  - frontend
```

`backend` and `frontend` run concurrently (fan-out); `notify` runs after both
finish (fan-in).

---

## Pipeline dependencies

A whole pipeline can depend on other pipelines by name, so multiple pipelines in
one file execute as a graph instead of all at once.

```yaml
kind: pipeline
type: docker
name: after

depends_on:
- backend
- frontend
```

---

## Matrix builds

A `matrix` expands one pipeline definition into several concurrent executions,
one per combination of the declared variables. Each variable is exposed as an
environment variable to the steps.

```yaml
kind: pipeline
type: docker
name: default

steps:
- name: build
  image: golang:${GO_VERSION}
  commands:
  - go build
  - go test

matrix:
  GO_VERSION:
  - 1.20
  - 1.21
  DATABASE:
  - mysql
  - postgres
```

> Note: this matrix example reflects standard Drone matrix syntax; the dedicated
> matrix page was unreachable when this reference was compiled. Confirm against
> your Drone version if behavior differs.
