"""
run_reel_tests.py — offline harness for the trial-reel metrics readback
=============================================================================
VERSION 1.7 — 2026-09-11

WHY THIS EXISTS
    Three bugs in this lane reached Marcus's terminal instead of mine, and all
    three had the same shape: code that parsed, imported and read correctly,
    but had never actually been RUN.

        Client.auth          — gspread 6 removed it; I checked the source, not
                               the runtime.
        No module named PIL  — Pillow was installed for a different python than
                               the one that runs this.
        status() NameError   — referenced a parameter it does not have. Shipped
                               2026-09-09, found 2026-09-10 by reading it again.
        --metrics-now        — filled BOTH real windows with one off-schedule
                               reading, closing them forever. The harness tested
                               that force returned every window; it never asked
                               whether it SHOULD. A test can pass and still be
                               asking the wrong question.

    So the metrics readback is not allowed to ship on a syntax check. Every
    behaviour that matters is exercised against a stubbed Graph API here:
    metrics supported, metrics partially supported, metrics not supported at
    all, an expired token, a sheet outage, the window schedule, and the two
    cases the sheet must never confuse — "0 views" and "cannot see views".

    NO NETWORK, NO CREDENTIALS, NO SIDE EFFECTS. Run it before touching
    anything in reel_metrics.py or reel_sheet.py.

USAGE
    python3 _tests/run_reel_tests.py

    Each file runs in its own process on purpose: they install different fakes
    into sys.modules, and sharing an interpreter would let one test's stub
    answer another test's question.
=============================================================================
"""

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LANE = os.path.dirname(HERE)

FILES = [
    ("negotiation", "test_metrics_negotiation.py"),
    ("resilience", "test_metrics_resilience.py"),
    ("sheet write", "test_metrics_sheet.py"),
    ("windows + probe", "test_metrics_windows.py"),
    ("music decision", "test_music_decision.py"),
    ("drive recursion", "test_drive_recursion.py"),
    ("9:16 framing", "test_framing.py"),
    ("size caps", "test_size_caps.py"),
    ("sync lock", "test_sync_lock.py"),
    ("intake persistence", "test_intake_persist.py"),
]


def main():
    failed = []
    for label, name in FILES:
        print(f"\n=== {label} ({name}) " + "=" * (46 - len(label) - len(name)))
        r = subprocess.run([sys.executable, os.path.join(HERE, name)],
                           cwd=LANE, capture_output=True, text=True)
        for line in r.stdout.splitlines():
            if line.startswith("[reel_"):
                continue
            print(line)
        if r.returncode:
            failed.append(label)
            print(r.stderr[-800:])

    print()
    if failed:
        print(f"FAILED: {', '.join(failed)}\n")
        return 1
    print("All reel metrics tests pass.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
