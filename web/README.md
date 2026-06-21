# lede - Next.js viewer

1:1 port of the Streamlit UI in Next.js 14 (App Router) + Tailwind. Reads
data from the parent repo's `data/` and `config/` directories at build / SSR time.

## Local dev

```bash
cd web
npm install
npm run dev
# → http://localhost:3000
```

The dev server reads JSONL files from `../data/` and the YAML config from
`../config/` of the parent repo. No copying needed.

## Deploy to Vercel

```bash
# from inside web/
npx vercel
```

Configuration:
- **Framework**: Next.js (auto-detected)
- **Root directory**: `web`
- **Build command**: `npm run build`
- **Install command**: `npm install`

After deploy, add `lede.io` in Vercel → Settings → Domains.

## What's the same as Streamlit

- Three views: Curate / Edition / Backtest, URL-routed
- Identical dark palette, Inter font, monospace where it adds clarity
- Per-newsletter section grouping with target_count caps
- Score breakdown, HN signal, freshness, source-weight boosts in detail pane
- Edition view with capacity progress, per-section approved stories, .txt export
- Backtest hero + per-newsletter table with 7-day sparklines + side-by-side compare

## What's different

- Clicking a story row is instant (client-side navigation, no server rerun)
- Approve / reject persists to `localStorage` instead of server-side JSONL
- The deployed UI is read-only on the pipeline data - generation still runs locally
- No background pipeline orchestration in the web app (kept in the Python CLI)
