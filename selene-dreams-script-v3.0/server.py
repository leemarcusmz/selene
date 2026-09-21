# =============================================================================
# Selene Dreams — Webhook Server
# server.py — Flask webhook server
#
# VERSION 3.7 — 2026-09-14
#   v3.7  2026-09-14  SECURITY. /state and /state/summary now require the
#                     X-Selene-Secret header — they were unauthenticated GETs
#                     and were readable over the public ngrok tunnel by anyone
#                     holding the URL. /health stays open because Apps Script
#                     pings it as a tunnel liveness check, but no longer
#                     reports SERVER_VERSION or the Replicate model. Flask now
#                     binds 127.0.0.1 instead of 0.0.0.0, so port 5001 is no
#                     longer answerable from the local network; ngrok still
#                     reaches it over loopback exactly as before.
#
# CHANGELOG
#   v3.6  2026-09-09  /reel endpoint: runs the TRIAL REEL lane (reel_runner).
#                     Poked every 15 min by com.selene.reel. Independent of the
#                     carousel lane and of Google Sheets — reel_runner keeps its
#                     own state in _state/reels.json — so a Sheets or Drive
#                     outage cannot stop trial reels, and a broken reel cannot
#                     touch the publishing flow. Single-flight, same as /publish.
#                     reel_runner is imported LAZILY inside the handler: a syntax
#                     error in the new lane must not stop the whole server from
#                     booting the way a top-level import would.
#   v3.5  2026-08-25  /publish endpoint: sweeps Generation Status for approved
#                     rows whose scheduled moment has passed and posts them to
#                     Instagram (publish_runner.run). Poked every 15 min by the
#                     com.selene.publish LaunchAgent — the same curl-the-local-
#                     server pattern as Monday research, chosen because launchd
#                     cannot read ~/Desktop directly (macOS privacy) but this
#                     server, started from Terminal, can.
#   v3.4  2026-08-19  Self-freeing port: on startup the server finds any OLD
#                     server.py still holding the port and terminates it, so
#                     "Address already in use" restarts are gone. One VERSION
#                     constant now feeds the banner AND /health (they had
#                     drifted: banner said 3.3, /health said 3.0).
#   v3.3  earlier     state + QA + outcomes endpoints.
# =============================================================================

import logging
import threading
from datetime import datetime

from flask import Flask, request, jsonify

import config
import pipeline_state
from google_services import get_google_services
from generate import process_row, process_all_ready_rows
from caption_runner import run_caption
from qa_runner import run_qa
from outcomes_runner import run_outcomes
from prompt_runner import run_selection
from screen_runner import run_screen
from publish_runner import run as run_publish
from research_runner import run_research

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

SERVER_VERSION = "3.7"


def _free_own_port(port):
    """Terminate any OLD server.py holding our port.

    The launcher's cleanup step misses the previous server, so every restart
    used to die with "Address already in use" until Marcus ran
    `lsof -ti :5001 | xargs kill` by hand (2026-08-19). Guarded: only kills
    processes whose command line contains server.py — anything else on the
    port is reported, not killed.
    """
    import os as _os
    import signal as _signal
    import subprocess as _sp
    import time as _time
    try:
        out = _sp.run(["lsof", "-ti", f":{port}"], capture_output=True,
                      text=True, timeout=10).stdout.split()
    except Exception:
        return
    me = _os.getpid()
    for pid_s in out:
        try:
            pid = int(pid_s)
            if pid == me:
                continue
            cmd = _sp.run(["ps", "-p", pid_s, "-o", "command="],
                          capture_output=True, text=True, timeout=5).stdout
            if "server.py" not in cmd:
                print(f"  ! port {port} held by non-server process {pid}: "
                      f"{cmd.strip()[:80]} — NOT killing it, startup will fail")
                continue
            print(f"  → stopping previous server (pid {pid})")
            _os.kill(pid, _signal.SIGTERM)
            for _ in range(20):                    # up to 2 s to exit cleanly
                _time.sleep(0.1)
                try:
                    _os.kill(pid, 0)
                except OSError:
                    break
            else:
                _os.kill(pid, _signal.SIGKILL)
        except (ValueError, OSError):
            continue


app = Flask(__name__)


def _process_row_in_background(row_index):
    logger.info(f"Background thread started for row {row_index}")
    try:
        sheets, drive = get_google_services()
        sheet = sheets.open_by_key(config.GOOGLE_SHEET_ID).worksheet(
            config.GOOGLE_SHEET_NAME
        )
        with pipeline_state.stage(pipeline_state.GENERATION,
                                  row=row_index - 1) as st:
            ok, msg = process_row(row_index, sheet, drive)
            (st.ok if ok else st.failed)(msg)
        if ok:
            logger.info(f"Row {row_index} — SUCCESS: {msg}")
            # Generation QA: score what we actually produced against the same
            # rubric the reference screener uses, and tie it back to the
            # prompts in prompt-playbook.md. Observer only — a QA failure
            # never invalidates a generation that already succeeded.
            number = row_index - 1
            qa_ok, qa_msg = run_qa(number, sheets, drive)
            logger.info(f"Row {row_index} — QA {'ok' if qa_ok else 'skipped'}: "
                        f"{qa_msg}")
        else:
            logger.warning(f"Row {row_index} — FAILED: {msg}")
    except Exception as e:
        logger.error(f"Row {row_index} — background thread crashed: {e}")


def _process_all_in_background():
    logger.info("Batch processing started...")
    try:
        sheets, drive = get_google_services()
        sheet = sheets.open_by_key(config.GOOGLE_SHEET_ID).worksheet(
            config.GOOGLE_SHEET_NAME
        )
        succ, fail = process_all_ready_rows(
            sheet, drive, filter_current_month=False
        )
        logger.info(f"Batch complete — {succ} succeeded, {fail} failed")
    except Exception as e:
        logger.error(f"Batch processing error: {e}")


def _start_background(target, args=()):
    t = threading.Thread(target=target, args=args, daemon=True)
    t.start()
    return t


def _check_secret(data):
    return data and data.get("secret") == config.WEBHOOK_SECRET


def _check_header_secret():
    """Auth for GET routes, which carry no JSON body. Same shared secret as
    the POST routes, passed as a header instead."""
    return request.headers.get("X-Selene-Secret") == config.WEBHOOK_SECRET


@app.route("/health", methods=["GET"])
def health():
    """Deliberately unauthenticated and deliberately empty: Apps Script pings
    this to tell "tunnel up" from "tunnel down" (ngrok answers 404 for a
    domain with no live tunnel). It must not report version or model — that
    is free reconnaissance for anyone who finds the URL."""
    return jsonify({"status": "ok"})


@app.route("/state", methods=["GET"])
def state():
    """Whole-pipeline state in one read — week-level and row-level. This is
    the endpoint any dashboard should consume rather than re-deriving state
    from the sheet, the repo and Drive separately."""
    if not _check_header_secret():
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify(pipeline_state.load_state())


@app.route("/state/summary", methods=["GET"])
def state_summary():
    if not _check_header_secret():
        return jsonify({"error": "Unauthorized"}), 401
    return pipeline_state.summary(), 200, {"Content-Type": "text/plain"}


@app.route("/webhook", methods=["POST"])
def webhook():
    """Triggered by trigger.gs when a row's Status is set to Ready."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Missing JSON body"}), 400
    if not _check_secret(data):
        return jsonify({"error": "Unauthorized"}), 401
    row_index = data.get("row_index")
    if not isinstance(row_index, int) or row_index < 2:
        return jsonify({"error": "Invalid row_index (must be int >= 2)"}), 400
    logger.info(f"Webhook received for row {row_index}")
    _start_background(_process_row_in_background, args=(row_index,))
    return jsonify({
        "success": True,
        "message": f"Processing row {row_index} in background.",
    }), 200


# In-flight caption runs, keyed by queue # — prevents double-fires while a
# row is already being captioned (G has no 'Processing' state by design).
_caption_inflight = set()
_caption_lock = threading.Lock()


def _run_caption_in_background(number):
    logger.info(f"Caption thread started for #{number}")
    try:
        ok, msg = run_caption(number)
        (logger.info if ok else logger.warning)(
            f"Caption #{number} — {'SUCCESS' if ok else 'FAILED'}: {msg}")
    except Exception as e:
        logger.error(f"Caption #{number} — thread crashed: {e}")
    finally:
        with _caption_lock:
            _caption_inflight.discard(number)


@app.route("/caption", methods=["POST"])
def caption():
    """Triggered by trigger.gs when Generation Status col G is set to Ready."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Missing JSON body"}), 400
    if not _check_secret(data):
        return jsonify({"error": "Unauthorized"}), 401
    number = data.get("number")
    if not isinstance(number, int) or number < 1:
        return jsonify({"error": "Invalid number (must be int >= 1)"}), 400
    with _caption_lock:
        if number in _caption_inflight:
            return jsonify({
                "success": True,
                "message": f"#{number} caption run already in progress.",
            }), 200
        _caption_inflight.add(number)
    logger.info(f"Caption webhook received for #{number}")
    _start_background(_run_caption_in_background, args=(number,))
    return jsonify({
        "success": True,
        "message": f"Captioning #{number} in background.",
    }), 200


_research_running = threading.Event()


def _run_research_in_background():
    logger.info("Weekly research thread started")
    try:
        ok, msg = run_research()
        (logger.info if ok else logger.warning)(
            f"Weekly research — {'SUCCESS' if ok else 'FAILED'}: {msg}")
    except Exception as e:
        logger.error(f"Weekly research — thread crashed: {e}")
    finally:
        _research_running.clear()


@app.route("/research", methods=["POST"])
def research():
    """Triggered by Apps Script Monday mornings (and re-poked every 15 min
    until the week's candidates file exists) — runs the weekly IG research
    locally, since the cloud environment is blocked from Apify."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Missing JSON body"}), 400
    if not _check_secret(data):
        return jsonify({"error": "Unauthorized"}), 401
    if _research_running.is_set():
        return jsonify({"success": True,
                        "message": "Research already running."}), 200
    _research_running.set()
    logger.info("Research webhook received — starting weekly run")
    _start_background(_run_research_in_background)
    return jsonify({"success": True,
                    "message": "Weekly research running in background."}), 200


_screen_inflight = set()
_screen_lock = threading.Lock()


def _run_screen_in_background(week):
    logger.info(f"Screening thread started for week {week}")
    try:
        ok, msg = run_screen(week)
        (logger.info if ok else logger.warning)(
            f"Screening {week} — {'SUCCESS' if ok else 'FAILED'}: {msg}")
    except Exception as e:
        logger.error(f"Screening {week} — thread crashed: {e}")
    finally:
        with _screen_lock:
            _screen_inflight.discard(week)


@app.route("/screen", methods=["POST"])
def screen():
    """Triggered by the Apps Script poller when a new candidates file exists
    but no shortlist yet — runs the visual brand screening."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Missing JSON body"}), 400
    if not _check_secret(data):
        return jsonify({"error": "Unauthorized"}), 401
    week = data.get("week")
    if not isinstance(week, str) or len(week) != 10:
        return jsonify({"error": "Invalid week (YYYY-MM-DD)"}), 400
    with _screen_lock:
        if week in _screen_inflight:
            return jsonify({"success": True,
                            "message": f"{week} screening already running."}), 200
        _screen_inflight.add(week)
    logger.info(f"Screening webhook received for week {week}")
    _start_background(_run_screen_in_background, args=(week,))
    return jsonify({"success": True,
                    "message": f"Screening week {week} in background."}), 200


def _run_selection_in_background(payload):
    week = payload.get("week", "?")
    logger.info(f"Selection thread started for week {week}")
    try:
        ok, msg = run_selection(payload)
        (logger.info if ok else logger.warning)(
            f"Selection week {week} — {'SUCCESS' if ok else 'FAILED'}: {msg}")
    except Exception as e:
        logger.error(f"Selection week {week} — thread crashed: {e}")


@app.route("/select", methods=["POST"])
def select():
    """Triggered by the Selene Picks web app when a teammate wins the week."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Missing JSON body"}), 400
    if not _check_secret(data):
        return jsonify({"error": "Unauthorized"}), 401
    picks = data.get("picks")
    if not isinstance(picks, list) or not picks or len(picks) > 5:
        return jsonify({"error": "Invalid picks (1-5 required)"}), 400
    logger.info(
        f"Selection webhook: week {data.get('week')} by {data.get('picker')} "
        f"— {len(picks)} pick(s)")
    _start_background(_run_selection_in_background, args=(data,))
    return jsonify({"success": True,
                    "message": f"Generating prompts for {len(picks)} pick(s)."}), 200


def _run_qa_in_background(number):
    try:
        ok, msg = run_qa(number)
        (logger.info if ok else logger.warning)(
            f"QA #{number} — {'SUCCESS' if ok else 'SKIPPED'}: {msg}")
    except Exception as e:
        logger.error(f"QA #{number} — thread crashed: {e}")


@app.route("/qa", methods=["POST"])
def qa():
    """Manual re-run of generation QA for one row (it normally runs itself
    right after a successful generation)."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Missing JSON body"}), 400
    if not _check_secret(data):
        return jsonify({"error": "Unauthorized"}), 401
    number = data.get("number")
    if not isinstance(number, int) or number < 1:
        return jsonify({"error": "Invalid number (must be int >= 1)"}), 400
    logger.info(f"QA webhook received for #{number}")
    _start_background(_run_qa_in_background, args=(number,))
    return jsonify({"success": True,
                    "message": f"Scoring #{number} in background."}), 200


def _run_outcomes_in_background():
    try:
        ok, msg = run_outcomes()
        (logger.info if ok else logger.warning)(
            f"Outcome join — {'SUCCESS' if ok else 'FAILED'}: {msg}")
    except Exception as e:
        logger.error(f"Outcome join — thread crashed: {e}")


@app.route("/outcomes", methods=["POST"])
def outcomes():
    """Match published posts back to the rows, prompts and QA scores that
    produced them. Safe to call repeatedly — it rewrites the CSV each time,
    because engagement keeps moving after publication."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Missing JSON body"}), 400
    if not _check_secret(data):
        return jsonify({"error": "Unauthorized"}), 401
    logger.info("Outcome join requested")
    _start_background(_run_outcomes_in_background)
    return jsonify({"success": True,
                    "message": "Joining post outcomes in background."}), 200


_publish_running = threading.Event()


def _run_publish_in_background():
    try:
        rc = run_publish()
        (logger.info if rc == 0 else logger.warning)(
            f"Publish sweep finished (exit {rc})")
    except Exception as e:
        logger.error(f"Publish sweep — thread crashed: {e}")
    finally:
        _publish_running.clear()


@app.route("/publish", methods=["POST"])
def publish():
    """Publish every approved row whose scheduled time has passed.
    Poked every 15 minutes by the com.selene.publish LaunchAgent; safe to call
    by hand. Single-flight: a sweep that is still running (a real publish takes
    a minute or two) makes overlapping pokes no-ops rather than double-posts."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Missing JSON body"}), 400
    if not _check_secret(data):
        return jsonify({"error": "Unauthorized"}), 401
    if _publish_running.is_set():
        return jsonify({"success": True,
                        "message": "Publish sweep already running."}), 200
    _publish_running.set()
    logger.info("Publish sweep requested")
    _start_background(_run_publish_in_background)
    return jsonify({"success": True,
                    "message": "Publish sweep started in background."}), 200


_reel_running = threading.Event()


def _run_reel_in_background():
    try:
        import reel_runner            # lazy: see the v3.6 changelog note
        reel_runner.run()
        logger.info("Trial reel tick finished")
    except Exception as e:
        logger.error(f"Trial reel tick — thread crashed: {e}")
    finally:
        _reel_running.clear()


@app.route("/reel", methods=["POST"])
def reel():
    """Run one tick of the trial-reel lane.

    A tick usually does nothing: the lane decides for itself whether a video is
    eligible and whether the cadence window is open, so most pokes are no-ops.
    That is the design — Marcus drops files and never schedules anything.
    Single-flight, because Meta's transcode step makes a real run take minutes."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Missing JSON body"}), 400
    if not _check_secret(data):
        return jsonify({"error": "Unauthorized"}), 401
    if _reel_running.is_set():
        return jsonify({"success": True,
                        "message": "Trial reel tick already running."}), 200
    _reel_running.set()
    logger.info("Trial reel tick requested")
    _start_background(_run_reel_in_background)
    return jsonify({"success": True,
                    "message": "Trial reel tick started in background."}), 200


@app.route("/process-all", methods=["POST"])
def process_all():
    """Manual batch trigger for all Ready rows (ignores month filter)."""
    data = request.get_json(silent=True)
    if not _check_secret(data):
        return jsonify({"error": "Unauthorized"}), 401
    logger.info("Manual batch trigger received")
    _start_background(_process_all_in_background)
    return jsonify({
        "success": True,
        "message": "Batch processing started.",
    }), 200


if __name__ == "__main__":
    print("=" * 60)
    print(f"Selene Dreams — Webhook Server v{SERVER_VERSION} (self-freeing port)")
    print(f"Started:  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Port:     {config.WEBHOOK_PORT}")
    print()
    print("Endpoints:")
    print(f"  GET  http://localhost:{config.WEBHOOK_PORT}/health")
    print(f"  POST http://localhost:{config.WEBHOOK_PORT}/webhook      (image generation)")
    print(f"  POST http://localhost:{config.WEBHOOK_PORT}/caption      (caption generation)")
    print(f"  POST http://localhost:{config.WEBHOOK_PORT}/select       (weekly pick → prompts)")
    print(f"  POST http://localhost:{config.WEBHOOK_PORT}/research     (weekly IG research, local)")
    print(f"  POST http://localhost:{config.WEBHOOK_PORT}/screen       (visual brand screening)")
    print(f"  POST http://localhost:{config.WEBHOOK_PORT}/qa           (generation QA re-run)")
    print(f"  POST http://localhost:{config.WEBHOOK_PORT}/outcomes     (join published posts to rows)")
    print(f"  GET  http://localhost:{config.WEBHOOK_PORT}/state        (whole-pipeline state)")
    print(f"  POST http://localhost:{config.WEBHOOK_PORT}/process-all")
    print()
    print("Expose to the internet with ngrok:")
    print(f"  ngrok http {config.WEBHOOK_PORT}")
    print("=" * 60)
    _free_own_port(config.WEBHOOK_PORT)
    app.run(host="127.0.0.1", port=config.WEBHOOK_PORT, debug=False)
