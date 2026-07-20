# Databricks Apps

Managed **serverless** hosting for a data/AI web app on Azure Databricks — no
separate infrastructure. Integrates with Unity Catalog (governance), Databricks
SQL (querying), and OAuth (auth).

## Table of contents

- [1. What they are & limits](#1-what-they-are--limits)
- [2. Project layout](#2-project-layout)
- [3. `app.yaml`](#3-appyaml)
- [4. Lifecycle via the CLI](#4-lifecycle-via-the-cli)
- [5. Resources, secrets & the service principal](#5-resources-secrets--the-service-principal)
- [6. Injected environment variables](#6-injected-environment-variables)
- [7. Local development](#7-local-development)
- [8. Permissions & auth models](#8-permissions--auth-models)

## 1. What they are & limits

- **Frameworks:** Python — Streamlit, Dash, Gradio (first-class), plus Flask,
  FastAPI, Shiny via a custom `command`. Node.js — React, Angular, Svelte, Express.
- **Requirements / limits:**
  - **Premium-tier** workspace required.
  - Billed per hour of compute **while running** (stop apps you're not using).
  - Limited number of apps per workspace.
  - **Each app file must be ≤ 10 MB** — large model weights or a bundled
    `node_modules` will fail the deploy; fetch big artifacts at runtime instead.
- **Runtime environment:** Ubuntu 22.04 LTS, Python 3.11, `uv`, Node.js 22. Default
  compute up to **2 vCPU / 6 GB** (configurable).

## 2. Project layout

Three canonical files at the project root:

```
my-app/
├── app.py            # your application code (entry point)
├── app.yaml          # optional runtime config (command + env)
└── requirements.txt  # Python deps (uv-compatible); Node uses package.json
```

If `app.yaml` is absent, the default command is `python <first .py file>` (Python)
or `npm run start` (Node).

## 3. `app.yaml`

Optional file (`.yaml` or `.yml`). Two keys: `command` (a sequence — argv, **not**
run through a shell) and `env` (a list of `name` + either `value` or `valueFrom`).
Because there's no shell, external env vars are not expanded except
`DATABRICKS_APP_PORT`, which is substituted at runtime.

Streamlit:

```yaml
command: ['streamlit', 'run', 'app.py']
env:
  - name: 'DATABRICKS_WAREHOUSE_ID'
    value: 'quoz2bvjy8bl7skl'
  - name: 'STREAMLIT_GATHER_USAGE_STATS'
    value: 'false'
```

Flask via Gunicorn:

```yaml
command:
  - gunicorn
  - app:app
  - -w
  - '4'
env:
  - name: 'VOLUME_URI'
    value: '/Volumes/my_catalog/my_schema/my_dir'
```

FastAPI (Uvicorn binds to the injected port automatically):

```yaml
command: ['uvicorn', 'app:app']
```

## 4. Lifecycle via the CLI

```bash
# 1. Create the app (provisions the app + a dedicated service principal)
databricks apps create my-app
databricks apps create my-app --no-compute --no-wait   # skip immediate compute

# 2. Get local code into the workspace. Either start fresh, or export a template:
databricks workspace export-dir /Workspace/Users/me@corp.com/databricks_apps/<template-folder> .
# Live-sync local edits up to the workspace:
databricks sync --watch . /Workspace/Users/me@corp.com/my-app

# 3. Deploy from the synced workspace source path
databricks apps deploy my-app --source-code-path /Workspace/Users/me@corp.com/my-app
databricks apps deploy my-app --no-wait

# 4. Operate
databricks apps list
databricks apps get my-app          # status + URL
databricks apps start my-app
databricks apps stop my-app         # stops billing
databricks apps logs my-app
databricks apps delete my-app
```

The app **URL is auto-generated** from the app name + workspace ID and is
immutable. In the workspace UI, the app's "Edit in your IDE" / "Deploy to
Databricks Apps" panels print the exact `export-dir` / `sync` / `deploy` commands
for your specific app.

Git-based deployment (alternative to workspace sync):

```bash
databricks apps create-update my-app \
  --json '{"update_mask":"git_repository","git_repository":{"url":"https://github.com/org/repo","provider":"gitHub"}}'
databricks apps deploy my-app --json '{"git_source":{"branch":"main"}}'
```

## 5. Resources, secrets & the service principal

Each app runs under its **own service principal**, created at `apps create`. To
give the app access to a SQL warehouse, secret, model-serving endpoint, UC table,
job, etc., **attach that resource to the app** (granting the app's SP access), then
reference it in `app.yaml` with `valueFrom` instead of hardcoding:

```yaml
env:
  - name: WAREHOUSE_ID
    valueFrom: sql_warehouse       # → the warehouse ID
  - name: SECRET_KEY
    valueFrom: secret              # → the decrypted secret value
  - name: SERVING_ENDPOINT
    valueFrom: serving_endpoint    # → the endpoint name
```

`valueFrom` resolves per resource type: SQL warehouse → warehouse ID; secret →
decrypted value; model-serving endpoint → endpoint name; UC table → full name; UC
volume → `/Volumes/...` path; job → job ID; experiment → experiment ID; connection
→ connection name; vector-search index → index full name; Genie → space ID.

**Never put a secret in `value`** — anything there is stored in plaintext in the
app config. Always route secrets through `valueFrom: secret`.

## 6. Injected environment variables

Every app automatically gets:

| Variable | Meaning |
|---|---|
| `DATABRICKS_APP_NAME` | the app name |
| `DATABRICKS_WORKSPACE_ID` | workspace ID |
| `DATABRICKS_HOST` | workspace URL |
| `DATABRICKS_APP_PORT` | the port your server must bind to |
| `DATABRICKS_CLIENT_ID` / `DATABRICKS_CLIENT_SECRET` | the app's **own** service-principal OAuth credentials |

Framework host/port vars are auto-set and bound to `DATABRICKS_APP_PORT`:
`STREAMLIT_SERVER_PORT`, `GRADIO_SERVER_PORT` / `GRADIO_SERVER_NAME=0.0.0.0`,
`UVICORN_PORT` / `UVICORN_HOST` (FastAPI), `FLASK_RUN_PORT` / `FLASK_RUN_HOST`,
`PORT` (Dash / Express). Bind to `DATABRICKS_APP_PORT` and you rarely set these
yourself.

Use the injected `DATABRICKS_CLIENT_ID`/`_SECRET` (via the Databricks SDK) for the
app to authenticate to Databricks services as itself.

## 7. Local development

```bash
databricks apps run-local
databricks apps run-local --prepare-environment --debug
```

`--prepare-environment` installs deps; `--debug` starts the app plus a debugger
(debugpy on port 5678). The local UI is served on `http://localhost:8001`. This
runs the app the same way the platform would (reading `app.yaml`), so it's the
fastest inner loop before `apps deploy`.

## 8. Permissions & auth models

Two authorization models:

- **App identity** — the app calls Databricks as its own service principal
  (`DATABRICKS_CLIENT_ID/_SECRET`). Simple; the app sees everything its SP can.
- **On-behalf-of-user** — the app acts with the calling user's identity/permissions
  (finer-grained governance).

Who can use or manage the app is controlled by app permissions
(`CAN_USE`, `CAN_MANAGE`, etc.), grantable via the UI or the API/bundle.

## Bundles

Apps are also a first-class **bundle resource** (`resources.apps`) — see
`bundles.md` for deploying an app as code with `databricks bundle deploy`, and
`databricks bundle generate app --existing-app-name <name>` to reverse-engineer the
YAML + download `app.yaml`/`app.py` from a live app.

Primary sources:
- Overview — <https://learn.microsoft.com/azure/databricks/dev-tools/databricks-apps/>
- Get started — <https://learn.microsoft.com/azure/databricks/dev-tools/databricks-apps/get-started>
- `app.yaml` / runtime — <https://learn.microsoft.com/azure/databricks/dev-tools/databricks-apps/app-runtime>
- Environment variables — <https://learn.microsoft.com/azure/databricks/dev-tools/databricks-apps/environment-variables>
- System environment — <https://learn.microsoft.com/azure/databricks/dev-tools/databricks-apps/system-env>
