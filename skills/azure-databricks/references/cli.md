# Databricks CLI on Azure — install, auth, commands

The **unified `databricks` CLI** (the Go rewrite, v0.205.0+) is a client over the
Databricks REST API. Bundles need **v0.218.0+**. It is *not* the legacy Python
`databricks-cli`. Everything here targets **Azure Databricks**.

## Table of contents

- [1. Install & verify](#1-install--verify)
- [2. Workspace & account URLs](#2-workspace--account-urls)
- [3. Authentication](#3-authentication)
  - [3.1 Config profiles (`.databrickscfg`)](#31-config-profiles-databrickscfg)
  - [3.2 OAuth U2M (interactive)](#32-oauth-u2m-interactive)
  - [3.3 OAuth M2M (Databricks-managed service principal)](#33-oauth-m2m-databricks-managed-service-principal)
  - [3.4 Microsoft Entra ID service principal](#34-microsoft-entra-id-service-principal)
  - [3.5 Azure CLI passthrough](#35-azure-cli-passthrough)
  - [3.6 Azure managed identity (MSI)](#36-azure-managed-identity-msi)
  - [3.7 Personal access token (PAT, legacy)](#37-personal-access-token-pat-legacy)
  - [3.8 Env-var ↔ config-field mapping](#38-env-var--config-field-mapping)
  - [3.9 Inspecting auth](#39-inspecting-auth)
- [4. Command groups](#4-command-groups)
- [5. Global flags & output](#5-global-flags--output)

## 1. Install & verify

```bash
# macOS (Homebrew)
brew tap databricks/tap
brew install databricks
# or without trusting the full tap:
brew install databricks/tap/databricks
brew upgrade databricks

# Linux / macOS (curl script — installs to /usr/local/bin/databricks; re-run to update)
curl -fsSL https://raw.githubusercontent.com/databricks/setup-cli/main/install.sh | sh

# Windows (WinGet)
winget install Databricks.DatabricksCLI
winget upgrade Databricks.DatabricksCLI
# Windows (Chocolatey, experimental)
choco install databricks-cli
```

Verify — and confirm it's the Go CLI, not the Python one:

```bash
databricks version      # e.g. "Databricks CLI v0.240.0"
databricks -v
```

If `databricks bundle`, `databricks apps`, or `databricks auth login` are
"unknown command", the legacy Python `databricks-cli` is on the PATH instead —
uninstall it (`pip uninstall databricks-cli`) or fix ordering.

Source install: download `databricks_cli_X.Y.Z_<os>_<arch>.zip` from
<https://github.com/databricks/cli/releases> and extract onto the PATH. The CLI is
also preinstalled in the workspace web terminal.

## 2. Workspace & account URLs

- **Per-workspace host (Azure):** `https://adb-<workspace-id>.<n>.azuredatabricks.net`
  — e.g. `https://adb-5555555555555555.19.azuredatabricks.net`. This is the value
  for `host`. Avoid legacy regional URLs like `https://westus.azuredatabricks.net`.
- **Account console (account-level commands):** `https://accounts.azuredatabricks.net`,
  combined with `--account-id <uuid>` (or `DATABRICKS_ACCOUNT_ID`, which only takes
  effect when `host` is the account endpoint).

## 3. Authentication

### 3.1 Config profiles (`.databrickscfg`)

Location: `~/.databrickscfg` (macOS/Linux) or `%USERPROFILE%\.databrickscfg`
(Windows). The `DEFAULT` profile is used when no `-p/--profile` is passed. Select a
profile with `-p <name>` or the `DATABRICKS_CONFIG_PROFILE` env var. Format:

```ini
[DEFAULT]
host = https://adb-5555555555555555.19.azuredatabricks.net

[prod]
host = https://adb-9999999999999999.7.azuredatabricks.net
```

**Auth resolution order (first match wins):** bundle settings files (no credentials
allowed there) → environment variables → `.databrickscfg` profiles.

### 3.2 OAuth U2M (interactive) — recommended for humans

```bash
# workspace-level
databricks auth login --host https://adb-5555555555555555.19.azuredatabricks.net
# account-level
databricks auth login --host https://accounts.azuredatabricks.net --account-id <account-id>
```

Opens a browser, then saves a profile (it prompts for a profile name). **As of CLI
v1.0.0, U2M tokens are stored in OS-native secure storage** (macOS Keychain,
Windows Credential Manager, Linux D-Bus Secret Service) — not written to
`.databrickscfg`. For headless/CI, force plaintext storage:

```bash
export DATABRICKS_AUTH_STORAGE=plaintext
databricks auth login --host <workspace-url>
# or set, under a [__settings__] section in .databrickscfg:
#   auth_storage = plaintext
```

### 3.3 OAuth M2M (Databricks-managed service principal) — recommended for automation

Create a Databricks service principal + OAuth secret in the account console, then:

```ini
[m2m]
host          = https://adb-5555555555555555.19.azuredatabricks.net
client_id     = <service-principal-application-id>
client_secret = <oauth-secret>
# account-level also needs: account_id = <account-id>
```

Env-var equivalent: `DATABRICKS_CLIENT_ID`, `DATABRICKS_CLIENT_SECRET`,
`DATABRICKS_HOST`.

### 3.4 Microsoft Entra ID service principal

An Azure AD (Entra ID) app registration with a client secret. **Requires the Azure
CLI (`az`) installed** on the machine. Distinct from 3.3 — different fields.

```ini
[entra-sp]
host                = https://adb-5555555555555555.19.azuredatabricks.net
azure_tenant_id     = <directory-tenant-id>
azure_client_id     = <application-client-id>
azure_client_secret = <client-secret>
# instead of host you may use:
# azure_workspace_resource_id = /subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.Databricks/workspaces/<name>
```

Env-var equivalent: `ARM_TENANT_ID`, `ARM_CLIENT_ID`, `ARM_CLIENT_SECRET`
(+ `DATABRICKS_HOST` or `DATABRICKS_AZURE_RESOURCE_ID`).

### 3.5 Azure CLI passthrough

Uses the identity from `az login` (user or SP). Minimal profile:

```bash
az login
```
```ini
[azure-cli]
host = https://adb-5555555555555555.19.azuredatabricks.net
```

### 3.6 Azure managed identity (MSI)

For code running on an Azure resource (VM, etc.) with a managed identity:

```ini
[msi]
host            = https://adb-5555555555555555.19.azuredatabricks.net
azure_client_id = <managed-identity-client-id>   # omit for system-assigned
azure_use_msi   = true
```

Env-var equivalent: `ARM_USE_MSI=true`, `ARM_CLIENT_ID`.

### 3.7 Personal access token (PAT, legacy)

Prefer OAuth. Still supported:

```ini
[pat]
host  = https://adb-5555555555555555.19.azuredatabricks.net
token = dapi0123456789abcdef...
```

`databricks configure --token --host <url> --profile <name>` also creates a PAT
profile interactively. Env-var equivalent: `DATABRICKS_HOST`, `DATABRICKS_TOKEN`.

### 3.8 Env-var ↔ config-field mapping

The `ARM_*` (Entra/MSI) vs `DATABRICKS_CLIENT_*` (Databricks OAuth SP) split is the
single most common source of auth errors. Full mapping:

| Env var | `.databrickscfg` field | Use |
|---|---|---|
| `DATABRICKS_HOST` | `host` | workspace or account URL |
| `DATABRICKS_TOKEN` | `token` | PAT or Entra ID token |
| `DATABRICKS_ACCOUNT_ID` | `account_id` | account endpoint |
| `DATABRICKS_CONFIG_PROFILE` | *(selects profile)* | non-DEFAULT profile |
| `DATABRICKS_CONFIG_FILE` | `config_file` | alternate cfg path |
| `DATABRICKS_CLIENT_ID` | `client_id` | OAuth M2M (Databricks SP) |
| `DATABRICKS_CLIENT_SECRET` | `client_secret` | OAuth M2M (Databricks SP) |
| `DATABRICKS_AUTH_TYPE` | `auth_type` | force a type: `oauth-m2m`, `pat`, `databricks-cli`, `azure-msi`, `azure-client-secret`, `azure-cli`, `oidc-token`, `github-oidc`, `azure-devops-oidc` |
| `ARM_CLIENT_ID` | `azure_client_id` | Entra ID SP / MSI |
| `ARM_CLIENT_SECRET` | `azure_client_secret` | Entra ID SP |
| `ARM_TENANT_ID` | `azure_tenant_id` | Entra ID SP |
| `ARM_USE_MSI` | `azure_use_msi` | MSI |
| `ARM_ENVIRONMENT` | `azure_environment` | defaults `PUBLIC` |
| `DATABRICKS_AZURE_RESOURCE_ID` | `azure_workspace_resource_id` | ARM ID of the workspace |
| `DATABRICKS_CLUSTER_ID` | `cluster_id` | pin a cluster |
| `DATABRICKS_SERVERLESS_COMPUTE_ID` | `serverless_compute_id` | value `auto` |

### 3.9 Inspecting auth

```bash
databricks auth profiles            # list profiles + whether each is valid
databricks auth describe            # what auth the CLI resolved right now
databricks auth env --profile prod  # env vars for a profile
databricks current-user me -p prod  # smoke test: who am I in this workspace
```

## 4. Command groups

Get help with `databricks <group> -h` and `databricks <group> <cmd> -h`.

| Group | Common commands | Notes |
|---|---|---|
| `auth` | `login`, `profiles`, `describe`, `token` | authentication |
| `configure` | `--token`, `--host`, `--profile` | create a profile |
| `current-user` | `me` | identity smoke test |
| `fs` | `cat`, `cp`, `ls`, `mkdir`, `rm` | DBFS files (`dbfs:/…`) |
| `workspace` | `import`, `export`, `import-dir`, `export-dir`, `list`, `mkdirs`, `delete`, `get-status` | notebooks/files in the workspace tree |
| `jobs` | `create`, `run-now`, `submit`, `list`, `get`, `get-run`, `cancel-run`, `repair-run`, `delete`, `reset`, `update` | Workflows / jobs |
| `clusters` | `create`, `start`, `restart`, `edit`, `delete`, `list`, `get`, `resize`, `spark-versions`, `list-node-types` | compute |
| `warehouses` | `create`, `start`, `stop`, `list`, `get` | Databricks SQL warehouses |
| `secrets` | `create-scope`, `put-secret`, `get-secret`, `list-scopes`, `list-secrets`, `put-acl`, `delete-secret` | secret scopes |
| `catalogs` / `schemas` / `tables` / `volumes` / `grants` | `list`, `get`, `create`… | Unity Catalog (`catalog.schema.table`) |
| `metastores` / `storage-credentials` / `external-locations` | `list`, `get`… | UC admin |
| `sync` | `<local> <remote> [--watch]` | one-way local→workspace dir sync (used by Apps) |
| `bundle` | `init`, `validate`, `plan`, `deploy`, `run`, `summary`, `destroy`, `generate`, `deployment`, `schema`, `sync` | Declarative Automation Bundles — see `bundles.md` |
| `apps` | `create`, `deploy`, `start`, `stop`, `list`, `get`, `delete`, `logs`, `run-local`, `create-update` | Databricks Apps — see `apps.md` |
| `api` | `get`/`post`/`patch`/`delete <path>` | raw REST escape hatch |

## 5. Global flags & output

- `-p, --profile <name>` — pick a `.databrickscfg` profile.
- `-t, --target <name>` — bundle target/environment (bundle commands).
- `-o, --output {text|json}` — JSON for scripting/piping to `jq`.
- `--debug` / `--log-level <level>` — verbose troubleshooting (shows the HTTP calls).
- `--var 'key=value'` — override a bundle variable.

Primary sources:
- Install — <https://learn.microsoft.com/azure/databricks/dev-tools/cli/install>
- Authentication — <https://learn.microsoft.com/azure/databricks/dev-tools/cli/authentication>
- Config profiles — <https://learn.microsoft.com/azure/databricks/dev-tools/auth/config-profiles>
- Env vars — <https://learn.microsoft.com/azure/databricks/dev-tools/auth/env-vars>
- Commands — <https://learn.microsoft.com/azure/databricks/dev-tools/cli/commands>
