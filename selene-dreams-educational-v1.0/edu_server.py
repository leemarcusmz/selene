# =============================================================================
# edu_server.py — Educational Carousel flow server (port 5002, poll-based)
# VERSION 2.6 — 2026-09-30
# CHANGELOG
#   2.6  2026-09-30  A FAILED TICK SAYS SO (Runner Hub p8d). /tick answered
#                    {"ok": true} whatever happened inside: a stage that raised
#                    became a "stage": "ERROR: ..." string and the response
#                    stayed 200, so poke.sh pinged healthchecks green and 14
#                    missing Drive folders went unreported for weeks. Now:
#                    - every stage error lands in results["errors"] (a list of
#                      stage names) and the body says "ok": false;
#                    - library folders missing on Drive (LibraryFoldersMissing,
#                      library_edu 2.3) are a CONFIGURATION fault -> HTTP 500
#                      on the first tick, every tick, until the Sources tab or
#                      LIBRARY_ROOTS is fixed;
#                    - any other stage error is HTTP 500 once it has failed on
#                      TICK_ERROR_ALERT_AFTER (2) consecutive ticks - a single
#                      Sheets 429 or Google 500 still logs and shows ok:false,
#                      but does not page anyone. The count lives in
#                      _state/edu-tick-errors.json and resets on success.
#                    poke.sh v1.2 turns a non-2xx into a /fail ping, so this is
#                    what makes the edu heartbeat mean something.
#   2.5  2026-09-14  SECURITY: /tick and /publish now require the shared
#                    secret, as a JSON body {"secret": ...} or an
#                    X-Selene-Secret header. They were open — the server is
#                    bound to 127.0.0.1 so this was never reachable from the
#                    network, but any local process or a browser form POST
#                    could fire a publish. /health stays open and unchanged:
#                    nothing external reaches port 5002, and the launcher
#                    reads it. com.selene.edu.plist v1.1 sends the body.
#   2.4  2026-09-11  LIBRARY stage first in the tick: index every Drive folder
#                    on the Sources tab (new shoots enter the library on their
#                    own) and describe up to one batch of undescribed images per
#                    tick (10 = one vision call), so a 40-frame shoot is fully
#                    described within an hour of being dropped in Drive.
#   2.3  2026-09-10  Adds the BRIEF stage between writer and plan: every
#                    Approved topic with slide copy and no visual briefs gets
#                    one Claude call that writes what each slide's photograph
#                    should show (Post Topic N-T, hidden). The planner matches
#                    those briefs against library descriptions.
#   2.2  2026-09-09  The arm stage now honours C.ARM_PER_TICK, so a batch of
#                    approvals drains one row per tick instead of all at once,
#                    and it reports WHICH rows it armed plus how many are still
#                    queued behind the cap.
#   2.1  2026-09-09  Adds the reroll stage between caption and notify: any row
#                    whose User Remark(s) carries "reroll <n>: <comment>" has that
#                    one slide regenerated from its original prompt plus the
#                    comment, then goes back to K=Review for another look.
#   2.0  2026-09-09  THE FULL CHAIN. One tick now runs, in order:
#                      1 writer   — draft slide copy for newly Approved topics
#                      2 plan     — image plan + queue/status rows (D=Drafted)
#                      3 arm      — D=Approved & E blank -> E=Ready (no flips)
#                      4 render   — backgrounds + typography -> Drive (E=Done)
#                      5 caption  — caption + alt text (H=Done)
#                      6 reroll   — "reroll <n>: <comment>" in col O regenerates
#                                   that one slide from its original prompt
#                      7 notify   — strip emailed, K=Review (final-look gate)
#                      8 publish  — K=Approved -> Thursday slot; fire when due
#                    Every stage is fenced: one stage failing logs and the
#                    rest still run. Same single-flight lock, same launchd poke,
#                    still no tunnel and no Apps Script.
#   1.0  2026-08-28  First release: plan -> arm -> render.
# =============================================================================
import json, os, threading, traceback
from flask import Flask, jsonify, request
import config_edu as C
import sheets_edu as S
from log_edu import log

VERSION = "2.6"
app = Flask(__name__)
_busy = threading.Event()


TICK_ERROR_ALERT_AFTER = 2          # consecutive failing ticks before HTTP 500
_ERRORS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "_state", "edu-tick-errors.json")


def _stage(results, name, fn):
    try:
        results[name] = fn()
    except Exception as e:
        results[name] = f"ERROR: {e}"
        results.setdefault("errors", []).append(name)
        # A missing Drive folder is configuration, not weather: it will not
        # heal on the next tick, so it alerts on this one.
        if e.__class__.__name__ == "LibraryFoldersMissing":
            results.setdefault("config_errors", []).append(name)
        log(f"{name} ERROR: {traceback.format_exc()}")


def _consecutive_failures(errors):
    """Update the per-stage consecutive-failure counts on disk; return the
    highest count among the stages that failed THIS tick. Never raises."""
    try:
        try:
            with open(_ERRORS_PATH) as f:
                counts = json.load(f)
        except Exception:
            counts = {}
        counts = {k: v + 1 for k, v in counts.items() if k in errors}
        for name in errors:
            counts.setdefault(name, 1)
        os.makedirs(os.path.dirname(_ERRORS_PATH), exist_ok=True)
        with open(_ERRORS_PATH, "w") as f:
            json.dump(counts, f)
        return max(counts.values()) if counts else 0
    except Exception as e:
        log(f"tick error-count bookkeeping failed: {e}")
        return TICK_ERROR_ALERT_AFTER


def _tick_response(results):
    """ok:true only when every stage ran clean. HTTP 500 when the failure is
    configuration (missing Drive folders) or has persisted across ticks."""
    errors = results.get("errors") or []
    if not errors:
        _consecutive_failures([])            # reset the counts
        return jsonify({"ok": True, **results})
    streak = _consecutive_failures(errors)
    results["consecutive"] = streak
    alert = bool(results.get("config_errors")) or streak >= TICK_ERROR_ALERT_AFTER
    body = {"ok": False, **results}
    if alert:
        log(f"tick FAILED ({', '.join(errors)}; streak {streak}) -> 500")
        return jsonify(body), 500
    log(f"tick degraded ({', '.join(errors)}; streak {streak}) -> 200 ok:false")
    return jsonify(body)


def _check_secret():
    """Accept the secret in a JSON body (how com.selene.edu sends it) or in
    an X-Selene-Secret header (handy for a manual GET). A blank configured
    secret never matches, so a missing .env fails closed."""
    if not C.WEBHOOK_SECRET:
        return False
    body = request.get_json(silent=True) or {}
    return (body.get("secret") == C.WEBHOOK_SECRET
            or request.headers.get("X-Selene-Secret") == C.WEBHOOK_SECRET)


@app.route("/health")
def health():
    return jsonify({"ok": True, "flow": "educational", "version": VERSION})


@app.route("/tick", methods=["POST", "GET"])
def tick():
    if not _check_secret():
        return jsonify({"error": "Unauthorized"}), 401
    if _busy.is_set():
        return jsonify({"ok": True, "skipped": "busy"})
    _busy.set()
    results = {}
    try:
        import writer_edu, brief_edu, plan_edu, render_runner_edu, caption_edu
        import reroll_edu, notify_edu, publish_edu
        def library():
            import library_edu, tag_library
            idx = library_edu.index_library()
            tagged = tag_library.run(only_untagged=True, limit=C.TAG_PER_TICK)
            return f"{idx}; {tagged}"
        _stage(results, "library", library)
        _stage(results, "writer", writer_edu.sync)
        _stage(results, "brief", brief_edu.run)
        _stage(results, "plan", plan_edu.sync)

        def arm():
            cap = getattr(C, "ARM_PER_TICK", 0) or 10 ** 6
            armed, waiting = [], 0
            for st in S.status_rows():
                if st["words"] == "Approved" and not st["render"]:
                    if len(armed) < cap:
                        S.set_status(st["row"], "E", "Ready")
                        armed.append(st["row"])
                    else:
                        waiting += 1
            return {"armed": armed, "waiting": waiting}
        _stage(results, "armed", arm)
        _stage(results, "render", render_runner_edu.run_ready)
        _stage(results, "caption", caption_edu.run_pending)
        _stage(results, "reroll", reroll_edu.run_pending)
        _stage(results, "notify", notify_edu.run_pending)
        _stage(results, "publish", publish_edu.run)
        log(f"tick: {results}")
        return _tick_response(results)
    finally:
        _busy.clear()


@app.route("/publish", methods=["POST"])
def publish_now():
    """Manual poke: schedule + fire without waiting for the next tick."""
    if not _check_secret():
        return jsonify({"error": "Unauthorized"}), 401
    if _busy.is_set():
        return jsonify({"ok": True, "skipped": "busy"})
    _busy.set()
    try:
        import publish_edu
        return jsonify({"ok": True, "publish": publish_edu.run()})
    finally:
        _busy.clear()


if __name__ == "__main__":
    log(f"edu_server v{VERSION} starting on port {C.SERVER_PORT}")
    app.run(host="127.0.0.1", port=C.SERVER_PORT)
