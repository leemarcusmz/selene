"""
chain.py — the v14 auto-chain
=============================================================================
VERSION 1.0 — 2026-08-21

WHY THIS EXISTS
    v14 removes the two manual gates (Generation Status D=Ready for images,
    G=Ready for captions). Judgement moved to the review screen, which looks
    at the finished post instead of the prompt.

THE TRAP THIS AVOIDS
    The obvious implementation — have prompt_runner write "Ready" into the
    sheet and let trigger.gs fire the webhook — DOES NOT WORK.
    trigger.gs's handleEdit is an installable ON-EDIT trigger, and Google's
    on-edit triggers fire ONLY for edits made by a human in the Sheets UI.
    Writes made through the Sheets API (which is all gspread does) do not
    fire them. The value would land in the cell and absolutely nothing would
    happen — a silent stall, the exact failure mode this project already has
    too much of.

WHAT WE DO INSTEAD
    Skip the round trip. prompt_runner, generate.py and caption_runner all
    already run ON THE MAC, and server.py is already an async job runner
    listening on localhost. So the chain simply calls the next stage directly
    through that local server. No ngrok, no Apps Script, no trigger.
    The sheet still records status honestly — it is just no longer the
    transport.

FAILURE BEHAVIOUR
    Never raises into the caller. A stage that cannot be fired writes a
    System Remark on the row so a stalled post is visible on the control
    panel and the dashboard, rather than looking like a quiet week.

KILL SWITCH
    SELENE_AUTO_CHAIN=0 in the environment disables every fire, so the
    pipeline falls straight back to the manual D/G flips.
=============================================================================
"""

import json
import os
import urllib.error
import urllib.request

import config

AUTO_CHAIN = os.getenv("SELENE_AUTO_CHAIN", "1") != "0"

LOCAL_BASE = f"http://127.0.0.1:{config.WEBHOOK_PORT}"
FIRE_TIMEOUT = 10          # the endpoints spawn a thread and return at once
HEALTH_TIMEOUT = 4


def log(msg):
    print(f"[chain] {msg}", flush=True)


# ── transport ───────────────────────────────────────────────────────────────

def _post(path, payload):
    body = json.dumps(dict(payload, secret=config.WEBHOOK_SECRET)).encode("utf-8")
    req = urllib.request.Request(
        LOCAL_BASE + path, data=body, method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=FIRE_TIMEOUT) as resp:
        return resp.status, resp.read().decode("utf-8", "replace")


def server_healthy():
    """Is 'Start Selene AI' actually running? Checked before every fire so a
    dead server produces a named remark instead of a mystery."""
    try:
        with urllib.request.urlopen(LOCAL_BASE + "/health", timeout=HEALTH_TIMEOUT) as r:
            return r.status == 200
    except Exception:
        return False


def _remark(queue_sheet, number, message):
    """Best-effort note onto the row's System Remark(s), col M."""
    if queue_sheet is None:
        return
    try:
        from google_services import get_gs_sheet, find_gs_row, gs_append_remark
        gs = get_gs_sheet(queue_sheet)
        if gs is None:
            return
        gs_append_remark(gs, find_gs_row(gs, number), message)
    except Exception as e:
        log(f"could not write remark for #{number}: {e}")


def _fire(kind, path, payload, number, queue_sheet):
    if not AUTO_CHAIN:
        log(f"AUTO_CHAIN disabled — not firing {kind} for #{number}")
        return False

    if not server_healthy():
        msg = (f"CHAIN: could not start {kind} for #{number} — the local server "
               f"is not answering on port {config.WEBHOOK_PORT}. "
               f"Start 'Selene AI', then set the status to Ready by hand.")
        log(msg)
        _remark(queue_sheet, number, msg)
        return False

    try:
        status, body = _post(path, payload)
        if 200 <= status < 300:
            log(f"{kind} fired for #{number}")
            return True
        msg = f"CHAIN: {kind} for #{number} refused (HTTP {status}): {body[:200]}"
    except urllib.error.URLError as e:
        msg = f"CHAIN: {kind} for #{number} failed to send: {e}"
    except Exception as e:
        msg = f"CHAIN: {kind} for #{number} failed: {e}"

    log(msg)
    _remark(queue_sheet, number, msg)
    return False


# ── the two links in the chain ──────────────────────────────────────────────

def fire_generation(number, queue_sheet=None):
    """Start image generation for queue #number.
    The row's Generation Status D must already read 'Ready' — generate.py
    refuses otherwise, deliberately, so a stray call cannot spend credits."""
    queue_row = int(number) + 1          # queue row = # + 1
    return _fire("image generation", "/webhook",
                 {"row_index": queue_row}, number, queue_sheet)


def fire_caption(number, queue_sheet=None):
    """Start the caption run for queue #number.
    The row's Generation Status G must already read 'Ready' — caption_runner
    refuses otherwise unless forced."""
    return _fire("caption", "/caption",
                 {"number": int(number)}, number, queue_sheet)
