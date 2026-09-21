# =============================================================================
# log_edu.py — one log function for every stage of the educational flow
# VERSION 1.0 — 2026-09-09
# CHANGELOG
#   1.0  2026-09-09  First release. Split out of edu_server so the stage
#                    modules can log without importing the Flask app.
# =============================================================================
import datetime
import config_edu as C

def log(msg):
    line = f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with open(C.LOG_PATH, "a") as f: f.write(line + "\n")
    except Exception:
        pass
