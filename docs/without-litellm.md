# Running this checkout without LiteLLM

This branch replaces LiteLLM with direct HTTP requests using the existing
`requests` dependency. Analysis, translation and AI filtering share this client.
LiteLLM and its otherwise unused dependencies have been removed from `uv.lock`.
This change does not audit or upgrade the remaining dependencies.

## Configure the endpoint

In `config/config.yaml`, configure a server supporting non-streaming
`POST /v1/chat/completions`, for example Ollama running local models:

```yaml
ai:
  model: "llama3.2:3b"  # Must already be installed on your model server.
  api_base: "http://192.168.1.50:11434/v1"  # Replace with your model server.
  api_key: ""
  timeout: 120
  max_tokens: 5000
  num_retries: 1
  fallback_models: []
```

The model server is separate; this checkout does not install Ollama or download
models. In Docker, localhost means the TrendRadar container, not your homeserver.
The sample config uses `ollama` as a service/host name; replace it if unavailable.
For authenticated endpoints, use HTTPS and supply `AI_API_KEY` in the container
instead of committing it to YAML. HTTP with a nonempty key is accepted only for
loopback hosts. Local keyless endpoints need no placeholder API key.

Set `ai_analysis.language: "English"` and `ai_analysis.include_rss: true` for
English RSS analysis. Translation is separately controlled by `ai_translation`.
Collection, retention and notification schedules keep their upstream behavior;
this change does not add weekly report synthesis.

Compatibility changes:

- Set `ai.api_base` explicitly. There are no implicit cloud/provider endpoints.
- Model IDs are passed as-is, except legacy `openai/`, `ollama/`, and `deepseek/`
  prefixes are stripped. Organization/model names otherwise retain their slash.
- Native Anthropic/Gemini APIs are not supported directly; an independently
  configured compatible endpoint is required.
- Retries cover connection errors, HTTP 408/429 and 5xx responses. Fallbacks
  are model IDs on the **same endpoint**, not other providers.
- `extra_params` supports additional JSON fields and `extra_headers`; it cannot
  change endpoint, credentials, core model/messages, or enable streaming.
- Redirects are rejected. Ambient proxy, custom CA environment variables and
  `.netrc` authentication are not used (`Session.trust_env = False`).
- Error messages omit server response bodies and connection exception details.

## Build your modified image

Do not use `wantcat/trendradar:latest` for this branch: it contains upstream code.
From the repository root on a Docker host:

```sh
docker build --build-arg TARGETARCH=amd64 -f docker/Dockerfile -t trendradar-local:no-litellm .
```

The ZimaBoard uses amd64. The upstream Dockerfile uses the checked-in lockfile.
Verify the resulting image before deployment:

```sh
docker run --rm --entrypoint python trendradar-local:no-litellm -c 'import importlib.util; assert importlib.util.find_spec("litellm") is None; from trendradar.ai.client import AIClient; print("HTTP client loads; LiteLLM absent")'
```

Build on the ZimaBoard, or transfer the image with `docker save` / `docker load`.
Use `image: trendradar-local:no-litellm` in your ZimaOS custom app, retaining the
config and output mounts described in the upstream installation guide. Do not
start the optional MCP container for ordinary feed collection/analysis. Keep
report access private and back up both configuration and output.

If dependencies were previously installed, use a fresh virtual environment or
fresh image. A manually upgraded environment can still contain old packages.

## Validation

The HTTP tests can run without the other app dependencies, using Python with
`requests` installed:

```sh
python -m unittest discover -s tests -p test_ai_extra_params.py -v
uv lock --check --offline
```

A real model request and Docker image build still need to be checked on the
intended deployment host. No provider keys are needed for the unit tests.
