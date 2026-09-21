# =============================================================================
# redraft_batch.py — redraft a list of topics under the current writer prompt
# VERSION 1.0 — 2026-09-09
# CHANGELOG
#   1.1  2026-09-09  Reports BLOCKED (quota/auth, retry as is) separately from
#                    FLAGGED (the copy failed on merit), and STOPS on the first
#                    BLOCKED rather than burning the rest of the list against a
#                    limit that will refuse every one of them.
#   1.0  2026-09-09  One-off helper. writer_edu.sync() only touches Approved
#                    topics with empty Slide cells; after a PROMPT change the
#                    existing drafts need re-running regardless of Status. This
#                    walks a list, clears and redrafts each, and prints a
#                    before/after so nothing is lost silently. Backs the old copy
#                    up to _state/ first.
# =============================================================================
import sys, json, os, datetime
import config_edu as C
import sheets_edu as S
import plan_edu, writer_edu
from log_edu import log

nums = [n.strip() for n in sys.argv[1:] if n.strip()]
if not nums:
    raise SystemExit("usage: redraft_batch.py 1 2 4 6 7 8 9")

topics = {t["num"]: t for t in S.topics_rows()}
stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
backup = {n: topics[n]["slides"] for n in nums if n in topics}
os.makedirs(os.path.dirname(C.STATE_PATH), exist_ok=True)
bpath = os.path.join(os.path.dirname(C.STATE_PATH), f"redraft_backup_{stamp}.json")
with open(bpath, "w") as f:
    json.dump(backup, f, indent=2, ensure_ascii=False)
log(f"redraft_batch: backing up {len(backup)} topic(s) -> {bpath}")

ws = S.topic_sheet().worksheet(C.TAB_TOPICS)
ok_n = fail_n = 0
for n in nums:
    t = topics.get(n)
    if not t:
        log(f"  #{n}: not found"); continue
    existing_q = S.tab(C.TAB_QUEUE).get_all_values()
    last, i = plan_edu.rotation_state(existing_q)
    cover = plan_edu.cover_from_remark(t["remark"]) or plan_edu._next_cover(last, i, t["type"])[0]
    log(f"redraft #{n} ({t['type']}) -> {cover}")
    okd, slides, general, remark = writer_edu.draft(t, cover)
    now = S.now_hkt()
    if okd is writer_edu.BLOCKED:
        writer_edu._remark(ws, t["row"], t["remark"],
                           f"[{now}] WRITER: BLOCKED cover={cover} · {slides} · "
                           f"copy never assessed, safe to retry unchanged")
        log(f"  #{n} BLOCKED: {slides}")
        log("  STOPPING: the remaining topics would fail the same way. Re-run this "
            "script with the unfinished numbers once the limit clears.")
        fail_n += 1
        break
    if not okd:
        writer_edu._remark(ws, t["row"], t["remark"], f"[{now}] WRITER: FLAGGED cover={cover} · {slides}")
        log(f"  #{n} FLAGGED: {slides}")
        fail_n += 1
        continue
    cells = [writer_edu.cell_text(s) for s in slides] + [""] * (7 - len(slides))
    ws.update(values=[cells], range_name=f"D{t['row']}:J{t['row']}")
    note = f"[{now}] WRITER v1.1 (prompt v4): cover={cover} · redrafted {len(slides)} slide(s)"
    if general:
        note += " · GENERAL CLAIMS (verify): " + " / ".join(general)
    if remark:
        note += " · " + remark
    writer_edu._remark(ws, t["row"], t["remark"], note)
    log(f"  #{n} OK ({len(slides)} slides)")
    for k, s in enumerate(slides, 1):
        log(f"    {k}. {writer_edu.cell_text(s)}")
    ok_n += 1
log(f"redraft_batch done: {ok_n} redrafted, {fail_n} flagged. Backup: {bpath}")
