# Weekly briefings with your Codex CLI login

TechRadar collects feeds throughout the week. A separate, single `codex exec` run
turns the stored titles/excerpts into a weekly briefing. There is no LiteLLM,
OpenAI API key, provider proxy, or API SDK in this runner. It uses the CLI's saved
ChatGPT login and is subject to your plan's usage limits and model availability.
The source records are sent to OpenAI for summarization; this is not local inference.

This does not replace the per-article HTTP client: disable `ai_analysis` and
`ai_translation`, and use `filter.method: keyword` in the collector configuration
if you want Codex to be the only AI component. Keep RSS collection enabled and
`storage.local.retention_days: 0`. Collect daily, not just on briefing day.

Official references:
- https://learn.chatgpt.com/docs/auth
- https://learn.chatgpt.com/docs/non-interactive-mode

## Native Linux runner

Requires Python 3.12+ (standard library only) and Codex CLI supporting
`--ignore-user-config`, `--ignore-rules`, `--ephemeral` and `--output-last-message`.
The invocation flags were checked against Codex CLI 0.163.0. No real model request
was made during development.

Create a dedicated authentication directory and sign in interactively:

```sh
mkdir -p "$HOME/.techradar-codex"
CODEX_HOME="$HOME/.techradar-codex" codex -c 'cli_auth_credentials_store="file"' login --device-auth
CODEX_HOME="$HOME/.techradar-codex" codex login status
```

Choose ChatGPT/subscription authentication, not an API key. Keep that directory
private and outside the repository; never commit its contents. Use a dedicated
OS account/container without unrelated secrets or personal files. The read-only
sandbox limits writes; it is not a substitute for filesystem isolation.

From the repository root, first check what will be included without calling Codex:

```sh
python3 scripts/weekly_codex.py --data-dir output --dry-run
```

Generate one edition (yesterday plus the six preceding days, Europe/Zurich):

```sh
python3 scripts/weekly_codex.py --data-dir output \
  --codex-home "$HOME/.techradar-codex"
```

Use `--end-date 2026-10-18` to choose an inclusive collection window ending on a
specific date. `--model MODEL_ID` is optional; otherwise Codex selects its default.
`--interests "..."` customizes the briefing. `--max-items` defaults to 150 newest
observed unique URLs, with 500 characters of title and 1,500 of excerpt per item.
The count of omitted items is recorded. It is not a relevance-ranking algorithm.

Each edition contains:

```text
output/weekly/START_END/
  briefing.md   # Briefing with source references
  sources.json  # Exact supplied records, database paths and collection observations
  prompt.txt    # Exact prompt for this edition
```

The script opens collection databases read-only, deduplicates identical URLs
across daily databases, and preserves each source observation. Related stories
with different URLs can be grouped by Codex. Publication dates can be older than
the collection window. Feed summaries may be incomplete; no full-text crawling
or independent verification is performed.

Existing editions are never overwritten. An empty data window, failed CLI call,
timeout, empty response or missing/unknown citation IDs produces an error and no
published edition. Citation-ID validation does not prove that every claim is
supported. No automatic retries are made against your subscription. To regenerate
an edition deliberately, select another `--archive-dir`.

## Docker / ZimaOS runner

The additional image runs only Python and Codex, independently of the collector.
Build this checkout on the ZimaBoard (or build amd64 elsewhere and transfer it):

```sh
docker compose -f docker/docker-compose-codex.yml build weekly
```

If `weekly-reports` was created by root, grant the container's node user (UID 1000)
write access to that directory only. Ensure the collection `output` directory is
readable by that user. Adjust bind-mount paths in the Compose file to match your
ZimaOS persistent storage; `/data` must point at the collector's output folder.

Authenticate into the dedicated named volume:

```sh
docker compose -f docker/docker-compose-codex.yml run --rm --entrypoint codex weekly \
  -c 'cli_auth_credentials_store="file"' login --device-auth
```

Follow the displayed sign-in instructions in your browser. Then run a dry check:

```sh
docker compose -f docker/docker-compose-codex.yml run --rm weekly \
  --data-dir /data --archive-dir /reports --codex-home /auth --dry-run
```

Generate the briefing by running the same command without `--dry-run`:

```sh
docker compose -f docker/docker-compose-codex.yml run --rm weekly
```

The image uses pinned Codex CLI 0.163.0; check release/security information before
upgrading. The image build and actual ChatGPT login/request still need validation
on your deployment host. If container sandbox initialization fails, investigate
that host's sandbox support rather than bypassing it.

For scheduling, use your host's persistent task scheduler. Run the command once
every Monday at 09:00 Europe/Zurich, which covers the previous Monday–Sunday.
For a Linux host running cron in that timezone, an example is:

```cron
0 9 * * 1 cd /ABSOLUTE/PATH/TO/TechRadar && /usr/bin/docker compose -f docker/docker-compose-codex.yml run --rm -T weekly >> /ABSOLUTE/PATH/TO/techradar-weekly.log 2>&1
```

Use the actual Docker path from `command -v docker`. Verify whether your ZimaOS
scheduler persists custom jobs across updates before relying on host cron. The
Compose app itself is a one-shot runner, not an always-running scheduler. Keep
collection running separately. Subscription expiry/rate limits cause a failed
job; review the scheduler log and authenticate again if needed.

## Execution controls

Prompts travel over stdin, not command-line arguments. The CLI runs in a fresh
empty directory with read-only sandboxing, no approvals, no loaded user config or
rules, web search disabled and the shell tool disabled. Only basic runtime env
variables and the dedicated CODEX_HOME are inherited, not API/cloud key variables.
Raw CLI output/errors are not copied into the briefing or logs. Timeouts terminate
the CLI process group on POSIX. Isolation on the deployment host remains essential.

Offline tests (no subscription use):

```sh
python3 -m unittest discover -s tests -p test_weekly_codex.py -v
```
