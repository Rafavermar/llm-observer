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

