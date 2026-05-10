# LiteLLM Integration

This directory contains the local LiteLLM Proxy configuration and the Observer callback.

The config uses LiteLLM's documented custom callback pattern:

```yaml
litellm_settings:
  callbacks: observer_callback.proxy_handler_instance
```

The callback extracts model, provider, usage, latency and metadata from LiteLLM callback payloads, normalizes them to the Observer event contract, and posts them to:

```text
${OBSERVER_API_URL}/api/events
```

The callback is intentionally defensive:

- Missing usage defaults to zero tokens.
- Unknown models still create Observer events with zero cost on the API side.
- Posting to Observer has a short timeout.
- Callback exceptions are logged and swallowed so the LLM call is not broken.

Validate the callback by running:

```bash
cp .env.example .env
docker compose up --build
python samples/call_openai_via_litellm.py
```

If the callback does not fire in your LiteLLM image version, use:

```bash
python samples/call_openai_via_litellm.py --also-send-observer-event
```

Reference: https://docs.litellm.ai/docs/proxy/logging

## Virtual Keys

The current local Compose stack keeps LiteLLM simple so the demo works without Postgres. Observer can still sync users and issue local development keys through:

```text
POST /api/users/sync
POST /api/virtual-keys
```

Real LiteLLM virtual keys require LiteLLM key management with a Postgres `DATABASE_URL`, then `/key/generate` authenticated with `LITELLM_MASTER_KEY`.

Local low-friction test:

```bash
docker compose -f docker-compose.yml -f docker-compose.litellm-keys.yml up --build
python samples/sync_users.py
python samples/request_virtual_key.py --user-id demo.user@company.com --try-litellm
```

The override compose file starts a local `litellm-db` Postgres service and mounts:

```text
litellm/config.with-keys.yaml
```

Reference: https://docs.litellm.ai/docs/proxy/virtual_keys

