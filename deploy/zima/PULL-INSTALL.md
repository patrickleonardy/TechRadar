# Install by pulling containers

The repository's **Publish TechRadar containers** GitHub Actions workflow builds
amd64 images for ZimaBoard and publishes these tags:

- `ghcr.io/patrickleonardy/techradar:collector`
- `ghcr.io/patrickleonardy/techradar:codex`

Check the workflow is successful before trying to pull. GitHub Container Registry
packages may initially be private even for public repositories. In your GitHub
profile's Packages page, open the `techradar` container package, then Package
settings, and set visibility to Public if you want unauthenticated pulls.

The workflow also publishes `collector-COMMIT_SHA` and `codex-COMMIT_SHA` tags.
Use a known commit tag or image digest instead of the moving tags when you want
updates to be deliberate. Existing upstream `wantcat/trendradar` images do not
contain these modifications.

## ZimaOS GUI

1. Download `compose-pull.yml` from this folder.
2. On your own device, replace both occurrences of
   `${TECHRADAR_BIND_IP:-127.0.0.1}` with the server's private/Tailscale IP.
   Keep the real address out of the public repository.
3. In ZimaOS, use **Install a customized app → Import → Docker Compose**.
4. Paste the YAML, review ports and named volumes, and install.

The collector runs every six hours; per-article AI, notifications and MCP are
not enabled. Persistent volumes hold config, article databases, briefings and
Codex authentication separately. Default feeds cover arXiv AI/ML/NLP, vLLM and
llama.cpp releases. Collector reports are on port 8088. Weekly briefing files
are on port 8089. Restrict access to trusted devices: reports contain source
records and prompts.

The `weekly` service is manual. Some ZimaOS import versions may ignore Compose
profiles. If it starts before authentication, it will fail without publishing a
briefing; it has no restart policy. GUI import compatibility must be checked on
your ZimaOS version. The terminal workflow below is more predictable.

## Terminal (no source checkout or local build)

Download the Compose file to a persistent directory, then run:

```sh
export TECHRADAR_BIND_IP=YOUR_SERVER_IP
docker compose -f compose-pull.yml pull collector weekly reports
docker compose -f compose-pull.yml up -d collector reports
```

Login once into the dedicated authentication volume:

```sh
docker compose -f compose-pull.yml run --rm --entrypoint codex weekly \
  -c 'cli_auth_credentials_store="file"' login --device-auth
```

Complete the browser sign-in with your ChatGPT subscription. Do not share codes
or tokens. Check input without spending subscription quota:

```sh
docker compose -f compose-pull.yml run --rm weekly \
  --data-dir /data --archive-dir /reports --codex-home /auth --dry-run
```

The normal report window ends yesterday. On the first collection day there may
be no matching data yet; add `--end-date YYYY-MM-DD` (today's date) for a test.
Remove `--dry-run` to make a real request, or use the default arguments:

```sh
docker compose -f compose-pull.yml run --rm weekly
```

Schedule that command every Monday at 09:00 Europe/Zurich with a persistent
scheduler for automatic weekly editions. Scheduling and a real Codex login/model
request still need validation on your server. Container sandbox limitations may
require investigation; don't bypass the sandbox or use privileged mode.

Named config volumes are initialized from the image on first creation. Updating
the image won't overwrite your config. Back up the named volumes; do not use
`docker compose down -v` unless you intend to delete data and authentication.
