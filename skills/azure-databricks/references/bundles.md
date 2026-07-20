# Declarative Automation Bundles (DAB)

Infrastructure-as-code for a Databricks project: define jobs, pipelines, **apps**,
dashboards, model-serving endpoints, MLflow models, etc. in YAML + source, then
`deploy` them reproducibly across environments.

> **Naming:** Microsoft Learn renamed **"Databricks Asset Bundles"** to
> **"Declarative Automation Bundles."** The file (`databricks.yml`), the
> `databricks bundle` command group, and the workflow are unchanged — only the doc
> title moved. "DAB", "Asset Bundles", and "Declarative Automation Bundles" all
> mean the same thing. Requires CLI **v0.218.0+**.

## Table of contents

- [1. Anatomy of `databricks.yml`](#1-anatomy-of-databricksyml)
- [2. Targets (environments)](#2-targets-environments)
- [3. Workflow](#3-workflow)
- [4. Deploying jobs](#4-deploying-jobs)
- [5. Deploying apps](#5-deploying-apps)
- [6. Generate & bind existing resources](#6-generate--bind-existing-resources)
- [7. State & identity](#7-state--identity)

## 1. Anatomy of `databricks.yml`

Exactly one `databricks.yml` at the project root (it may `include` other `*.yml`).
Top-level mappings: `bundle`, `variables`, `workspace`, `artifacts`, `resources`,
`targets`, plus `run_as`, `include`, `sync`, `scripts`, `permissions`.

Minimal:

```yaml
bundle:
  name: my_bundle

targets:
  dev:
    default: true
```

References inside YAML: variables `${var.name}`, resources
`${resources.jobs.my_job.id}`, workspace `${workspace.file_path}`.

## 2. Targets (environments)

`targets` are named environments; each can override `workspace.host`, `mode`,
variables, and resources. **Prefer setting each target's `workspace.host` over
`default: true`** — the CLI matches that host against a `.databrickscfg` profile to
select the auth type (see `cli.md`).

```yaml
targets:
  dev:
    mode: development                 # prefixes resource names, relaxes validation
    workspace:
      host: https://adb-5555555555555555.19.azuredatabricks.net
  prod:
    mode: production
    workspace:
      host: https://adb-9999999999999999.7.azuredatabricks.net
```

`mode: development` name-prefixes and pauses schedules so dev deploys don't collide;
`mode: production` enforces stricter validation.

## 3. Workflow

```bash
databricks bundle init                    # interactive template picker
databricks bundle init default-python     # a named built-in template
databricks bundle init https://github.com/org/repo --branch main   # a git template

databricks bundle validate                # local config check
databricks bundle plan                    # preview changes without applying
databricks bundle deploy                  # deploy the default target
databricks bundle deploy -t prod          # deploy a specific target
databricks bundle run my_job              # run a job/pipeline/app resource
databricks bundle summary                 # deployed identity + deep links
databricks bundle destroy                 # delete deployed resources (--auto-approve)
```

Key `deploy` flags: `-t/--target`, `--force`, `--force-lock`, `--auto-approve`,
`--fail-on-active-runs`, `-c/--cluster-id`, `--select <resource>` (deploy a subset).
`run` flags: `--params k=v,...`, `--restart`, `--no-wait`.

> Built-in template names beyond `default-python` (e.g. `default-sql`, `dbt-sql`,
> `mlops-stacks`) vary by CLI version — confirm via the interactive
> `databricks bundle init` prompt or the templates docs.

## 4. Deploying jobs

```yaml
bundle:
  name: hello-bundle

resources:
  jobs:
    hello_job:
      name: hello-job
      tasks:
        - task_key: hello-task
          notebook_task:
            notebook_path: ./hello.py

targets:
  dev:
    default: true
  prod:
    workspace:
      host: https://adb-9999999999999999.7.azuredatabricks.net
    resources:
      jobs:
        hello_job:
          tasks:
            - task_key: hello-task
              existing_cluster_id: 2345-678901-fabcd456
```

Deploy then run:

```bash
databricks bundle deploy -t prod
databricks bundle run hello_job -t prod
```

## 5. Deploying apps

Apps are a first-class bundle resource (`resources.apps`) — this is how a Databricks
App ships to production. `source_code_path` is required; `config` mirrors `app.yaml`
(`config.env` overrides the file); attach resources and set permissions inline.

Minimal:

```yaml
resources:
  apps:
    hello_world_app:
      name: 'hello-world-app'
      source_code_path: .
      description: 'A Databricks app'
```

Fuller:

```yaml
resources:
  apps:
    analytics_app:
      name: 'analytics-app'
      source_code_path: ./app
      description: 'Analytics dashboard app'
      config:
        command: ['streamlit', 'run', 'app.py']
        env:
          - name: MY_ENV_VAR
            value: test_value
      resources:
        - name: 'analytics-warehouse'
          sql_warehouse:
            id: ${var.warehouse_id}
            permission: 'CAN_USE'
        - name: 'ml-model'
          serving_endpoint:
            name: my-serving-endpoint
            permission: 'CAN_QUERY'
      permissions:
        - level: CAN_RUN
          user_name: user@example.com
```

Deploy (optionally just the app while iterating):

```bash
databricks bundle deploy -t dev
databricks bundle deploy -t dev --select apps.analytics_app
```

> The `resources.apps[].resources[]` sub-schema (the `sql_warehouse` / `secret` /
> `serving_endpoint` keys and permission enums like `CAN_USE`, `CAN_QUERY`,
> `READ_VOLUME`) is actively evolving and some resource types are direct-engine-only.
> Confirm against the live "Declarative Automation Bundles resources" reference at
> build time.

## 6. Generate & bind existing resources

Reverse-engineer YAML from resources already in the workspace:

```bash
databricks bundle generate app --existing-app-name my-app     # writes <app>.app.yml + downloads app.yaml/app.py
databricks bundle generate job --existing-job-id 1234
databricks bundle generate pipeline --existing-pipeline-id <id>
databricks bundle generate dashboard --existing-path <path>
```

Add `--bind` (or `databricks bundle deployment bind`) to manage the existing
resource in place instead of creating a copy. UC resources bind by full name
(`catalog.schema.table`), not by ID.

## 7. State & identity

A deployment's identity = deployer + `bundle.name` + target + workspace. State
lives at `root_path` (defaults to `~/.bundle/${bundle.name}/${bundle.target}` in the
workspace) and tracks resources by ID, so re-deploys update rather than duplicate.

Primary sources:
- Overview — <https://learn.microsoft.com/azure/databricks/dev-tools/bundles/>
- Settings (`databricks.yml`) — <https://learn.microsoft.com/azure/databricks/dev-tools/bundles/settings>
- Resources — <https://learn.microsoft.com/azure/databricks/dev-tools/bundles/resources>
- Bundle commands — <https://learn.microsoft.com/azure/databricks/dev-tools/cli/bundle-commands>
- Examples — <https://github.com/databricks/bundle-examples>
