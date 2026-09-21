# =============================================================================
# library_edu.py — Image Library: Drive indexer + reuse decisions
# VERSION 2.2 — 2026-09-11
# CHANGELOG
#   2.2  2026-09-11  NEVER INDEX OUR OWN OUTPUT. Walking 03. Generated Images
#                    swept up the educational lane's rendered slides (text baked
#                    in), strips and contact sheets - 68 rows that could have
#                    come back as "backgrounds". Row folders are skipped except
#                    their candidates/ subfolder; strip/candidates/slide render
#                    names are skipped by pattern. Ids now continue from the
#                    highest existing id, never from the row count.
#   2.1  2026-09-11  Product "from filename": a Sources row whose Product cell
#                    says `from filename` has each image's product parsed from
#                    its name (Linen_Sheet-Set_Stone-Sage.jpg -> "Linen — Sheet
#                    Set — Stone Sage"). Built for 01. Product Photos, the image
#                    lane's SKU catalogue, which the library now reads (never
#                    writes) so every SKU has one Ours = Yes reference frame.
#   2.0  2026-09-10  LIBRARY v2 (Marcus's matching design). Every row now carries
#                    a sentence description and structured fields (K-T: setting,
#                    action, people, light, ours, product, source folder,
#                    non-brand, brief). The indexer walks every folder on the new
#                    Sources tab as well as the default roots, records the folder
#                    each image came from, and inherits Ours/Product from the
#                    Sources row for that folder - the two facts no vision model
#                    can know. folder_by_path resolves nested Drive paths.
#   1.2  2026-08-28  Drive uses the v3.0 flow's OAuth user token (token.json,
#                    auto-refresh) — service accounts have NO storage quota, so
#                    uploads 403'd. Same lesson v3.0 already learned.
#   1.1  2026-08-28  pick_reuse accepts preloaded rows (429 quota fix — callers
#                    load the library ONCE per run, not once per slide).
#   1.0  2026-08-28  First release. Fingerprints = Drive md5Checksum (no
#                    downloads needed). Cover rule: an image ever used as a
#                    posted cover is never cover-eligible again.
# =============================================================================
import io, os, re
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials as OAuthCredentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
import config_edu as C
import sheets_edu as S

SCOPES = ["https://www.googleapis.com/auth/drive"]
_drive = None
def drive():
    """OAuth user creds (v3.0's token.json) — SAs have no Drive storage quota."""
    global _drive
    if _drive is None:
        token = os.path.join(C.V3_DIR, "token.json")
        if os.path.exists(token):
            creds = OAuthCredentials.from_authorized_user_file(token, SCOPES)
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                with open(token, "w") as f: f.write(creds.to_json())
        else:
            creds = service_account.Credentials.from_service_account_file(C.CREDENTIALS_PATH, scopes=SCOPES)
        _drive = build("drive", "v3", credentials=creds, cache_discovery=False)
    return _drive

def find_folder(name, parent=None):
    q = f"name = '{name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    if parent: q += f" and '{parent}' in parents"
    res = drive().files().list(q=q, fields="files(id,name)", pageSize=5).execute()
    files = res.get("files", [])
    return files[0]["id"] if files else None

def folder_by_path(path, parent=None):
    """'03. Generated Images/2026/07. July' -> folder id, or None."""
    fid = parent
    for seg in [p for p in path.split("/") if p]:
        fid = find_folder(seg, fid)
        if not fid:
            return None
    return fid


def sources_rows():
    """The Sources tab: one row per Drive folder Marcus has labelled."""
    try:
        vals = S.values(C.TAB_SOURCES)
    except Exception:
        return []
    out = []
    for i, r in enumerate(vals[2:], start=3):       # row 1 note, row 2 header
        r = (r + [""] * 6)[:6]
        if not r[0].strip():
            continue
        out.append({"row": i, "folder": r[0].strip().strip("/"), "ours": r[1].strip(),
                    "product": r[2].strip(), "date": r[3].strip(), "notes": r[4].strip(),
                    "indexed": r[5].strip()})
    return out


def source_for(folder_path, sources=None):
    """Longest-prefix match of an image's folder against the Sources tab."""
    sources = sources if sources is not None else sources_rows()
    best = None
    for src in sources:
        if folder_path == src["folder"] or folder_path.startswith(src["folder"] + "/"):
            if best is None or len(src["folder"]) > len(best["folder"]):
                best = src
    return best


_SKIP_NAME = re.compile(r"(_strip|_candidates)\.jpe?g$|^row\d+_slide\d+\.jpe?g$", re.I)


def is_pipeline_output(folder, name):
    """True for files this lane wrote that must never be reused as a photo:
    rendered slides, strips, contact sheets. Candidates (raw generations) are
    the one thing under a Row folder that IS reusable."""
    if _SKIP_NAME.search(name or ""):
        return True
    parts = (folder or "").split("/")
    if C.EDU_OUTPUT_SUBFOLDER in parts:
        return not parts[-1].startswith("candidates")
    return False


def product_from_filename(name):
    """'Linen_Sheet-Set_Stone-Sage.jpg' -> 'Linen — Sheet Set — Stone Sage'."""
    import os as _os, re as _re
    stem = _os.path.splitext(name)[0]
    parts = [p.replace("-", " ").strip() for p in stem.split("_") if p.strip()]
    parts = [_re.sub(r"\s+", " ", p) for p in parts]
    return " — ".join(parts) if parts else ""


def ensure_folder(name, parent):
    fid = find_folder(name, parent)
    if fid: return fid
    meta = {"name": name, "mimeType": "application/vnd.google-apps.folder", "parents": [parent]}
    return drive().files().create(body=meta, fields="id").execute()["id"]

def walk_images(folder_id, prefix=""):
    """Yield (path, file dict with id/name/md5Checksum) for images under folder."""
    page = None
    while True:
        res = drive().files().list(
            q=f"'{folder_id}' in parents and trashed = false",
            fields="nextPageToken, files(id,name,mimeType,md5Checksum)",
            pageSize=200, pageToken=page).execute()
        for f in res.get("files", []):
            p = f"{prefix}/{f['name']}" if prefix else f["name"]
            if f["mimeType"] == "application/vnd.google-apps.folder":
                yield from walk_images(f["id"], p)
            elif f["mimeType"].startswith("image/"):
                yield p, f
        page = res.get("nextPageToken")
        if not page: break

def index_library(limit=None):
    """Walk every library root (config + Sources tab) and append unknown
    fingerprints. Each new row records its Drive folder and inherits
    Ours/Product from the Sources row that covers it."""
    ws = S.tab(C.TAB_LIBRARY)
    existing = ws.get_all_values()
    known = {r[2] for r in existing[1:] if len(r) > 2 and r[2]}
    nums = [int(m.group(1)) for r in existing[1:] if r and r[0]
            for m in [re.match(r"IMG-(\d+)", r[0])] if m]
    next_id = (max(nums) + 1) if nums else 1
    sources = sources_rows()
    roots = list(dict.fromkeys(list(C.LIBRARY_ROOTS) + [s["folder"] for s in sources]))
    # a folder already covered by a shorter root is walked once, via the root
    roots = [r for r in roots if not any(o != r and r.startswith(o + "/") for o in roots)]
    added, rows, missing = 0, [], []
    for root in roots:
        rid = folder_by_path(root)
        if not rid:
            missing.append(root)
            continue
        for sub, f in walk_images(rid):
            fp = f.get("md5Checksum", "")
            if not fp or fp in known:
                continue
            known.add(fp)
            folder = f"{root}/{sub.rsplit('/', 1)[0]}" if "/" in sub else root
            if is_pipeline_output(folder, f["name"]):
                continue
            src = source_for(folder, sources)
            ours = (src or {}).get("ours", "") or "No"
            product = (src or {}).get("product", "")
            if product.strip().lower() == "from filename":
                product = product_from_filename(f["name"])
            rows.append([f"IMG-{next_id + added:04d}", f"{root}: {sub.rsplit('/', 1)[0] if '/' in sub else ''}".rstrip(": "),
                         fp, f"drive:{f['id']}", sub, "", 0, "", "", "Yes",
                         "", "", "", "", "", ours, product, folder, "", ""])
            added += 1
            if limit and added >= limit:
                break
    if rows:
        ws.append_rows(rows, value_input_option="RAW")
    # mark Sources rows as indexed
    sws = S.tab(C.TAB_SOURCES) if sources else None
    if sws:
        for src in sources:
            if src["indexed"] != "Yes" and src["folder"] not in missing:
                sws.update_acell(f"F{src['row']}", "Yes")
    msg = f"indexed {added} new images"
    if missing:
        msg += f"; folders not found on Drive: {', '.join(missing)}"
    return msg

def library_rows():
    vals = S.values(C.TAB_LIBRARY)
    out = []
    for i, r in enumerate(vals[1:], start=2):
        r = (r + [""] * 20)[:20]
        out.append({"row": i, "id": r[0], "source": r[1], "fp": r[2], "loc": r[3],
                    "subject": r[4], "mood": r[5], "used": r[6], "used_in": r[7],
                    "cover": r[8], "eligible": r[9],
                    # v2 (K-T)
                    "description": r[10], "setting": r[11], "action": r[12],
                    "people": r[13], "light": r[14], "ours": r[15], "product": r[16],
                    "folder": r[17], "non_brand": r[18], "brief": r[19]})
    return out

def pick_reuse(keyword, need_cover_eligible=False, exclude_ids=(), rows=None):
    """v1 matcher: substring match on subject tags/path; prefers least-used.
    Pass rows=library_rows() loaded once per run — never load per slide."""
    if rows is None: rows = library_rows()
    cands = [r for r in rows
             if r["id"] not in exclude_ids
             and (not need_cover_eligible or r["eligible"] == "Yes")
             and (not keyword or keyword.lower() in (r["subject"] + " " + r["mood"]).lower())]
    cands.sort(key=lambda r: int(r["used"] or 0))
    return cands[0] if cands else None

def download_image(loc):
    """loc = 'drive:<fileId>' -> bytes"""
    fid = loc.split(":", 1)[1]
    buf = io.BytesIO()
    dl = MediaIoBaseDownload(buf, drive().files().get_media(fileId=fid))
    done = False
    while not done:
        _, done = dl.next_chunk()
    return buf.getvalue()

def upload_jpeg(local_path, name, parent_id):
    with open(local_path, "rb") as fh:
        media = MediaIoBaseUpload(io.BytesIO(fh.read()), mimetype="image/jpeg")
    meta = {"name": name, "parents": [parent_id]}
    f = drive().files().create(body=meta, media_body=media,
                               fields="id,webViewLink").execute()
    return f["id"], f.get("webViewLink", "")
