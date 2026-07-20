# Drone CLI Reference

Complete command reference for the `drone` command-line tool. The CLI is a REST
client for a Drone server — every command reads `DRONE_SERVER` and `DRONE_TOKEN`
from the environment (see [Install & configure](#install--configure)).

Repository arguments always use the `owner/name` form, e.g. `octocat/hello-world`.

## Table of contents

- [Install & configure](#install--configure)
- [Local pipeline execution](#local-pipeline-execution): `exec`, `jsonnet`, `sign`, `encrypt`
- [Builds](#builds): `build ls/info/last/restart/stop/promote/approve/decline`
- [Repositories](#repositories): `repo ls/info/enable/rm/update/repair/chown`
- [Repository secrets](#repository-secrets): `secret add/ls/info/update/rm`
- [Organization secrets](#organization-secrets): `orgsecret add/ls/info/update/rm`
- [Cron jobs](#cron-jobs): `cron add/ls/info/enable/disable/exec/rm`
- [Logs](#logs): `log view/purge`
- [Templates](#templates): `template add/ls/info/update/rm`
- [Users (admin)](#users-admin): `user ls/info/add/rm`

---

## Install & configure

### Install

**Linux (x64)**
```
curl -L https://github.com/harness/drone-cli/releases/latest/download/drone_linux_amd64.tar.gz | tar zx
sudo install -t /usr/local/bin drone
```
(arm64 and arm tarballs are on the same GitHub releases page.)

**macOS**
```
# curl
curl -L https://github.com/harness/drone-cli/releases/latest/download/drone_darwin_amd64.tar.gz | tar zx
sudo cp drone /usr/local/bin

# Homebrew
brew tap drone/drone
brew install drone
```

**Windows** (via [scoop](https://scoop.sh/))
```
scoop install drone
```

Checksum files are published on the GitHub releases page for verifying binaries.

### Configure

The CLI talks to the server over REST, so it needs the server address and your
personal token. Set both as environment variables:

```
export DRONE_SERVER=https://drone.mycompany.com
export DRONE_TOKEN=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

Get your token from the Drone UI: click your avatar → account settings. Without
these two variables every command fails with an authentication/connection error.

---

## Local pipeline execution

### drone exec

Execute a build locally on your machine using a `.drone.yml` file. No server or
token required — this is how you test a pipeline before committing.

```
drone exec [command options] [path/to/.drone.yml]
```

| Flag | Description |
|------|-------------|
| `--pipeline value` | name of the pipeline to execute (for multi-pipeline files) |
| `--include value` | name of steps to include |
| `--exclude value` | name of steps to exclude |
| `--resume-at value` | name of the step to resume at |
| `--trusted` | run as a trusted build (enables `privileged`, host volumes) |
| `--timeout value` | build timeout (default: `1h0m0s`) |
| `--secret-file value` | file of `KEY=VALUE` secrets to inject |
| `--env-file value` | file of `KEY=VALUE` environment variables |

```
drone exec --trusted --secret-file=secrets.txt .drone.yml
```

### drone jsonnet

Convert a Jsonnet configuration file to YAML.

```
drone jsonnet [command options] [path/to/.drone.jsonnet]
```

- `--source value` — source file (default `.drone.jsonnet`)
- `--target value` — target file (default `.drone.yml`)
- `--stream` — write output as a YAML stream (multi-document)
- `--format` — write output as formatted YAML
- `--stdout` — write output to stdout
- `--string` — expect a string, manifest as plain text

```
drone jsonnet --stdout --stream
```

### drone sign

Sign a YAML configuration file to prevent tampering (see the signatures section
of `concepts.md`). The source argument is `owner/name`; the server computes the
HMAC and returns it.

```
drone sign [command options] <source>
```

- `--save` — write the resulting `signature` resource back into the source file

```
drone sign --save octocat/hello-world
```

Re-sign every time the configuration changes, or the pipeline will be blocked.

### drone encrypt

Encrypt a secret into a string you can paste into your pipeline (encrypted
secrets, as opposed to server-stored named secrets).

```
drone encrypt [command options] <repo/name> <string>
```

```
drone encrypt octocat/hello-world "correct-horse-batter-staple"
drone encrypt octocat/hello-world @/path/to/secret.txt   # read value from a file
```

---

## Builds

### drone build ls — list build history

```
drone build ls [command options] <repo/name>
```

- `--branch value` — filter by branch
- `--event value` — filter by event (`push`, `pull_request`, `tag`, `promote`, `cron`, …)
- `--status value` — filter by status
- `--limit value` — page size (default: 25)
- `--page value` — page number (default: 1)

```
drone build ls octocat/hello-world --branch=master --event=push
```

### drone build info — show build details

```
drone build info [command options] <repo/name> [build]
```
```
drone build info octocat/hello-world 42
```

### drone build last — latest build details

```
drone build last [command options] <repo/name>
```
```
drone build last octocat/hello-world
```

### drone build restart — re-run a build

Restarting assigns a new, unique build number. Requires push privileges.

```
drone build restart [command options] <repo/name> [build]
```

- `--param value, -p value` — inject a custom parameter into the job environment

```
drone build restart octocat/hello-world 42 \
  --param=foo=bar \
  --param=baz=qux
```

### drone build stop — stop a running/pending build

Requires push privileges.

```
drone build stop <repo/name> [build]
```
```
drone build stop octocat/hello-world 42
```

### drone build promote — promote a build to an environment

Creates a new build with event type `promote`. Requires push privileges. The
environment name is freeform.

```
drone build promote [command options] <repo/name> <build> <environment>
```

- `--param value, -p value` — inject a custom parameter into the job environment

```
drone build promote octocat/hello-world 42 production
drone build promote octocat/hello-world 42 production --param=ref=v1.2.3
```

### drone build approve / decline — manual approval gates

Approve or decline a pipeline stage that is pending manual approval. Both require
admin privileges to the repository; declining fails the pipeline.

```
drone build approve <repo/name> <build> <stage>
drone build decline <repo/name> <build> <stage>
```
```
drone build approve octocat/hello-world 42 default
```

---

## Repositories

### drone repo ls — list repositories

```
drone repo ls [command options]
```

- `--format value` — Go-template output (e.g. `--format="{{ .Link }}"`)
- `--org value` — filter by organization

```
drone repo ls
drone repo ls --org=github
drone repo ls --format="{{ .Link }}"
```

### drone repo info — repository details

```
drone repo info [command options] <repo/name>
```

- `--format value` — Go-template output

```
drone repo info octocat/hello-world
```

### drone repo enable — activate a repository

Registers a repository with Drone (creates webhooks). Requires admin access.

```
drone repo enable <repo/name>
```

### drone repo rm — disable a repository

The "disable" command is invoked as `drone repo rm`. Requires admin access.

```
drone repo rm <repo/name>
```

### drone repo update — change repository settings

Requires write access.

```
drone repo update [command options] <repo/name>
```

| Flag | Description |
|------|-------------|
| `--trusted` | mark repository trusted (enables privileged steps, host volumes) |
| `--protected` | mark repository protected (enforce signed config) |
| `--timeout value` | build timeout (default: `0s`) |
| `--visibility value` | repository visibility |
| `--ignore-forks` | ignore forks |
| `--ignore-pull-requests` | ignore pull requests |
| `--auto-cancel-pull-requests` | auto-cancel pending PR builds |
| `--auto-cancel-pushes` | auto-cancel pending push builds |
| `--auto-cancel-running` | auto-cancel a running build when a newer commit is pushed |
| `--config value` | config path (e.g. `.drone.yml`) |
| `--build-counter value` | starting build number (default: 0) |
| `--unsafe` | required to make an unsafe change to the build counter |

```
drone repo update octocat/hello-world --trusted=true
drone repo update octocat/hello-world --config=.github/.drone.yml
drone repo update octocat/hello-world --build-counter=10 --unsafe
```

### drone repo repair — recreate webhooks

Re-creates the repository webhooks in your source control system (useful if a
webhook was accidentally deleted).

```
drone repo repair octocat/hello-world
```

### drone repo chown — take ownership

The caller assumes ownership of the repository. Requires admin access.

```
drone repo chown octocat/hello-world
```

---

## Repository secrets

Named secrets scoped to a single repository. Push privileges required. Reference
them in YAML with `from_secret` (see `pipeline-yaml.md`). By default secrets are
**not** exposed to pull requests.

### drone secret add

```
drone secret add [command options] [repo/name]
```

- `--repository value` — repository (e.g. `octocat/hello-world`)
- `--name value` — secret name
- `--data value` — secret value (use `@file` to read from a file)
- `--allow-pull-request` — permit read access from pull requests (security risk)
- `--allow-push-on-pull-request` — permit write access from PRs (e.g. docker push)

```
drone secret add --name my_token --data e72e16c7e42f29 octocat/hello-world
drone secret add --name my_token --data @/path/to/secret.json octocat/hello-world
```

### drone secret ls / info / update / rm

```
drone secret ls octocat/hello-world
drone secret info octocat/hello-world --name my_token
drone secret update --name my_token --data <new_value> octocat/hello-world
drone secret rm octocat/hello-world token
```

`update` accepts the same `--name` / `--data` / `--allow-pull-request` flags as
`add`. `rm` takes `--name` (or the name as a positional argument).

---

## Organization secrets

Named secrets shared across every repository in an organization. **System
administrator** privileges required.

### drone orgsecret add

```
drone orgsecret add [command options] [organization] [name] [data]
```

- `--allow-pull-request` — permit read access from pull requests

```
drone orgsecret add acme my_token e72e16c7e42f29
drone orgsecret add acme my_token e72e16c7e42f29 --allow-pull-request
drone orgsecret add acme my_token @/path/to/secret.json
```

### drone orgsecret ls / info / update / rm

```
drone orgsecret ls
drone orgsecret ls --filter=acme
drone orgsecret info acme my_token
drone orgsecret update acme my_token <new_value> --allow-pull-request
drone orgsecret rm acme my_token
```

---

## Cron jobs

Time-based pipeline triggers. **Self-hosted only** — cron is disabled on Drone
Cloud. See the cron section of `concepts.md` for the critical 6-field expression
format (Drone expressions include a leading **seconds** field).

### drone cron add

```
drone cron add [command options] [repo/name] [cronjob] [cronexpr]
```

- `--branch value` — branch to build (default: `"master"`)

```
drone cron add octocat/hello-world nightly "0 0 0 * * *"   # 6 fields incl. seconds
drone cron add octocat/hello-world deploy @daily            # predefined schedule
```

### drone cron ls / info / enable / disable / exec / rm

```
drone cron ls octocat/hello-world
drone cron info octocat/hello-world nightly
drone cron enable octocat/hello-world nightly
drone cron disable octocat/hello-world nightly
drone cron exec octocat/hello-world nightly     # trigger immediately
drone cron rm octocat/hello-world nightly
```

`ls`/`info` need push access; `enable`/`disable`/`exec`/`rm` need admin access.

---

## Logs

Manage per-step logs. Arguments are `<repo/name> <build> <stage> <step>`.

```
drone log view octocat/hello-world 19 1 3    # print step logs
drone log purge octocat/hello-world 19 1 3   # delete step logs
```

---

## Templates

Organization-level, reusable pipeline templates (Jsonnet / Starlark / YAML). Push
privileges required. See the templates section of `concepts.md`.

### drone template add

```
drone template add [command options] [namespace] [name] [data]
```

- `--name value` — template name (extension selects the engine, e.g. `.yaml`, `.jsonnet`, `.star`)
- `--namespace value` — organization namespace
- `--data value` — template file data (use `@file`)

```
drone template add octocat plugin.starlark @path_to_file
```

### drone template ls / info / update / rm

```
drone template ls octocat
drone template info --namespace octocat --name plugin.starlark
drone template update --namespace octocat --name plugin.starlark --data @path_to_file
drone template rm --namespace octocat --name plugin.starlark
```

---

## Users (admin)

Server user management. **Administrative** privileges required.

```
drone user ls
drone user ls --format="{{ .Login }} <{{ .Email }}>"
drone user info octocat
drone user add octocat
drone user rm octocat
```

`ls`/`info` accept a `--format` Go template.
