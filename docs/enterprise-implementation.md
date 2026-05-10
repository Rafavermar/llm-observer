# Enterprise Implementation Guide

This guide explains how to run LLM Observer in a company with low implementation friction while preserving user, team, app and workflow attribution.

## Recommended Pattern

Use LLM Observer together with LiteLLM as a central LLM gateway.

```text
developers / internal apps
  -> https://llm-gateway.company.com/v1
  -> LiteLLM Proxy
  -> OpenAI / Anthropic / Azure OpenAI / Databricks
         |
         | callback / normalized usage event
         v
  Observer API
  -> Observer database
  -> dashboard
```

Provider keys belong in the gateway, not in every application. Applications should receive virtual keys from the gateway and send enough metadata to identify who or what caused the usage.

## Localhost vs Company URLs

`localhost` is only for local development. It means "this same machine".

Local development:

```text
Dashboard: http://localhost:3000
Observer API: http://localhost:8080
LiteLLM Gateway: http://localhost:4040/v1
```

In a company, users should not open `localhost`. Use real internal domains.

Recommended production-style URLs:

```text
Dashboard: https://llm-observer.company.com
Observer API: https://llm-observer.company.com/api
LiteLLM Gateway: https://llm-gateway.company.com/v1
```

This same-domain dashboard/API pattern reduces CORS friction because the browser reads the API from the same origin.

Alternative split-domain pattern:

```text
Dashboard: https://llm-observer.company.com
Observer API: https://llm-observer-api.company.com
LiteLLM Gateway: https://llm-gateway.company.com/v1
```

If using split domains, configure CORS so the API only accepts the real dashboard origin.

Internal container or cluster service names are different from browser URLs:

```text
observer-api:8080
litellm-proxy:4000
```

Those names are for service-to-service communication inside Docker/Kubernetes, not for end users.

## How To Attribute Spend With A Corporate Provider Key

A provider API key identifies the billing credential, not the real caller.

Example:

```text
OPENAI_API_KEY=sk-company-provider-key
```

That key tells OpenAI which account to bill. It does not automatically tell Observer whether Ana, Rafa, the support app, the data platform team, or a batch job caused the usage.

To attribute usage, you need one or both of these:

- A LiteLLM virtual key per user, team, app or environment.
- Per-request metadata from the calling application.

Recommended model:

```text
Corporate provider key
  -> stored only in LiteLLM

LiteLLM virtual key
  -> given to a user/team/app
  -> maps usage to owner and budget

Request metadata
  -> identifies actual end user, app, workflow and cost center
```

Without virtual keys or metadata, Observer can still show total provider usage, but it cannot reliably split spend by user.

## Identity Levels

Use several identity levels because enterprise LLM usage is rarely just "one user".

```text
provider_account: billing account at OpenAI/Azure/Anthropic/Databricks
virtual_key_owner: user/team/app that owns the LiteLLM key
end_user: person who triggered the action in an internal app
app: product or service making the call
workflow: business process or feature
team: accountable engineering/product/business team
department: higher-level organization
cost_center: finance ownership
```

Example event:

```json
{
  "user_id": "ana@company.com",
  "user_name": "Ana Lopez",
  "team": "support-ops",
  "department": "operations",
  "app": "support-copilot",
  "workflow": "ticket-summary",
  "provider": "openai",
  "model": "gpt-4o-mini"
}
```

## Implementation Modes

### Mode 1: Local Demo

Best for product evaluation.

```bash
cp .env.example .env
docker compose up --build
```

Open:

```text
http://localhost:3000
```

Click **Seed demo data**.

### Mode 2: Direct Observer Events

Best for quick app instrumentation when LiteLLM callback behavior is not ready.

Application flow:

```text
app calls LLM
  -> reads usage from provider response
  -> POST /api/events
```

This proves attribution and dashboard value with minimal moving parts.

### Mode 3: LiteLLM Gateway With Virtual Keys

Best target for production.

Application flow:

```text
app uses OpenAI-compatible client
  -> base_url = https://llm-gateway.company.com/v1
  -> api_key = LiteLLM virtual key
  -> request includes metadata
  -> LiteLLM calls provider with corporate provider key
  -> LiteLLM callback posts Observer event
```

For OpenAI-compatible clients, the app change should be small:

```python
from openai import OpenAI

client = OpenAI(
    base_url="https://llm-gateway.company.com/v1",
    api_key="sk-user-or-app-virtual-key",
)
```

## User Sync

Start with CSV for low-friction pilots:

```bash
python samples/sync_users.py
```

For production, sync from the company identity source:

- Microsoft Entra ID
- LDAP / Active Directory
- Okta
- HRIS
- CSV export as a transitional option

Minimum fields:

```text
user_id
user_name
email
role
team
department
active
```

Useful endpoint:

```text
POST /api/users/sync
```

## Virtual Keys

There are two practical paths:

- **Observer local key**: works in the Tiny MVP without LiteLLM Postgres. Good for modeling identity and future budgets.
- **LiteLLM real virtual key**: accepted by the LiteLLM gateway. Requires LiteLLM key management with Postgres.

### Path A: Local Observer Key

Use this first if you only want to validate the Observer ownership model.

```bash
python samples/request_virtual_key.py --user-id demo.user@company.com
```

Observer returns the key once and stores only a hash plus prefix.

This key is not yet accepted by LiteLLM. It is useful for proving the product model:

```text
synced user
  -> virtual key metadata
  -> future budget/model policy
  -> dashboard ownership
```

### Path B: Real LiteLLM Virtual Key

Use this when you want an app to call LiteLLM with a virtual key instead of the master key.

LiteLLM requires Postgres for key management. This repo includes a local override file to make that test low-friction:

```bash
docker compose -f docker-compose.yml -f docker-compose.litellm-keys.yml up --build
```

This starts:

```text
observer-api
observer-frontend
litellm-proxy
litellm-db
```

The override file gives LiteLLM:

```text
DATABASE_URL=postgresql://litellm:litellm@litellm-db:5432/litellm
```

and mounts:

```text
litellm/config.with-keys.yaml
```

That config uses LiteLLM's documented key-management settings:

```yaml
general_settings:
  master_key: os.environ/LITELLM_MASTER_KEY
  database_url: os.environ/DATABASE_URL
```

Required LiteLLM settings:

```text
DATABASE_URL=postgresql://...
LITELLM_MASTER_KEY=sk-...
```

### Step-By-Step Local Virtual Key Test

1. Copy env and add a provider key.

```bash
cp .env.example .env
```

Set:

```text
OPENAI_API_KEY=your-provider-key
LITELLM_MASTER_KEY=sk-litellm-master-key
```

2. Start the Postgres-backed LiteLLM key-management stack.

```bash
docker compose -f docker-compose.yml -f docker-compose.litellm-keys.yml up --build
```

3. Sync demo users into Observer.

```bash
python samples/sync_users.py
```

4. Ask Observer to request a real LiteLLM virtual key.

```bash
python samples/request_virtual_key.py --user-id demo.user@company.com --try-litellm
```

Expected output:

```text
Virtual key issued. Store it securely; Observer only returns it once.
key: sk-...
source: litellm
user: demo.user@company.com
team: data-platform
```

If `source` is `observer_local`, LiteLLM did not generate the key. Read the `LiteLLM note` line printed by the script.

5. Test the key against LiteLLM.

PowerShell:

```powershell
$env:LITELLM_VIRTUAL_KEY="sk-returned-by-request-virtual-key"
python samples\call_openai_via_litellm.py
```

The sample uses `LITELLM_VIRTUAL_KEY` first, then `LITELLM_API_KEY`, then `LITELLM_MASTER_KEY`.

Or use cURL:

```bash
curl http://localhost:4040/v1/chat/completions \
  -H "Authorization: Bearer sk-returned-by-request-virtual-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o-mini",
    "messages": [
      {"role": "user", "content": "Say hello in one short sentence."}
    ],
    "metadata": {
      "user_id": "demo.user@company.com",
      "team": "data-platform",
      "department": "engineering",
      "app": "sample-app",
      "workflow": "virtual-key-smoke-test"
    }
  }'
```

6. Verify Observer.

Open:

```text
http://localhost:3000/#events
```

You should see an event with:

```text
source=litellm
user/team/app/workflow metadata
provider/model
tokens
cost
```

### Direct LiteLLM Key Creation

If you want to bypass Observer and prove LiteLLM itself first:

```bash
curl -X POST http://localhost:4040/key/generate \
  -H "Authorization: Bearer sk-litellm-master-key" \
  -H "Content-Type: application/json" \
  -d '{
    "models": ["gpt-4o-mini"],
    "user_id": "demo.user@company.com",
    "metadata": {
      "team": "data-platform",
      "department": "engineering",
      "app": "sample-app",
      "workflow": "manual-key-test"
    },
    "max_budget": 5,
    "budget_duration": "30d"
  }'
```

Then use the returned `sk-...` as the API key against:

```text
http://localhost:4040/v1
```

### Practical Troubleshooting

If `/key/generate` returns unauthorized:

```text
Check LITELLM_MASTER_KEY.
It must match the Authorization Bearer token.
It should start with sk-.
```

If `/key/generate` fails with database errors:

```text
Check that litellm-db is healthy.
Check DATABASE_URL.
Start with docker-compose.litellm-keys.yml.
```

If the key is generated but model calls fail:

```text
Check OPENAI_API_KEY or the provider key for the selected model.
Check that the generated key allows model gpt-4o-mini.
```

If the LLM call works but Observer does not show an event:

```text
Check litellm-proxy logs.
Check OBSERVER_API_URL=http://observer-api:8080 inside Docker.
Use samples/call_openai_via_litellm.py --also-send-observer-event as fallback.
```

LiteLLM virtual keys can carry ownership metadata and, in later iterations, budgets, model restrictions and rate limits.

Reference: https://docs.litellm.ai/docs/proxy/virtual_keys

## Plug-And-Play Rollout

1. Deploy Observer API, dashboard and LiteLLM gateway.
2. Put provider API keys only in the LiteLLM environment.
3. Choose company URLs for dashboard, API and gateway.
4. Sync users from CSV or identity provider.
5. Generate virtual keys for pilot users/apps/teams.
6. Update pilot apps to use the LiteLLM base URL and virtual key.
7. Ensure each app sends user/team/app/workflow metadata.
8. Validate a real LLM call appears in Events with cost and identity.
9. Review Developers, Teams and Hygiene.
10. Add budgets, auth/RBAC, Postgres and migrations before broad rollout.

## UAT Checklist

- Dashboard opens from the company URL.
- API health endpoint returns `ok`.
- LiteLLM gateway accepts a virtual key.
- A pilot app can call a real model through LiteLLM.
- The event appears in Observer.
- Event has user, team, department, app and workflow.
- Cost is calculated and marked as estimated.
- Developers and Teams pages aggregate the event correctly.
- Hygiene issues are understandable and actionable.
- No provider API key is stored in application code.

## Important Limitations

- A shared provider API key alone is not enough for per-user attribution.
- Provider billing exports are still the final source of truth for invoices.
- Observer costs are operational estimates until reconciled with billing.
- Current MVP uses SQLite; production should use Postgres.
- Current MVP has no auth/RBAC; production must restrict dashboard, API and Swagger.
- LiteLLM real virtual-key persistence requires Postgres.

## Production Hardening Path

Recommended order:

1. Postgres for Observer storage.
2. Alembic migrations.
3. LiteLLM Postgres key management.
4. Real virtual keys per user/team/app.
5. Auth/RBAC for dashboard and API.
6. Budgets and model access policies.
7. Billing reconciliation.
8. Alerting and audit logs.
9. OpenTelemetry ingestion.
10. Deployment automation.
