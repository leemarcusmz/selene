"""
_tests/test_reference_sets.py — reference_drive 1.1 set semantics, offline
=============================================================================
VERSION 1.0 — 2026-09-16

Stubbed Drive + stubbed claude. Run from the v3.0 folder:
    python3 _tests/test_reference_sets.py
Checks: a sub-folder of 02. Educational becomes one set; slides land in
<lane>/<set>/ in filename order; notes.txt is read; a set is described in
ONE call with all slides listed; section() shows a set as one entry and
counts it once toward MAX_VIEW; a withdrawn slide clears the set note;
a renamed set moves locally; a set deleted in Drive is dropped; 1.0
manifests load; taste_store rolls a set up into one row; every consumer
prompt still renders.
"""
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
V3 = os.path.dirname(HERE)
sys.path.insert(0, V3)

import reference_drive as rd  # noqa: E402

TMP = tempfile.mkdtemp(prefix="selene_reftest_")
rd.ROOT = TMP
rd.MANIFEST = os.path.join(TMP, "_manifest.json")
rd.LOCK_PATH = os.path.join(TMP, "_sync.lock")
rd.FOLDER_ID = "root"

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64
FAILED = []


def check(cond, msg):
    print(("  ok   " if cond else "  FAIL ") + msg)
    if not cond:
        FAILED.append(msg)


# ── a fake Drive ────────────────────────────────────────────────────────────
class FakeDrive:
    """tree: {folder_id: [children]}; child = dict(id, name, mimeType, parent)"""
    def __init__(self):
        self.nodes = {}

    _clock = 0

    def add(self, fid, name, parent, mime, size=100):
        # each node added later is "newer" in Drive, as in real life
        FakeDrive._clock += 1
        self.nodes[fid] = {"id": fid, "name": name, "mimeType": mime,
                           "size": str(size),
                           "modifiedTime": f"2026-09-16T00:{FakeDrive._clock:02d}:00Z",
                           "parent": parent}

    def rm(self, fid):
        self.nodes.pop(fid, None)

    def files(self):
        return self

    def list(self, q="", **kw):
        parent = q.split("'")[1]
        want_folders = "application/vnd.google-apps.folder" in q
        want_notes = "text/plain" in q
        out = []
        for n in self.nodes.values():
            if n["parent"] != parent:
                continue
            is_folder = n["mimeType"] == "application/vnd.google-apps.folder"
            is_text = n["mimeType"] in ("text/plain", "text/markdown")
            if want_folders and is_folder:
                out.append({"id": n["id"], "name": n["name"]})
            elif want_notes and is_text:
                out.append({k: n[k] for k in ("id", "name", "mimeType", "size")})
            elif not want_folders and not want_notes and n["mimeType"].startswith("image/"):
                out.append({k: n[k] for k in ("id", "name", "mimeType", "size", "modifiedTime")})
        return FakeResp({"files": out})


class FakeResp:
    def __init__(self, d):
        self.d = d

    def execute(self):
        return self.d


drive = FakeDrive()
F = "application/vnd.google-apps.folder"
drive.add("edu", "02. Educational", "root", F)
drive.add("sty", "01. Style", "root", F)
drive.add("arc", "00. Archive", "root", F)
drive.add("single1", "loose-edu.jpg", "edu", "image/jpeg")
drive.add("set1", "brooklinen - thread count myth", "edu", F)
drive.add("s1c", "03.png", "set1", "image/png")
drive.add("s1a", "01.png", "set1", "image/png")
drive.add("s1b", "02.png", "set1", "image/png")
drive.add("s1n", "notes.txt", "set1", "text/plain")
drive.add("style1", "moody-bed.jpg", "sty", "image/jpeg")
drive.add("arcimg", "old.jpg", "arc", "image/jpeg")

NOTE_TEXT = "Saved for the myth-busting hook; slide 1 asks a question."


def fake_download(_drive, fid):
    if fid == "s1n":
        return NOTE_TEXT.encode()
    return PNG


import google_services  # noqa: E402
google_services.download_file_from_drive = fake_download

# ── stub claude ─────────────────────────────────────────────────────────────
CALLS = []


def fake_invoke(prompt, workdir, out_path, schema=None, stage=None, timeout=600, **kw):
    CALLS.append(prompt)
    keys = list(schema.keys())
    return True, {k: f"<{k}>" for k in keys}


import claude_client  # noqa: E402
claude_client.invoke_claude_json = fake_invoke

print("\n1. first sync")
new, removed = rd.sync(drive)
m = rd.load_manifest()
check(new == 5, f"5 images pulled (got {new})")
check("set1" in m["sets"], "set recorded")
s = m["sets"]["set1"]
check(s["marcus_note"] == NOTE_TEXT, "notes.txt read into marcus_note")
check([m["files"][f]["name"] for f in s["files"]] == ["01.png", "02.png", "03.png"],
      "slides in filename order")
check(all(m["files"][f]["local"].startswith("educational/brooklinen - thread count myth/")
          for f in s["files"]), "slides live under <lane>/<set>/")
check(m["files"]["single1"]["local"] == "educational/loose-edu.jpg", "loose file stays a single")
check("arcimg" not in m["files"], "00. Archive ignored")

print("\n2. describe")
n = rd.describe_new()
check(n == 3, f"3 vision calls: 1 set + 2 singles (got {n})")
set_prompt = [p for p in CALLS if "Set name" in p]
check(len(set_prompt) == 1, "set described in ONE call")
check(set_prompt and "01.png" in set_prompt[0] and "03.png" in set_prompt[0]
      and set_prompt[0].index("01.png") < set_prompt[0].index("03.png"),
      "set prompt lists all slides in order")
check(set_prompt and NOTE_TEXT in set_prompt[0], "Marcus's note in the set prompt")
m = rd.load_manifest()
check(m["sets"]["set1"].get("note", {}).get("structure") == "<structure>", "set note stored with structure")

print("\n3. section()")
sec = rd.section("educational", limit=1)
check('SET "brooklinen - thread count myth"' in sec, "set rendered as one entry")
check("newest 1 of 2" in sec, "set counts once toward the limit (1 of 2 items)")
check(rd._lane_items(rd.load_manifest(), "educational")[0]["kind"] == "set", "newest-first uses Drive modifiedTime (set added later sorts first)")
check(sec.count("/01.png") == 1 and "/03.png" in sec, "all slides listed inside the set")
check("A SET is one whole post" in sec, "competitor framing present")
check(NOTE_TEXT in sec, "Marcus's note surfaces in the prompt block")
check("Structure: <structure>" in sec, "structure note surfaces")
sty = rd.section("style")
check("A SET is one whole post" not in sty, "no set framing when a lane has no sets")
check(len(rd.files("educational", limit=1)) == 3, "files() flattens a set (3 slides for 1 slot)")
check("SET brooklinen" in rd.notes_text("educational"), "notes_text includes the set")
check(os.path.exists(os.path.join(TMP, "_notes-educational.md")), "_notes file written")

print("\n4. withdraw a slide -> set re-describes")
drive.rm("s1b")
new, removed = rd.sync(drive)
m = rd.load_manifest()
check(removed == 1, "one slide dropped")
check("note" not in m["sets"]["set1"], "set note cleared for re-describe")
check([m["files"][f]["name"] for f in m["sets"]["set1"]["files"]] == ["01.png", "03.png"], "set files updated")
check(not os.path.exists(os.path.join(TMP, "educational/brooklinen - thread count myth/02.png")), "local slide removed")

print("\n5. rename the set folder in Drive -> moves locally")
drive.nodes["set1"]["name"] = "brooklinen - thread count myth v2"
rd.sync(drive)
m = rd.load_manifest()
check(m["sets"]["set1"]["name"].endswith("v2"), "set renamed")
check(all(m["files"][f]["local"].startswith("educational/brooklinen - thread count myth v2/")
          for f in m["sets"]["set1"]["files"]), "slides moved to the new folder")
check(os.path.exists(os.path.join(TMP, "educational/brooklinen - thread count myth v2/01.png")), "file really moved")

print("\n6. move a loose single INTO a set")
drive.nodes["single1"]["parent"] = "set1"
rd.sync(drive)
m = rd.load_manifest()
check(m["files"]["single1"].get("set") == "set1", "single now belongs to the set")
check(len(m["sets"]["set1"]["files"]) == 3, "set has 3 slides again")
check(len(rd._lane_items(m, "educational")) == 1, "lane now has exactly 1 item (the set)")

print("\n7. delete the whole set in Drive")
for fid in ("s1a", "s1c", "single1", "s1n", "set1"):
    drive.rm(fid)
new, removed = rd.sync(drive)
m = rd.load_manifest()
check("set1" not in m["sets"], "set dropped")
check(removed == 3, f"3 files dropped (got {removed})")
check(rd.section("educational") == "", "educational section empty -> placeholder vanishes")

print("\n8. drive down -> cache kept")
class Down:
    def files(self):
        raise RuntimeError("invalid_grant")
new, removed = rd.sync(Down())
check((new, removed) == (0, 0) and rd.section("style") != "", "fail-open, style cache intact")

print("\n9. a 1.0 manifest loads")
with open(rd.MANIFEST) as f:
    old = json.load(f)
old.pop("sets", None)
with open(rd.MANIFEST, "w") as f:
    json.dump(old, f)
m = rd.load_manifest()
check(m.get("sets") == {}, "missing sets key -> {}")
check(rd.section("style") != "", "1.0 manifest still renders")

print("\n10. taste_store rolls a set into one row")
drive.add("set2", "hommey - linen care", "edu", F)
drive.add("t1", "1.png", "set2", "image/png")
drive.add("t2", "2.png", "set2", "image/png")
rd.sync(drive)
CALLS.clear()
rd.describe_new()
import taste_store  # noqa: E402
rows = taste_store.collect_references()
edu = [r for r in rows if r["lane"] == "educational"]
check(len(edu) == 1 and edu[0]["name"].startswith("SET hommey - linen care (2 slides)"),
      "one row per set, slides not listed as singles")
check("Structure:" in edu[0]["shows"], "structure carried into references.md row")
check(taste_store.VERSION == "1.3", f"taste_store VERSION constant is 1.3 (got {taste_store.VERSION})")

print("\n11. consumer prompts still render")
sec = rd.section("educational", heading="MARCUS'S EDUCATIONAL REFERENCES")
for name in ("image-prompts", "screening", "reference-note", "reference-set"):
    try:
        body, ver = claude_client.load_prompt(name)
        check(bool(body) and ver != "unversioned", f"prompts/{name}.md loads ({ver})")
    except Exception as e:
        check(False, f"prompts/{name}.md loads ({e})")
edu_prompt = os.path.join(os.path.dirname(V3), "selene-dreams-educational-v1.0", "prompts", "picker_edu.md")
if os.path.exists(edu_prompt):
    tpl = open(edu_prompt).read()
    check("{reference_section}" in tpl, "picker_edu.md carries {reference_section}")
    try:
        import string
        fields = {fn for _, fn, _, _ in string.Formatter().parse(tpl) if fn}
        rendered = tpl.format(**{f: (sec if f == "reference_section" else "x") for f in fields})
        check('SET "hommey - linen care"' in rendered, "picker_edu renders with a set inside")
    except Exception as e:
        check(False, f"picker_edu.md renders ({e})")

shutil.rmtree(TMP, ignore_errors=True)
print(f"\n{'ALL PASSED' if not FAILED else str(len(FAILED)) + ' FAILED'}")
sys.exit(1 if FAILED else 0)
