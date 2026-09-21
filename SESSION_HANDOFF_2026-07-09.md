# Selene Dreams AI Generation — Session Handoff (2026-07-09)

Context dump for continuing work in a new Claude session. Paste the "Quick context" section into the new chat as your first message.

---

## Where things stand right now

The v3 generation pipeline is **live and working**. Flow:

1. Fill a row in the Generation Queue Google Sheet
2. Set Status = "Ready"
3. Apps Script webhook fires → local Flask server (`server.py`) on Marcus's MacBook
4. ngrok exposes local server to internet
5. Server orchestrates: pulls product image from Drive, sends to Nano Banana Pro on Replicate, downloads result, uploads to Drive
6. Sheet updates Status = Done with URLs, or ERROR with reason

## Current tech stack

- **Model**: Nano Banana Pro (`google/nano-banana-pro` on Replicate), with Seedream 5 fallback enabled
- **Interface**: Google Sheet + Apps Script (`trigger.gs`)
- **Server**: Python Flask (`server.py`)
- **Tunnel**: ngrok free tier (URL changes each session — pain point)
- **Storage**: Google Drive folders `01. Product Photos`, `02. Reference Images`, `03. Generated Images` under parent `10. AI Generation`
- **Launcher**: Two `.command` files on Desktop — `Start Selene AI.command` and `Stop Selene AI.command`

## Sheet schema (22 columns)

#, Year, Month, Fabric, Product Type, Variant, Prompt 1–5, Reference Image 1–5, Status, Credits Used, Output Folder, Image URLs, Carousel ID, Notes.

**Cascading dropdowns:**
- Fabric, Month, Status: static ONE_OF_LIST validation
- Product Type + Variant: dynamic per-row via Apps Script (when Fabric changes, PT filters; when PT changes, Variant filters). Baseline "all types/variants" fallback so arrows show on empty rows.

## Fabric / Product Type / Variant data

- **Cooling**: Blanket → Cream White, Ocean Breeze, Silver Mist
- **Gauze**: Blanket → Alabaster White, Shadow Gray, Soft Maple
- **Linen**: Duvet Set, Sheet Set → Alabaster White, Desert Sand, Stone Sage, Terracotta Blush
- **Percale**: Duvet Set, Sheet Set → Ash Gray, Desert Sand, Herb Sage, Icy White
- **Sateen**: Duvet Set, Sheet Set → Driftwood, Icy White, Ocean Breeze
- **Silk**: Eye Mask, Pillow Case → Alabaster White, Olive Sage, Pewter Gray, Warm Taupe
- **Tencel**: Duvet Set, Sheet Set → Deep Ocean, Dove Gray, Frost White, Stone Taupe

44 unique combinations total.

## Key file paths

- **v3 code**: `/Users/marcuslee/Desktop/_Claud/Work Projects/Selene Dreams/AI Generation Flow/selene-dreams-script-v3.0/`
- **Config**: `config.py` (contains Replicate token, Sheet ID, Drive folder IDs)
- **Renamed product photos**: `/Users/marcuslee/Desktop/_Claud/Work Projects/Selene Dreams/Product Image/_v3 Source Images (upload to Drive)/`
- **Launcher scripts**: `AI Generation Flow/Start Selene AI.command` and `Stop Selene AI.command`
- **Sheet**: https://docs.google.com/spreadsheets/d/1GJO1YgfPY1QSTX-7ZhBA4xI7teKsajf04-MVPkMdp9s/edit
- **Drive parent folder**: https://drive.google.com/drive/u/0/folders/15gGeETzOnyKWfoYwKAUJCxqML7T8a75I

## Fixes shipped this session

- Switched model FLUX 2 Pro → Nano Banana Pro (FLUX invented generic products)
- Explicit `predictions.create()` + polling (replaced `client.run()` which was dropping connections mid-generation)
- Resumable Drive uploads with 1 MB chunks and 3-retry outer loop (fixed "Broken pipe" errors on long generations)
- Fixed cascading dropdown UX: dropdown arrows now appear on all rows via baseline validation, Apps Script overrides per-row when Fabric picked
- "Oliver Sage" → "Olive Sage" typo corrected everywhere
- Removed formula-based data validation (Sheets doesn't support formulas in "dropdown from range")

## The next big move: home-server upgrade

**Marcus has decided to repurpose a spare older laptop as an always-on home server** for the generation pipeline and future automated workflows. He wants best-practice setup that can scale.

**The plan (in priority order):**

**Tier 1 (foundation):**
1. Install Docker Desktop or OrbStack on the spare laptop
2. Cloudflare Tunnel (free, better than ngrok — stable URL, no router config)
3. Tailscale for remote SSH/access from anywhere
4. Everything in a private git repo (configs, code, docker-compose)

**Tier 2 (reliability, when second service added):**
5. Caddy as reverse proxy (routes multiple services under one URL)
6. Uptime Kuma for monitoring/alerts
7. `restart: unless-stopped` in Docker

**Tier 3 (nice-to-have):**
8. Backups via rsync to Backblaze B2 (~$5/mo)
9. Log aggregation (Grafana Loki, later)
10. Small UPS ($50)

**OS choice:** Keep macOS on the old laptop for now. Later, if running 5+ services, consider wiping to Ubuntu Server.

## What Marcus wants next

To start upgrading the generation flow. Specifically:
- Package the current Selene code as a Docker container
- Docker-compose file with server + Cloudflare Tunnel + Uptime Kuma
- Deployment guide for the spare laptop
- Get off ngrok free tier onto Cloudflare Tunnel (free, stable URL, no session limit)

## Open decisions / questions

- Whether to build the Dockerized version now or first stabilize on Marcus's current setup for a week
- Whether to use a domain (buy one, ~$10/yr) or start with `trycloudflare.com` free subdomain
- Backup strategy — start with git repo for code/configs, add cloud backups later

## Files that need to go into any new git repo

- `selene-dreams-script-v3.0/*.py` (server, generate, google_services, replicate_service, migrate_sheet_to_v3, etc.)
- `trigger.gs` (Apps Script)
- `Start Selene AI.command` / `Stop Selene AI.command`
- `requirements.txt`
- `README.md`
- **NOT** `credentials.json`, `oauth_credentials.json`, `token.json`, or the API token in `config.py` — those go in a git-ignored `.env` file

## User preferences (from earlier sessions)

- Wants free/low-cost solutions when possible
- Non-developer, entrepreneur, JD student at CUHK
- Prefers direct honest responses, no flattery
- If uncertain, say so and indicate what's uncertain
- Doesn't use emojis unless explicitly asked
