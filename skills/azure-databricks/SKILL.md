---
name: azure-databricks
description: >-
  Work with Azure Databricks from the command line — the unified `databricks`
  CLI (the Go rewrite, v0.205+), Databricks Apps, and Declarative Automation
  Bundles (formerly Databricks Asset Bundles / DAB). Use this whenever the user
  mentions the `databricks` CLI, a `.databrickscfg` profile, `databricks auth
  login`, `databricks.yml`, `databricks bundle`, Databricks Apps, an `app.yaml`,
  `databricks apps deploy`, `databricks sync`, an `adb-*.azuredatabricks.net`
  workspace, Databricks service principals / Entra ID auth, or driving Unity
  Catalog / jobs / clusters / secrets through the CLI — even if they don't say
  the word "skill." This includes configuring auth for Azure, deploying a
  Streamlit/Dash/Gradio app, authoring or fixing bundle YAML, and running
  everyday workspace operations. IMPORTANT: this is the Databricks data & AI
  platform on Azure and its `databricks` command-line tool, NOT generic Apache
  Spark, NOT the AWS/GCP-specific setup steps, and NOT database "bricks" of any
  other kind.
---

# Azure Databricks (CLI, Apps, Bundles)

This skill helps you drive Azure Databricks through the unified `databricks` CLI:
authenticate against a workspace, run everyday operations, deploy **Databricks
Apps**, and ship resources as **Declarative Automation Bundles**.

## Mental model (read this first)

The `databricks` CLI is a thin client over the workspace **REST API**. Almost
everything is: pick an identity (a profile), point at a workspace host, call a
command group. Three kinds of work this skill covers:

1. **Operate** — one-off commands against a workspace: `fs`, `workspace`, `jobs`,
   `clusters`, `secrets`, Unity Catalog (`catalogs`/`schemas`/`tables`).
2. **Databricks Apps** — host a Python/Node web app (Streamlit, Dash, Gradio,
   Flask/FastAPI, Shiny) on Databricks' serverless platform via `databricks apps`.
3. **Bundles (DAB)** — define a project (jobs, pipelines, **apps**, dashboards…)
   as code in `databricks.yml` and `deploy` it across dev/prod targets.

One naming trap up front: **"Databricks Asset Bundles" were renamed "Declarative
Automation Bundles"** in the Azure docs. The file (`databricks.yml`), the command
group (`databricks bundle`), and the workflow are unchanged — only the doc title
moved. Treat "DAB", "Asset Bundles", and "Declarative Automation Bundles" as the
same thing.

## Before running any command: the CLI and auth

**This must be the unified Go CLI (v0.205.0+; bundles need v0.218.0+).** The old
Python `databricks-cli` is a different tool with different commands. Verify:

```
databricks version      # or: databricks -v   → shows e.g. Databricks CLI v0.240.0
```

Install (details + Windows in `references/cli.md`):

```
brew tap databricks/tap && brew install databricks          # macOS
curl -fsSL https://raw.githubusercontent.com/databricks/setup-cli/main/install.sh | sh   # Linux/macOS
```

Every command except local ones (`bundle validate`, `apps run-local`) needs an
**identity + workspace host**. On Azure the workspace host looks like
`https://adb-<workspace-id>.<n>.azuredatabricks.net`. Credentials live in
`~/.databrickscfg` as named profiles (the `DEFAULT` profile is used when no
`-p/--profile` is given). Resolution order: **bundle files → environment
variables → `.databrickscfg`**.

Pick the auth method that matches the user's situation — do not default to a PAT:

| Situation | Method | Quick start |
|-----------|--------|-------------|
| A human at a laptop | **OAuth U2M** (browser) | `databricks auth login --host https://adb-….azuredatabricks.net` |
| CI/CD, automation (Databricks-managed SP) | **OAuth M2M** | profile with `client_id` + `client_secret` |
| Azure AD / Entra ID service principal | **Entra SP** | profile with `azure_tenant_id`/`azure_client_id`/`azure_client_secret` (needs `az` CLI) |
| Already signed in with Azure CLI | **`az login` passthrough** | `az login` + a profile with just `host` |
| Code on an Azure VM | **Managed identity (MSI)** | profile with `azure_use_msi = true` |
| Legacy / quick token | **PAT** | profile with `token = dapi…` (prefer OAuth) |

The single biggest auth mistake: **Entra ID service principals use `ARM_*` /
`azure_*` fields; Databricks-managed OAuth SPs use `DATABRICKS_CLIENT_ID/_SECRET`
/ `client_id`.** They are not interchangeable. The full field ↔ env-var mapping
table is in `references/cli.md` — read it before writing any auth config.

Inspect what you have: `databricks auth profiles`, `databricks auth describe`,
`databricks current-user me -p <profile>`.

## Everyday operations

Once a profile works, drive the workspace. Add `-p <profile>` (or set
`DATABRICKS_CONFIG_PROFILE`) and `-o json` for machine-readable output.

```
databricks workspace list /Users/me@corp.com          # browse the workspace tree
databricks fs cp ./data.csv dbfs:/tmp/data.csv         # DBFS files (dbfs:/ scheme)
databricks jobs list                                   # jobs; run-now, submit, get-run…
databricks clusters list                               # clusters; start, get, spark-versions
databricks secrets list-scopes                         # secrets: create-scope, put-secret…
databricks catalogs list                               # Unity Catalog: schemas, tables, volumes, grants
databricks api get /api/2.1/jobs/list                  # raw REST escape hatch
```

Full command-group cheatsheet and flags: `references/cli.md`.

## Databricks Apps

Managed **serverless** hosting for a data/AI web app — no infra to run. See
`references/apps.md` for the full lifecycle; the shape:

```
databricks apps create my-app                          # provisions the app + a dedicated service principal
databricks sync --watch . /Workspace/Users/me@corp.com/my-app   # push local code up
databricks apps deploy my-app --source-code-path /Workspace/Users/me@corp.com/my-app
databricks apps logs my-app                            # start / stop / list / get / delete
```

An app is three files: your code (`app.py`), an optional `app.yaml` (the
`command` to run + `env`), and `requirements.txt`. Two rules that cause silent
failures, both detailed in `references/apps.md`:

- **Never put a secret in `env.value`.** Attach the resource (SQL warehouse,
  secret, serving endpoint…) to the app and reference it with `valueFrom` — the
  app's service principal is granted access.
- **Requirements to know before promising anything:** a **Premium-tier**
  workspace, billed per running hour, and **each app file must be ≤ 10 MB**.

## Bundles (Declarative Automation Bundles / DAB)

Define jobs, pipelines, **apps**, dashboards, etc. as code and deploy them
reproducibly. Full syntax in `references/bundles.md`. Minimal loop:

```
databricks bundle init default-python     # scaffold from a template
databricks bundle validate                 # check config (local)
databricks bundle deploy -t dev            # deploy to the "dev" target
databricks bundle run my_job               # run a resource
databricks bundle deploy -t prod           # promote to prod
databricks bundle destroy                  # tear down
```

`databricks.yml` has a `bundle:` name, `resources:` (what to create), and
`targets:` (environments — each overriding `workspace.host`, `mode`, variables).
Prefer setting each target's `workspace.host` over `default: true`; the CLI
matches that host to a `.databrickscfg` profile to choose the auth. **Apps deploy
as a bundle resource** (`resources.apps`) — this is how an app ships to
production. See `references/bundles.md` for the app-in-bundle schema and
`bundle generate app --existing-app-name` to reverse-engineer YAML from a live app.

## Gotchas to check before handing something over

These pass a glance but fail at runtime:

1. **Wrong CLI.** If commands like `bundle`, `apps`, or `auth login` are missing,
   it's the legacy Python `databricks-cli`. Require v0.205+ (`databricks version`);
   bundles need v0.218+.
2. **Entra SP vs Databricks OAuth SP fields.** `ARM_*` / `azure_*` ≠
   `DATABRICKS_CLIENT_*`. Mixing them yields "cannot configure default
   credentials". Match the method to the field set (see the table above).
3. **Azure workspace host format.** Use `adb-<id>.<n>.azuredatabricks.net`, not a
   legacy regional URL like `westus.azuredatabricks.net`. Account-level commands
   use `accounts.azuredatabricks.net` with `--account-id`.
4. **App secrets belong in `valueFrom`, never `value`.** Anything in `value` is
   plaintext in the app config.
5. **App file-size limit (10 MB each) and Premium-tier requirement.** Large model
   files or a big `node_modules` will fail the deploy.
6. **U2M token storage.** As of CLI v1.0.0, `auth login` stores tokens in the OS
   keychain, not `.databrickscfg`. For headless CI, set
   `DATABRICKS_AUTH_STORAGE=plaintext` before `auth login`.
7. **Bundle target ≠ profile automatically.** A target selects auth by matching
   `workspace.host` to a profile (or via `-p`); a bare `bundle deploy` uses the
   default target — always pass `-t <target>` for prod.

## Reference files

Load the one that matches the task — don't guess syntax from memory:

- **`references/cli.md`** — install (macOS/Linux/Windows), the full Azure auth
  matrix with the env-var ↔ `.databrickscfg`-field mapping table, and the command
  groups with flags. Read before writing any auth config or unfamiliar command.
- **`references/apps.md`** — Databricks Apps end to end: create/deploy lifecycle,
  `app.yaml` (`command` + `env` + `valueFrom`), the injected env vars and service
  principal, resources/permissions, and the local dev loop (`apps run-local`).
- **`references/bundles.md`** — `databricks.yml` structure, `targets`, the
  `init/validate/plan/deploy/run/destroy` workflow, and deploying **apps** and
  jobs as bundle resources.

When something isn't covered here, the authoritative docs are the Azure Databricks
dev-tools pages at
<https://learn.microsoft.com/azure/databricks/dev-tools/> and the CLI reference at
<https://learn.microsoft.com/azure/databricks/dev-tools/cli/commands>.
