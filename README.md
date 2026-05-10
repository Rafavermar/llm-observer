# LLM Observer Tiny MVP

LLM Observer Tiny MVP is a local, plug-and-play prototype for monitoring LLM usage across apps, users, teams and providers. It ingests normalized LLM events, stores them in SQLite, calculates token cost and hygiene issues, and shows everything in a dark local dashboard.

The first successful milestone is simple:

```text
Run one real LLM call through LiteLLM and see it appear in the dashboard with tokens, cost and hygiene context.
```

## 1. What This Is

- A small working foundation for an LLM observability product.
- A local FastAPI backend with stable event APIs.
- A SQLite storage layer that can later be replaced by Postgres.
- A static HTML dashboard served by nginx.
- A LiteLLM Proxy integration with a custom Observer callback.
- Sample scripts for fake events and real OpenAI-compatible calls.

## 2. What This Is Not

- Not the final enterprise product.
- No authentication, SSO or RBAC yet.
- No Postgres or migrations yet.
- No Kubernetes, Terraform or cloud dependency.
- No heavy frontend framework or frontend build chain.

## 3. Architecture

```text
sample app or script
        |
        | normalized event
        v
Observer API: FastAPI on :8080
        |
        | SQLite file
        v
data/observer.db
        ^
        |
LiteLLM Proxy on :4040
        |
        | optional provider API call
        v
OpenAI-compatible provider

Dashboard on :3000
        |
        | reads Observer API
        v
summary, events, developers, teams, hygiene
```

## 4. Requirements

- Docker and Docker Compose.
- Python 3.11+ if you want to run sample scripts or tests locally.
- Optional: an OpenAI-compatible API key for real model calls.

## 5. Quick Start Without API Keys

```bash
cp .env.example .env
docker compose up --build
```

On Windows PowerShell:

```powershell
Copy-Item .env.example .env
docker compose up --build
```

Open:

```text
http://localhost:3000
```

Click **Seed demo data**. The dashboard should show cost, token volume, cache hit rate, developer rows, team rows and hygiene issues.

Health check:

```text
http://localhost:8080/health
```

Expected response:

```json
{
  "status": "ok",
  "db": "ok"
}
```

## 6. Quick Start With OpenAI Key

Edit `.env`:

```text
OPENAI_API_KEY=your-key-here
```

Restart LiteLLM:

```bash
docker compose restart litellm-proxy
```

Install sample dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install requests openai
```

On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install requests openai
```

Run a real call through LiteLLM:

```bash
python samples/call_openai_via_litellm.py
```

Then refresh the dashboard at:

```text
http://localhost:3000/#events
```

If the LiteLLM callback does not fire in your image version, use the direct fallback:

```bash
python samples/call_openai_via_litellm.py --also-send-observer-event
```

## 7. Send A Fake Event

With the API running:

```bash
python samples/send_fake_event.py
```

The script posts to:

```text
http://localhost:8080/api/events
```

Override with:

```bash
OBSERVER_PUBLIC_API_URL=http://localhost:8080 python samples/send_fake_event.py
```

On Windows PowerShell:

```powershell
$env:OBSERVER_PUBLIC_API_URL="http://localhost:8080"
python samples/send_fake_event.py
```

## 8. Real LLM Call Through LiteLLM

LiteLLM Proxy runs on:

```text
http://localhost:4040/v1
```

The sample uses the OpenAI Python SDK with:

```python
client = OpenAI(
    base_url="http://localhost:4040/v1",
    api_key=os.getenv("LITELLM_MASTER_KEY", "sk-litellm-master-key"),
)
```

The LiteLLM callback in `litellm/observer_callback.py` normalizes callback payloads and posts them to:

```text
http://observer-api:8080/api/events
```

Reference for the custom callback pattern: https://docs.litellm.ai/docs/proxy/logging

## 9. View Events In Dashboard

Open:

```text
http://localhost:3000
```

Sections:

- Overview: KPIs and charts.
- Events: latest raw normalized events with filters.
- Developers: per-user aggregates.
- Teams: team aggregates and top issue.
- Hygiene: active issues, affected users and fix snippets.
- Settings: API base URL, connection test and manual fake event.

The frontend defaults to:

```text
http://localhost:8080
```

You can change the API base in Settings. The value is stored in browser `localStorage`.

## 10. API Contract

### GET /health

```json
{
  "status": "ok",
  "db": "ok"
}
```

### POST /api/events

Request:

```json
{
  "ts": "2026-05-08T10:30:00Z",
  "source": "litellm",
  "user_id": "demo.user@company.com",
  "user_name": "Demo User",
  "team": "data-platform",
  "department": "engineering",
  "app": "sample-app",
  "workflow": "demo-call",
  "provider": "openai",
  "model": "gpt-4o-mini",
  "input_tokens": 1234,
  "output_tokens": 220,
  "cached_tokens": 0,
  "latency_ms": 1840,
  "status": "success",
  "retry_count": 0,
  "request_id": "abc123",
  "raw": {}
}
```

Response includes the stored event plus:

- `id`
- `total_tokens`
- `cost_input`
- `cost_cached`
- `cost_output`
- `total_cost`
- `cache_hit`
- `context_ratio`
- `model_tier`
- `hygiene_flags`

### GET /api/events

Query params:

- `limit`, default `100`
- `offset`, default `0`
- `since`
- `user_id`
- `team`
- `provider`
- `model`

Response:

```json
{
  "items": [],
  "count": 0
}
```

### Other Endpoints

- `GET /api/summary`
- `GET /api/developers`
- `GET /api/teams`
- `GET /api/hygiene/issues`
- `POST /api/demo/seed`
- `POST /api/demo/clear`

Seed request:

```json
{
  "count": 500
}
```

## 11. Pricing

Prices are in `api/app/pricing.py` and are expressed per 1M tokens. The current catalog is an operational estimate for the MVP, not a replacement for provider billing exports.

Formula:

```text
cost_input = (input_tokens - cached_tokens) * input_price / 1_000_000
cost_cached = cached_tokens * cached_price / 1_000_000
cost_output = output_tokens * output_price / 1_000_000
total_cost = cost_input + cost_cached + cost_output
```

Included models:

- OpenAI: `gpt-4o`, `gpt-4o-mini`
- Anthropic: `claude-3-5-sonnet`, `claude-3-haiku`
- Azure OpenAI: `gpt-4o`
- Databricks: `dbrx-instruct`, `llama-3-70b`

Unknown provider or model combinations do not crash. They return zero cost with a pricing warning in the enriched response.

Pricing governance:

- The catalog includes `pricing_source`, `pricing_unit` and `pricing_last_verified` metadata in API responses.
- OpenAI model prices should be checked against the official OpenAI model/pricing docs.
- Anthropic entries in this MVP include legacy aliases and must be verified against current Anthropic API pricing before production use.
- Azure OpenAI pricing varies by deployment type, region, data zone and commercial agreement; use Azure Pricing Calculator or the Azure Retail Prices API for production-grade estimates.
- Databricks Foundation Model pricing is published as DBU consumption; USD cost depends on the customer's DBU rate and should be reconciled with Databricks billing.
- Production should add billing reconciliation jobs so estimated Observer cost and provider invoice totals can be compared.

## 12. Hygiene Rules

Company score starts at `100`.

Deductions:

- Cache hit rate below `0.30`: minus `25`
- Average context ratio above `0.85`: minus `20`
- Retry rate above `0.05`: minus `15`
- Premium short-output rate above `0.20`: minus `20`

Active issue rules:

- `H01` Context Bloat
- `H02` Caching Not Active
- `H03` Premium Model Overuse
- `H04` Verbose Instructions
- `H05` High Retry Rate
- `H06` Possible JSON Bloat
- `H07` Long Unstructured Output
- `H08` Large Context, No Cache

Demo seed data intentionally generates enough usage to show `H01`, `H02`, `H03`, `H05` and `H08`.

## 13. Troubleshooting

### LiteLLM starts but model call fails

Check `.env`:

```text
OPENAI_API_KEY=
```

If it is empty, the dashboard and demo seed still work. Real provider calls need a real key.

### Observer API unreachable from callback

Inside Docker, the callback uses:

```text
OBSERVER_API_URL=http://observer-api:8080
```

Check:

```bash
docker compose logs observer-api
docker compose logs litellm-proxy
```

### CORS errors

The API allows local development origins:

```text
http://localhost:3000
http://127.0.0.1:3000
```

Production should restrict CORS origins to the real dashboard domain.

### Empty dashboard

Click **Seed demo data** or run:

```bash
python samples/send_fake_event.py
```

Also verify the dashboard Settings API base URL is:

```text
http://localhost:8080
```

### SQLite file permissions

The API writes to:

```text
data/observer.db
```

Docker mounts it as:

```yaml
./data:/data
```

If the API logs SQLite permission errors, delete only local generated database files after stopping Compose:

```bash
docker compose down
```

Then remove `data/observer.db` using your file manager or shell and restart.

### Callback does not fire

Use the fallback event path:

```bash
python samples/call_openai_via_litellm.py --also-send-observer-event
```

This still proves the first milestone: real usage, token accounting, calculated cost and dashboard visibility.

## 14. Evolve To Production

Recommended next iterations:

- Replace SQLite with Postgres.
- Add Alembic migrations.
- Add auth/RBAC.
- Add LiteLLM virtual keys per user/team/app.
- Add budgets and quota policies.
- Add alerting for cost spikes and hygiene regressions.
- Add OpenTelemetry ingestion.
- Add GitHub and M365 pollers for ownership context.
- Add Helm/Terraform only when deployment shape is clear.
- Add CI/CD with tests, linting and container build checks.

## Run Tests

```bash
cd api
pytest
```

## Repository Layout

```text
llm-observer/
  README.md
  LICENSE
  docker-compose.yml
  .env.example
  .gitignore
  api/
  frontend/
  litellm/
  samples/
  data/
```

