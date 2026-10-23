# ZimaOS deployment

Run these commands in ZimaOS's terminal/SSH, from this repository's root.
Requires Docker Compose. This uses locally built images from this modified source,
not upstream TrendRadar images. There is no MCP service or per-article AI.

## Build and start collection

```sh
export TECHRADAR_BIND_IP=100.75.162.16
export TECHRADAR_DATA_DIR=/DATA/AppData/techradar
docker compose -f deploy/zima/compose.yml build collector weekly
# Create writable reports directory for the unprivileged weekly runner.
docker compose -f deploy/zima/compose.yml run --rm --entrypoint sh collector \
  -c 'mkdir -p /app/output/weekly && chown 1000:1000 /app/output/weekly'
docker compose -f deploy/zima/compose.yml up -d collector
docker compose -f deploy/zima/compose.yml logs --tail=80 collector
```

Open http://100.75.162.16:8088/ to browse collection reports and saved briefings.
Binding to that IP requires the address to exist on the ZimaOS host. If Docker
reports "cannot assign requested address", inspect the host addresses and use
its actual interface address. Do not change it to 0.0.0.0 by default.

The included sources are arXiv AI/ML/NLP, vLLM releases and llama.cpp releases.
Collection runs every six hours. Edit `deploy/zima/config.yaml` for more sources.
Data is retained indefinitely under `/DATA/AppData/techradar/output`; back it up.
Generated briefings, source manifests and prompts are accessible through the
report server, so restrict access to trusted devices on your network/Tailscale.

## Authenticate the separate Codex runner

```sh
docker compose -f deploy/zima/compose.yml run --rm --entrypoint codex weekly \
  -c 'cli_auth_credentials_store="file"' login --device-auth
docker compose -f deploy/zima/compose.yml run --rm --entrypoint codex weekly login status
```

Complete the sign-in in your browser. Do not paste login codes, tokens or auth
files into chats or GitHub. Login persists in a dedicated Docker volume.

Check collected input without using subscription quota:

```sh
docker compose -f deploy/zima/compose.yml run --rm weekly \
  --data-dir /data --archive-dir /reports --codex-home /auth --dry-run
```

The default window ends yesterday; immediately after first collection there may
be no records yet. For an immediate test, add `--end-date YYYY-MM-DD` using today's
Zurich date. Once satisfied, remove `--dry-run` for one real request. To generate
the normal weekly edition:

```sh
docker compose -f deploy/zima/compose.yml run --rm weekly
```

Run that once each Monday at 09:00 Europe/Zurich using a persistent scheduler.
It covers the previous Monday–Sunday. The Compose app currently provides a
one-shot weekly runner; automatic scheduling must be configured separately.
Subscription rate limits, login expiry and sandbox support still need testing
on the deployment host. Existing editions are not overwritten.

If Codex cannot initialize its read-only sandbox inside this container, keep
collection running and investigate the host's sandbox support. Do not disable
sandboxing or make the container privileged as a workaround.
