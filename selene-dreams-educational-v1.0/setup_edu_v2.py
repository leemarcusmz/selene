# =============================================================================
# setup_edu_v2.py — one-off sheet migration for the full flow (run ONCE)
# VERSION 1.0 — 2026-09-09
# CHANGELOG
#   1.0  2026-09-09  First release. Idempotent; --dry-run prints, --apply writes.
#     1. Post Topic / Topic Types: add "Real Moments" (archetype A, photo essay).
#     2. Post Topic / Topic Guide: add the Real Moments series entry (wording
#        PLACEHOLDER for Marcus).
#     3. Generated Caption: existing headers A-J kept, K1 <- Remark(s).
#     4. Rows 1-9 were planned under the OLD rules (hybrid plans, flat bubble
#        backgrounds, old claim list): queue Notes <- SUPERSEDED, status D <-
#        Superseded, and the topics' Slide cells CLEARED (backed up to _state/)
#        so writer_edu redrafts them in the two-field shape.
#     5. The two posts Marcus approved in chat on 2026-09-09 become topics
#        #10 and #11, Approved, with their copy and cover recorded.
# =============================================================================
import os, json, sys, datetime
import config_edu as C
import sheets_edu as S

APPLY = "--apply" in sys.argv
STAMP = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

def say(msg): print(("APPLY " if APPLY else "DRY   ") + msg)

# --- 1 + 2: topic type + guide ----------------------------------------------
tsheet = S.topic_sheet()
tt = tsheet.worksheet("Topic Types")
tt_vals = tt.get_all_values()
if not any("Real Moments" in (r[0] if r else "") for r in tt_vals):
    row = ["Real Moments", "Feel",
           "A photo essay. Text on the thumbnail only; every other slide is a bare photograph "
           "from a shoot or a generation. Approve the topic (why this is a wordless post) and the "
           "thumbnail line, nothing else. No outro, no product tags."]
    say(f"Topic Types: append {row[0]}")
    if APPLY: tt.append_row(row, value_input_option="RAW")
else:
    say("Topic Types: Real Moments already present")

tg = tsheet.worksheet("Topic Guide")
tg_vals = tg.get_all_values()
if not any("Real Moments" in " ".join(r) for r in tg_vals):
    row = ["Real Moments", "Real Moments",
           "PLACEHOLDER — Marcus to word. The wordless series: a cover line and five photographs "
           "that show a moment with Selene rather than explain one. Candidates: a morning, a "
           "shoot outtake, a customer's room, a colourway in real light."]
    say("Topic Guide: append Real Moments (PLACEHOLDER wording)")
    if APPLY: tg.append_row(row, value_input_option="RAW")
else:
    say("Topic Guide: Real Moments already present")

# --- 3: caption tab headers (existing A-J kept; add K Remark(s)) --------------
cap = S.tab(C.TAB_CAPTION)
have = cap.row_values(1)
if len(have) < 11 or have[10] != "Remark(s)":
    say("Generated Caption: set K1 = Remark(s) (existing headers A-J untouched)")
    if APPLY: cap.update_acell("K1", "Remark(s)")
else:
    say("Generated Caption: K1 Remark(s) already present")

# --- 4: supersede rows 1-9 ----------------------------------------------------
qws = S.tab(C.TAB_QUEUE); sws = S.tab(C.TAB_STATUS)
qrows = S.queue_rows(); srows = S.status_rows()
old = [q for q in qrows if q["num"] and int(q["num"]) <= 9 and "SUPERSEDED" not in q["notes"].upper()]
say(f"queue rows to supersede: {[q['num'] for q in old]}")
if APPLY:
    for q in old:
        note = (q["notes"] + " | " if q["notes"] else "") + f"[{STAMP}] SUPERSEDED — planned under the pre-v1.7 rules; re-planned by writer_edu"
        qws.update_acell(f"S{q['row']}", note)
        st = next((s for s in srows if s["num"] == q["num"]), None)
        if st:
            S.set_status(st["row"], "D", "Superseded")
            S.add_remark(st["row"], "SETUP", "superseded 2026-09-09; topic will be redrafted and re-planned")

topics = S.topics_rows()
tws = tsheet.worksheet(C.TAB_TOPICS)
backup = {t["num"]: t["slides"] for t in topics if t["num"] and t["num"].isdigit() and int(t["num"]) <= 9}
os.makedirs(os.path.dirname(C.STATE_PATH), exist_ok=True)
bpath = os.path.join(os.path.dirname(C.STATE_PATH), "topics_slides_backup_20260909.json")
say(f"backing up slide text of topics {sorted(backup)} -> {bpath}")
if APPLY:
    with open(bpath, "w") as f: json.dump(backup, f, indent=2, ensure_ascii=False)
    for t in topics:
        if t["num"] in backup and any(s.strip() for s in t["slides"]):
            tws.update(values=[[""] * 7], range_name=f"D{t['row']}:J{t['row']}")
            cur = (t["remark"] or "").strip()
            entry = f"[{STAMP}] SETUP: slide copy cleared (old one-field drafts backed up); writer_edu will redraft"
            tws.update_acell(f"M{t['row']}", (cur + " | " + entry) if cur else entry)

# --- 5: the two approved posts ------------------------------------------------
POSTS = [
 ("Care & How-To", "How to wash linen so it lasts: cool water, no softener, dry low and fold damp, wash it alone.",
  ["How To Wash Linen. | Four habits that keep a sheet set softening for years instead of wearing out.",
   "Cool Water, Gentle Cycle | Heat wears flax down over time, so go cold or warm but never hot.",
   "Skip The Softener | Fabric softener coats the weave, so you lose the breathability you paid for.",
   "Dry Low, Fold Damp | Pull it out while it is still a little damp and the creases fall out on the bed.",
   "Give It Its Own Load | Zips and hooks catch the weave, so let your linen wash on its own."],
  "cover_hero"),
 ("Sleep Rituals / Slow Living", "The last hour before bed: lower the light, phone down first, turn the bed down, let the room cool.",
  ["The Last Hour. | What you do in the hour before bed matters more than what time you get into it.",
   "Lower The Light | Turn off the ceiling and leave one lamp on, so your body reads it as evening.",
   "Put The Phone Down First | Do it before you get tired, because by then you have stopped deciding.",
   "Turn The Bed Down | Do it early, so arriving at it later feels like something is waiting.",
   "Let The Room Cool | Your body drops its temperature to fall asleep, so help it along a little."],
  "cover_editorial"),
]
existing_desc = {t["desc"] for t in topics}
next_num = max([int(t["num"]) for t in topics if t["num"].isdigit()] + [0]) + 1
for ttype, desc, slides, cover in POSTS:
    if desc in existing_desc:
        say(f"topic already present: {desc[:40]}..."); continue
    row = [next_num, ttype, desc] + slides + [""] * (7 - len(slides)) + ["Approved", "",
           f"[{STAMP}] WRITER: cover={cover} · copy approved by Marcus in chat 2026-09-09 · general claims (verify): "
           + ("heat wears flax down over time" if ttype == "Care & How-To" else "your body drops its temperature to fall asleep")]
    say(f"Topics: append #{next_num} {ttype} ({cover})")
    if APPLY: tws.append_row(row, value_input_option="RAW")
    next_num += 1

print("\nDONE" if APPLY else "\nDRY RUN ONLY — re-run with --apply to write")
