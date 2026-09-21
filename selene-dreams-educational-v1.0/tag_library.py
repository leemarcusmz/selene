# =============================================================================
# tag_library.py — write real subject/mood tags onto the Image Library
# VERSION 2.0 — 2026-09-10
# CHANGELOG
#   2.0  2026-09-10  LIBRARY v2. Writes the sentence description and structured
#                    fields (K-O, S) that Marcus's matching design needs, next to
#                    the v1 tags. "Untagged" now means "no description yet", so
#                    --only-untagged (the default) re-describes the whole v1
#                    library once and then only touches new images. Ours and
#                    Product are never written here - they come from the Sources
#                    tab via the indexer.
#   1.0  2026-09-09  First release. The library's subject column held the Drive
#                    PATH, so plan_edu's keyword match was matching FILENAMES:
#                    "bed" found 0 of 50 images (the files say Sheet-Set and
#                    Duvet-Set) and forced Buying Guide and Styling & Home to
#                    generate every slide, while "Row" found 45 of 50 by matching
#                    the folder name and let any picture answer any post.
#                    This looks at each image and writes what is in it.
#                    Also records an explicit pale/mid/dark luminance term, which
#                    is what a future legibility gate needs to keep white type off
#                    a washed-out photograph.
#                    Batched (default 10 images per call) so one refusal or
#                    timeout costs a batch, not the whole run, and so a partial
#                    run can be resumed with --only-untagged.
# =============================================================================
import os, re, json, tempfile, shutil, argparse
import config_edu as C
import sheets_edu as S
import library_edu as L
from log_edu import log
from claude_client import invoke_claude_json

SCHEMA = {"images": {"type": "list", "required": True, "min_len": 1}}
BATCH = 10
# Image Library columns: A id · B source · C fingerprint · D loc · E subject
# F mood · G times used · H used-in · I used-as-cover · J cover-eligible
COL_SUBJECT, COL_MOOD, COL_ELIGIBLE = "E", "F", "J"
# v2: K description · L setting · M action · N people · O light · S non-brand
COL_DESC, COL_SETTING, COL_ACTION, COL_PEOPLE, COL_LIGHT, COL_NONBRAND = "K", "L", "M", "N", "O", "S"


def _prompt():
    path = os.path.join(C.PROMPT_DIR, "tag_library.md")
    with open(path) as f:
        text = f.read()
    m = re.search(r"<!--\s*VERSION:\s*([^\s>]+)\s*-->", text)
    return text, (m.group(1) if m else "unversioned")


def untagged(rows):
    """A row still needs tagging if it has no v2 description yet (or v1 tags
    that are still the Drive path)."""
    return [r for r in rows if not (r.get("description") or "").strip()
            or "/" in (r["subject"] or "") or not (r["mood"] or "").strip()]


def tag_batch(rows):
    """Returns {id: {subject, mood, coverEligible}} for one batch."""
    workdir = tempfile.mkdtemp(prefix="selene_tag_")
    try:
        img_dir = os.path.join(workdir, "images")
        os.makedirs(img_dir)
        for r in rows:
            with open(os.path.join(img_dir, f"{r['id']}.jpg"), "wb") as f:
                f.write(L.download_image(r["loc"]))
        out_path = os.path.join(workdir, "tags.json")
        tpl, ver = _prompt()
        prompt = tpl.format(img_dir=img_dir, n_images=len(rows), out_path=out_path)
        ok, res = invoke_claude_json(prompt, workdir, out_path, schema=SCHEMA,
                                     stage="tag_library", timeout=600)
        if not ok:
            return None, res
        return {str(e.get("id")): e for e in res.get("images", [])}, ver
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def run(only_untagged=True, limit=None, dry_run=False):
    rows = L.library_rows()
    todo = untagged(rows) if only_untagged else rows
    if limit:
        todo = todo[:limit]
    log(f"tag_library: {len(todo)} image(s) to tag (of {len(rows)} in the library)")
    ws = S.tab(C.TAB_LIBRARY)
    done = fail = 0
    for i in range(0, len(todo), BATCH):
        batch = todo[i:i + BATCH]
        log(f"  batch {i // BATCH + 1}: {batch[0]['id']}..{batch[-1]['id']}")
        tags, info = tag_batch(batch)
        if tags is None:
            log(f"  BLOCKED: {info}")
            log("  STOPPING — the rest would fail the same way. Re-run to resume.")
            fail += len(batch)
            break
        updates = []
        for r in batch:
            e = tags.get(r["id"])
            if not e:
                log(f"    {r['id']}: no tag returned"); fail += 1; continue
            subj = str(e.get("subject", "")).strip().lower()
            mood = str(e.get("mood", "")).strip().lower()
            desc = str(e.get("description", "")).strip()
            yn = lambda k: "Yes" if str(e.get(k, "")).strip().lower().startswith("y") else "No"
            elig, nonbrand = yn("coverEligible"), yn("nonBrand")
            if not subj or not mood or not desc:
                log(f"    {r['id']}: empty fields"); fail += 1; continue
            log(f"    {r['id']}: {desc[:70]}  cover={elig} nonbrand={nonbrand}")
            if not dry_run:
                updates += [
                    {"range": f"{COL_SUBJECT}{r['row']}", "values": [[subj]]},
                    {"range": f"{COL_MOOD}{r['row']}", "values": [[mood]]},
                    {"range": f"{COL_ELIGIBLE}{r['row']}", "values": [[elig]]},
                    {"range": f"{COL_DESC}{r['row']}:{COL_LIGHT}{r['row']}", "values": [[
                        desc, str(e.get("setting", "")).strip().lower(),
                        str(e.get("action", "")).strip().lower(),
                        str(e.get("people", "")).strip().lower(),
                        str(e.get("light", "")).strip().lower()]]},
                    {"range": f"{COL_NONBRAND}{r['row']}", "values": [[nonbrand]]},
                ]
            done += 1
        if updates:
            ws.batch_update(updates)          # one write per batch, not per cell (429 lesson)
    return f"{done} tagged, {fail} failed"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="retag everything, not just untagged")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    print(run(only_untagged=not a.all, limit=a.limit, dry_run=a.dry_run))
