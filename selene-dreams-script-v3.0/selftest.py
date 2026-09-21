# =============================================================================
# Selene Dreams — Self Test v1.0 (2026-08-12)
# selftest.py — Check the pipeline is wired correctly, before it matters
# =============================================================================
#
# Read-only and cheap. It writes nothing to the sheet, nothing to the memory
# repo, and generates no images. The single paid call is a two-word prompt to
# the Claude CLI to confirm the model/effort flags are accepted by YOUR
# installed version — the one risk that would otherwise surface silently at
# 9am on Monday.
#
#   python3 selftest.py           # everything
#   python3 selftest.py --quick   # skip the CLI + Google checks
# =============================================================================

import argparse
import os
import shutil
import subprocess
import sys
import tempfile

PASS, FAIL, WARN = "PASS", "FAIL", "WARN"
results = []


def check(name, fn, critical=True):
    try:
        status, detail = fn()
    except Exception as e:
        status, detail = (FAIL if critical else WARN), f"{type(e).__name__}: {e}"
    results.append((status, name, detail))
    icon = {PASS: "  ok  ", FAIL: " FAIL ", WARN: " warn "}[status]
    print(f"[{icon}] {name}" + (f"\n           {detail}" if detail else ""))
    return status


# =============================================================================

def c_imports():
    import config, pipeline_state, claude_client, memory_digests  # noqa
    import caption_runner, prompt_runner, qa_runner, screen_runner  # noqa
    import outcomes_runner, research_runner, eval_runner  # noqa
    return PASS, "all modules import cleanly"


def c_config():
    import config
    missing = [a for a in ("STAGE_MODELS", "GS_COL_POST_URL",
                           "BRAND_GUIDE_GOVERNS_PROMPTS", "APIFY_TOKEN")
               if not hasattr(config, a)]
    if missing:
        return FAIL, f"config.py is missing: {', '.join(missing)}"
    governs = config.BRAND_GUIDE_GOVERNS_PROMPTS
    return PASS, (f"post URL col={config.GS_COL_POST_URL} (O) · "
                  f"brand guide governs prompts={governs} · "
                  f"{len(config.STAGE_MODELS)} stage model routes")


def c_prompts():
    import claude_client as cc
    args = {
        "caption": dict(fabric="F", product_type="P", variant="V",
                        img_dir="/tmp", n_images=2, memory_section="M",
                        week_context="W", out_path="/tmp/o.json"),
        "caption-review": dict(brand_section="B", fabric="F", product_type="P",
                               variant="V", img_dir="/tmp", n_images=2,
                               caption="c", alt_block="a", out_path="/tmp/o.json"),
        "image-prompts": dict(fabric="F", product_type="P", variant="V",
                              img_dir="/tmp", n_images=2, concept="c",
                              brand_section="B", week_context="W",
                              playbook_section="PB", out_path="/tmp/o.json"),
        "generation-qa": dict(mem="/tmp", fabric="F", product_type="P",
                              variant="V", prompt_block="1. x", img_dir="/tmp",
                              n_images=2, out_path="/tmp/o.json"),
        "screening": dict(mem="/tmp", img_dir="/tmp", cand_path="/tmp/c.json",
                          out_path="/tmp/o.json", min_score=7, smin=8, smax=12,
                          attribute_section="A"),
    }
    versions = []
    for name, kw in args.items():
        body, ver = cc.load_prompt(name)
        body.format(**kw)          # raises if a placeholder is missing
        versions.append(f"{name}={ver}")
    return PASS, " · ".join(versions)


def c_state():
    import pipeline_state as ps
    s = ps.load_state()
    weeks, rows = len(s.get("weeks", {})), len(s.get("rows", {}))
    runs = 0
    if os.path.exists(ps.RUNS_FILE):
        with open(ps.RUNS_FILE) as f:
            runs = sum(1 for _ in f)
    if weeks == 0 and rows == 0:
        return WARN, "no state recorded yet (expected — nothing has run since the upgrade)"
    return PASS, f"{weeks} week(s), {rows} row(s), {runs} run log line(s)"


def c_claude_cli():
    if not shutil.which("claude"):
        return FAIL, "claude CLI not on PATH — every agent stage will fail"
    plain = subprocess.run(["claude", "-p", "Reply with exactly: OK",
                            "--dangerously-skip-permissions"],
                           capture_output=True, text=True, timeout=180)
    if plain.returncode != 0:
        tail = (plain.stderr or plain.stdout or "").strip()[-200:]
        if "login" in tail.lower():
            return FAIL, f"claude CLI is not logged in — run `claude` then /login ({tail})"
        return FAIL, f"claude CLI failed: {tail}"

    flagged = subprocess.run(["claude", "-p", "Reply with exactly: OK",
                              "--model", "sonnet", "--effort", "low",
                              "--dangerously-skip-permissions"],
                             capture_output=True, text=True, timeout=180)
    if flagged.returncode != 0:
        tail = (flagged.stderr or flagged.stdout or "").strip()[-200:]
        return WARN, ("CLI works but rejects --model/--effort, so model routing "
                      f"is inactive (stages still run at your default): {tail}")
    return PASS, "CLI responds and accepts --model / --effort (routing is live)"


def c_memory():
    import caption_runner, memory_digests as md
    workdir = tempfile.mkdtemp(prefix="selene_selftest_")
    try:
        mem = caption_runner.clone_memory(workdir)
        if not mem:
            return FAIL, "memory repo clone failed — check github_token.txt"
        present = [f for f in ("brand-guide.md", "visual-taste.md",
                               "selections.md", "prompt-playbook.md",
                               "screening-attributes.csv", "post-outcomes.csv",
                               "generation-scores.csv", "objections.md")
                   if os.path.exists(os.path.join(mem, f))]
        print("\n           --- digests the agents will actually read ---")
        for label, text in (
                ("playbook  ", md.playbook_digest(mem)),
                ("attributes", md.attribute_digest(mem)),
                ("outcomes  ", md.outcomes_digest(mem))):
            first = text.split("\n")[0]
            print(f"           {label}: {first}")
        return PASS, f"clone ok · files present: {', '.join(present) or 'none yet'}"
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def c_google():
    import config
    from google_services import get_google_services, get_gs_sheet
    sheets, drive = get_google_services()
    queue = sheets.open_by_key(config.GOOGLE_SHEET_ID) \
        .worksheet(config.GOOGLE_SHEET_NAME)
    gs = get_gs_sheet(queue)
    if gs is None:
        return FAIL, "Generation Status tab not reachable"
    header = gs.cell(config.GS_HEADER_ROW, config.GS_COL_POST_URL).value or ""
    if "post" not in header.lower() or "url" not in header.lower():
        return WARN, (f"column O header reads '{header}' — the outcome join "
                      f"expects a Post URL column there")
    return PASS, f"sheet reachable · column O header = '{header}'"


def c_server():
    import json
    import urllib.request
    import config
    try:
        with urllib.request.urlopen(
                f"http://localhost:{config.WEBHOOK_PORT}/health", timeout=5) as r:
            data = json.loads(r.read().decode())
        return PASS, f"server up (version {data.get('version')})"
    except Exception:
        return WARN, ("server not responding on localhost — start it with the "
                      "Selene AI command before any live test")


# =============================================================================

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true",
                    help="skip the Claude CLI and Google checks")
    args = ap.parse_args()

    print("=" * 68)
    print("Selene pipeline self-test")
    print("=" * 68)

    check("Modules import", c_imports)
    check("config.py settings", c_config)
    check("Prompt files load and render", c_prompts)
    check("Pipeline state readable", c_state, critical=False)
    check("Server /health", c_server, critical=False)
    if not args.quick:
        check("Claude CLI + model routing", c_claude_cli)
        check("Memory repo + digests", c_memory)
        check("Google Sheet + column O", c_google)

    print("=" * 68)
    fails = [r for r in results if r[0] == FAIL]
    warns = [r for r in results if r[0] == WARN]
    print(f"{len(results) - len(fails) - len(warns)} passed · "
          f"{len(warns)} warning(s) · {len(fails)} failure(s)")
    for _, name, detail in fails:
        print(f"  FAIL: {name} — {detail}")
    for _, name, detail in warns:
        print(f"  warn: {name} — {detail}")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
