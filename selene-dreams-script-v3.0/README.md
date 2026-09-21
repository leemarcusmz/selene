# Selene Dreams — AI Image Generation Script v3.0

FLUX 2 Pro pipeline for Selene Dreams Instagram content. Teammates fill out
the Generation Queue Google Sheet, set Status to **Ready**, and the script
generates photorealistic lifestyle images via Black Forest Labs' FLUX 2 Pro
on Replicate.

## What changed from v2.0

| Aspect | v2.0 | v3.0 |
|---|---|---|
| Image model | Claid AI (single input image) | FLUX 2 Pro on Replicate (multi-reference) |
| Source naming | `ProductVariant.jpg` (no spaces) | `Fabric_Product-Type_Variant.jpg` |
| Prompts per row | 3 | 5 |
| Reference images per prompt | 0 (text only) | unlimited (comma-separated filenames) |
| Sheet columns | 18 | 22 |
| Error handling | Status reset to Ready on failure (loop risk) | Status set to ERROR (no retry loop) |
| Output folders | `{Year}/{N. Month}/{ProductVariant_Month_Year_NN}` | `{Year}/{NN. Month}/Column N` |
| Auto-prompt generation | Claude API filled blank prompts | Removed — users write prompts manually |

## File Structure

```
selene-dreams-script-v3.0/
├── config.py               — Credentials, folder IDs, column indexes
├── google_services.py      — Sheets, Drive, source/reference lookup, error detection
├── replicate_service.py    — FLUX 2 Pro generation via Replicate
├── generate.py             — Row processing logic (CLI entry point)
├── server.py               — Flask webhook server
├── trigger.gs              — Apps Script (paste into the Sheet)
├── migrate_sheet_to_v3.py  — One-off schema migration script
├── requirements.txt
├── credentials.json        — Service account (Sheets)
├── oauth_credentials.json  — OAuth client (Drive personal)
└── token.json              — Cached OAuth token
```

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Get a Replicate API token

Sign up at [replicate.com](https://replicate.com), then go to
[Account > API Tokens](https://replicate.com/account/api-tokens) and create
a token. Paste it into `config.py` as `REPLICATE_API_TOKEN`. Tokens with
no expiry are recommended; if you set an expiry, calendar-reminder it.

### 3. Run the migration script (one-time)

This rewrites the existing v2 spreadsheet to the v3 schema and moves it
into the new Drive folder.

```bash
python migrate_sheet_to_v3.py
```

The script will:
- Replace the Generation Queue header row (22 columns).
- Clear all data rows.
- Add a `=ROW()-1` formula to the # column on rows 2–500.
- Add data validation to the Status column.
- Rewrite the Documentation tab with one row per field.
- Move the Sheet file into the `10. AI Generation` Drive folder.
- Confirm the service account still has Editor access.

### 4. Share the Sheet with the service account (one-time, manual)

Open the Sheet in Drive, click Share, add
`selene-dreams-script@selene-dreams.iam.gserviceaccount.com` as Editor.
This is required even though the parent folder is shared with the service
account, because Sheets sometimes require explicit per-file sharing.

### 5. Upload product photos

Drag everything from the local `_v3 Source Images (upload to Drive)` folder
into `01. Product Photos` in Drive. Then delete the local folder.

### 6. Reference images (refit 2026-09-16)

`02. Reference Images` in Drive is where you and the team drop images that
show the KIND of content you want. **Style only** — they are viewed by the
writers for mood, composition, light and styling; nothing is ever passed to
the image generator as pixels.

```
02. Reference Images/
  01. Style         -> image lane: prompt writer (prompt_runner) + Monday screener
  02. Educational   -> educational carousels: the picture editor (plan_edu)
  00. Archive       -> ignored (the old 2026/month folders live here)
  loose files       -> count as Style
```

**Saving a whole post (1.1, 2026-09-16).** A sub-folder inside a lane folder
is ONE reference post — screenshot a competitor carousel slide by slide and
drop the slides in their own folder:

```
02. Educational/
  brooklinen - thread count myth/     <- folder name = the label ("brand - topic")
    01.png 02.png 03.png ...          <- slides, numbered so the order is right
    notes.txt                         <- optional: one line on WHY you saved it
```

A set is described in one vision call as a carousel (hook, sequencing,
payoff), takes ONE of the 6 slots the writers see (all its slides listed, in
order), and is framed to them as "borrow the structure and pacing, never the
brand, layout, colours or copy". Your `notes.txt` line is quoted verbatim and
weighted above the description — it is the highest-signal thing you can add.
Loose files in a lane folder stay single images. Works the same under
`01. Style` (e.g. a brand's grid saved as one set).

`reference_drive.py` syncs the folder into the local cache
`AI Generation Flow/reference-images/{style,educational}/` before each
prompt-writing, screening or planning run (fail-open: a dead Drive token
leaves the cache as it was), writes one vision note per new image
(`_notes-<lane>.md`), and the writers view the newest 6. Remove an image in
Drive to withdraw it. HEIC is skipped — export as JPG.

```
python3 reference_drive.py --sync     # pull + describe now, print the cache
```

The v2.0 per-month scheme and the Sheet's "Reference Image 1-5" cells are
gone since 2026-07-22; the column table below is historical.

## Running

### Webhook (recommended)

```bash
python server.py        # Terminal 1
ngrok http 5001         # Terminal 2
```

Paste the ngrok URL into `trigger.gs` (in the Apps Script editor) and save.
Whenever a teammate sets a row's Status to `Ready`, the row generates
automatically.

### CLI / batch

```bash
python generate.py
```

Processes all `Ready` rows for the current month and year.

## Sheet column reference

| # | Column | Field | Filled by | Notes |
|---|---|---|---|---|
| 1 | A | # | Formula | `=ROW()-1`, used for the output folder name |
| 2 | B | Year | User | e.g. `2026` |
| 3 | C | Month | User | Full month name (`May`, `June`) |
| 4 | D | Fabric | User | First component of source filename, e.g. `Cooling`, `Linen`, `Silk`, `Tencel`, `Sateen`, `Percale`, `Gauze` |
| 5 | E | Product Type | User | Second component of source filename, e.g. `Blanket`, `Duvet Set`, `Sheet Set`, `Eye Mask`, `Pillow Case` |
| 6 | F | Variant | User | Color or finish, e.g. `Cream White`, `Shadow Gray` |
| 7 | G | Prompt 1 | User | Required if any image is wanted |
| 8 | H | Prompt 2 | User | Optional |
| 9 | I | Prompt 3 | User | Optional |
| 10 | J | Prompt 4 | User | Optional |
| 11 | K | Prompt 5 | User | Optional |
| 12 | L | Reference Image 1 | User | One filename or several comma-separated. Looks up in `02. Reference Images/{Year}/{NN. Month}/` |
| 13 | M | Reference Image 2 | User | Pairs with Prompt 2 |
| 14 | N | Reference Image 3 | User | Pairs with Prompt 3 |
| 15 | O | Reference Image 4 | User | Pairs with Prompt 4 |
| 16 | P | Reference Image 5 | User | Pairs with Prompt 5 |
| 17 | Q | Status | User | `Ready` triggers generation; `Hold` skips; the script sets `Processing` then `Done` or `ERROR` |
| 18 | R | Credits Used | Script | Approximate USD spent |
| 19 | S | Output Folder | Script | Drive path to the carousel folder |
| 20 | T | Image URLs | Script | Comma-separated Drive URLs for each generated image |
| 21 | U | Carousel ID | Script | `Fabric_Type_Variant_MonthYear` |
| 22 | V | Notes | User / Script | Free text. On ERROR, the script logs the failure here |

## Status values

- `Ready` — triggers a run.
- `Hold` — skipped, ignored.
- `Processing` — generation in progress (set automatically; do not edit).
- `Done` — completed successfully.
- `ERROR` — failed; see Notes for the reason. Edit the row, then change
  Status back to `Ready` to retry.

## Source image naming convention

`{Fabric}_{Product-Type-with-dashes}_{Variant-with-dashes}.jpg`

Examples:
- `Cooling_Blanket_Cream-White.jpg`
- `Linen_Duvet-Set_Alabaster-White.jpg`
- `Silk_Eye-Mask_Pewter-Gray.jpg`
- `Gauze_Blanket_Shadow-Gray.jpg`

Spaces in multi-word values become dashes. The three segments are joined
with underscores. Case-insensitive matching.

## Output folder structure

```
03. Generated Images/
└── 2026/
    └── 05. May/
        ├── Column 1/
        │   ├── Cooling_Blanket_Cream-White_May_2026_01.png
        │   ├── Cooling_Blanket_Cream-White_May_2026_02.png
        │   └── ...
        └── Column 2/
            └── ...
```

`Column N` corresponds to the `#` value in the sheet — i.e. row 2's
generation lands in `Column 1`, row 3's in `Column 2`, and so on.
Re-running a row appends `_02`, `_03`, ... so old runs are preserved.

## Troubleshooting

**Status stuck on `Processing`**
The script crashed mid-run. Manually change Status to `Ready` to retry.

**`ERROR: Source image not found...`**
The script could not match Fabric / Product Type / Variant against any
file in `01. Product Photos`. The error message lists which of the three
fields is the typo and suggests the closest match.

**`ERROR: Reference image(s) not found...`**
Check that the filename you typed in the Reference Image cell exists in
`02. Reference Images/{Year}/{NN. Month}/`.

**Webhook not firing**
- Confirm `server.py` is running.
- Confirm ngrok is running and `trigger.gs` has the current URL.
- In the Apps Script editor, check Executions for errors.
- Run `testHealth()` from the editor to confirm reachability.

**OAuth token expired**
Delete `token.json` and run `python generate.py` once — it will reopen the
browser for re-authorization.
