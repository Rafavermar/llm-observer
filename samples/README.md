# Samples

Install local sample dependencies:

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

Send one fake normalized event:

```bash
python samples/send_fake_event.py
```

Call a real model through LiteLLM Proxy:

```bash
python samples/call_openai_via_litellm.py
```

To use a LiteLLM virtual key instead of the master key:

```bash
LITELLM_VIRTUAL_KEY=sk-your-virtual-key python samples/call_openai_via_litellm.py
```

On Windows PowerShell:

```powershell
$env:LITELLM_VIRTUAL_KEY="sk-your-virtual-key"
python samples\call_openai_via_litellm.py
```

If the LiteLLM callback does not fire in your local image, use the direct fallback:

```bash
python samples/call_openai_via_litellm.py --also-send-observer-event
```

Sync sample users into Observer:

```bash
python samples/sync_users.py
```

Request a local Observer virtual key:

```bash
python samples/request_virtual_key.py --user-id demo.user@company.com
```

Try real LiteLLM key generation only after LiteLLM key management has Postgres configured:

```bash
python samples/request_virtual_key.py --user-id demo.user@company.com --try-litellm
```

