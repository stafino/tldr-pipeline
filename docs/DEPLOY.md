# Deployment

The pipeline has two pieces with different deployment shapes:

1. **Pipeline** (ingest → dedup → rank → blurbs → format) — runs the Claude CLI against your Claude Code subscription. **Must run locally** because OAuth tokens only work on your machine.
2. **Streamlit UI** — read-only viewer of the data the pipeline produced. **Deployable** to Streamlit Community Cloud, Fly.io, Render, etc.

The cron job (`scripts/cron-refresh.sh`) runs every 6 hours on your Mac, refreshes the pipeline, commits the data files to git, and pushes. The deployed Streamlit auto-pulls on each refresh and shows the latest issues.

## Local cron (already installed)

The launchd job is installed at `~/Library/LaunchAgents/com.tldr.pipeline.refresh.plist` and loaded. It runs:
- Immediately on system boot (`RunAtLoad`)
- Every 6 hours after that (`StartInterval 21600`)

### Useful commands

```bash
# Status
launchctl list | grep com.tldr.pipeline

# Stop / unload
launchctl unload ~/Library/LaunchAgents/com.tldr.pipeline.refresh.plist

# Reload after changes
launchctl unload ~/Library/LaunchAgents/com.tldr.pipeline.refresh.plist
launchctl load ~/Library/LaunchAgents/com.tldr.pipeline.refresh.plist

# Trigger now (don't wait 6h)
launchctl kickstart -k gui/$UID/com.tldr.pipeline.refresh

# Tail logs
tail -f data/logs/cron-*.log
tail -f data/logs/launchd.stderr.log
```

### What the cron does

1. cd into the repo
2. Source `.env` so `LLM_BACKEND=cli` applies
3. Run `./tldr refresh` (full pipeline)
4. If any data changed, commit `data/blurbs`, `data/scored`, `data/issues` and push
5. Rotate logs (keep last 30 runs)

The cron does **not** commit the intermediate `data/raw` or `data/deduped` files — those are large and regenerable.

## Streamlit Cloud deployment

### One-time setup

1. Go to https://share.streamlit.io and sign in with GitHub.
2. **New app** → select repo `stafino/tldr-pipeline`, branch `main`, main file `ui/app.py`.
3. Advanced settings:
   - Python version: 3.11
   - Secrets: leave empty (the deployed app doesn't need ANTHROPIC_API_KEY because it's read-only)
4. Deploy. First boot takes ~3 min while it installs Python deps.

Streamlit Cloud auto-redeploys on every push to `main`, including the cron's data commits. The deployed app reads the same JSONL files your local pipeline writes.

### What works on the deployed instance

| Feature | Works? | Notes |
|---|---|---|
| Browse stories per newsletter | ✓ | Reads `data/scored/<date>.jsonl` |
| View blurbs / issue preview | ✓ | Reads `data/blurbs/<date>.jsonl` |
| Approve / reject in the UI | partial | Saves to in-session state but doesn't persist across deploys (Streamlit Cloud filesystem is ephemeral) |
| Regenerate a blurb | ✗ | Would need `claude` CLI or `ANTHROPIC_API_KEY` |
| Run the pipeline on-demand | ✗ | Same reason |

For the TLDR demo, this is fine — the deployed UI is the audience-facing artifact; the curator workflow happens locally.

## Alternative deployment targets

### Fly.io (free tier, decent for demos)

```bash
fly launch --image python:3.11-slim
# Then add a Dockerfile and a fly.toml — see Fly's docs
```

Same constraint: no Claude CLI, so the pipeline only runs in CI / locally.

### Render

Free tier is fine for static-ish Streamlit. Same constraint.

### Local tunnel (simplest "live demo")

If you don't want to deal with cloud, expose your local Streamlit:

```bash
# install cloudflared once
brew install cloudflared

# expose port 8501
cloudflared tunnel --url http://localhost:8501
```

You get a public URL like `https://wild-name.trycloudflare.com` that proxies to your local Streamlit. This gets you the live pipeline + full functionality (since claude CLI works locally). Downsides: URL changes on restart unless you sign up; depends on your Mac being awake.

## If you'd rather pay per token instead of using the subscription

The cron can also run with the API backend. Edit `.env`:

```bash
LLM_BACKEND=api
ANTHROPIC_API_KEY=sk-ant-...
```

Then the cron uses the API, no subscription dependency, and the same pipeline can run in any environment (including a deployed instance via GitHub Actions or a Fly.io cron). Cost: ~$5-15 per full refresh in API mode (Sonnet for ranking + Opus for blurbs).

## Troubleshooting

**Cron didn't fire**: check `data/logs/launchd.stderr.log` for permission errors. macOS may have blocked it on first run — go to System Settings → Privacy & Security → Login Items, find the agent.

**Cron fires but `claude` CLI fails**: launchd uses a minimal PATH. The wrapper script sets `/opt/homebrew/bin:/usr/local/bin:...`. If your `claude` is elsewhere, edit `scripts/cron-refresh.sh` line 14 to add its directory.

**Streamlit Cloud build fails on `torch`**: torch is heavy. If Streamlit Cloud's build timeout is hit, switch to a lighter embedding model (e.g., drop sentence-transformers and use `fastembed` or hash-based dedup). The deployed UI doesn't actually need torch — only the dedup step does, and dedup runs locally.
