# =============================================================================
# Selene Dreams — Claude Client v1.0 (2026-08-12)
# claude_client.py — One way to call an agent, one way to trust its output
# =============================================================================
#
# WHAT THIS REPLACES: every runner used to build its own `claude -p` call, ask
# for "EXACTLY one JSON object", and json.load() the result. When a model
# emitted a stray backtick or a missing field, a twenty-minute screening run
# died on a parse error with nothing to show for it. Each runner also got the
# same default model regardless of whether it was doing mechanical tagging or
# adversarial reasoning.
#
# FOUR THINGS LIVE HERE:
#
#   1. MODEL ROUTING — each stage declares the model and effort it deserves
#      (config.STAGE_MODELS). Cheap mechanical passes stop paying for deep
#      reasoning; the critic pass stops being starved of it.
#   2. invoke_claude_json() — asks, validates against a schema, and on failure
#      RETRIES ONCE with the validation error fed back to the model. Most
#      malformed output is self-correcting when the model is told what broke.
#   3. VERSIONED PROMPTS — prompt text lives in prompts/*.md with a version
#      header, not as string constants scattered across five Python files.
#      The version is stamped into playbook and QA records, so a change in
#      output quality can be attributed to a change in wording.
#   4. WEEK CONTEXT — a shared brief every agent can read, so the caption
#      writer knows what the research found and the prompt writer knows what
#      the brand guide says.
# =============================================================================

import os
import re
import shutil
import subprocess
from datetime import datetime

import config

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROMPT_DIR = os.path.join(BASE_DIR, "prompts")

VERSION_RE = re.compile(r"<!--\s*VERSION:\s*([^\s>]+)\s*-->")


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


# =============================================================================
# MODEL ROUTING
# =============================================================================

def model_for(stage):
    """(model, effort) for a stage, falling back to the configured default."""
    cfg = getattr(config, "STAGE_MODELS", {}) or {}
    entry = cfg.get(stage) or cfg.get("default") or {}
    return entry.get("model"), entry.get("effort")


# =============================================================================
# INVOCATION
# =============================================================================

LOG_DIR = os.path.join(BASE_DIR, "_logs")


def _secrets():
    """Every credential that must never land in a transcript. github_token.txt
    is read directly because not every caller goes through config."""
    vals = [config.APIFY_TOKEN, config.APIFY_RUN_TOKEN,
            config.REPLICATE_API_TOKEN, config.WEBHOOK_SECRET]
    try:
        with open(os.path.join(BASE_DIR, "github_token.txt")) as f:
            tok = f.read().strip()
            if tok:
                vals.append(tok)
    except OSError:
        pass
    return [v for v in vals if v]


def _redact(text):
    """Transcripts are the pipeline's memory; they must not also be its leak.
    Added 2026-08-19 — before this, every log embedded the full prompt,
    credentials included, which made token rotation a 16-file hunt."""
    if not text:
        return text
    for v in _secrets():
        text = text.replace(v, "***REDACTED***")
    return text


def _write_log(stage, prompt, proc=None, note=""):
    """Keep what the agent actually said.

    Headless runs used to be a black box: if the CLI exited 0 but produced no
    file, the only evidence was 'claude finished but the file is missing',
    which is unactionable. The transcript is the difference between guessing
    and knowing.
    """
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = os.path.join(LOG_DIR, f"{stage or 'claude'}-{stamp}.log")
        with open(path, "w") as f:
            f.write(f"=== stage: {stage} · {datetime.now()} ===\n")
            if note:
                f.write(f"=== note: {note} ===\n")
            if proc is not None:
                f.write(f"=== exit code: {proc.returncode} ===\n")
            f.write("\n=== PROMPT ===\n")
            f.write(_redact(prompt))
            if proc is not None:
                f.write("\n\n=== STDOUT ===\n")
                f.write(_redact(proc.stdout or ""))
                f.write("\n\n=== STDERR ===\n")
                f.write(_redact(proc.stderr or ""))
        return path
    except Exception:
        return None


def invoke_claude(prompt, workdir, timeout=600, stage=None,
                  model=None, effort=None):
    """Run the Claude Code CLI headlessly. Returns (ok, message).

    Every invocation writes a transcript to _logs/ so a run that fails
    silently can still be diagnosed afterwards.
    """
    claude_bin = shutil.which("claude")
    if not claude_bin:
        return False, ("claude CLI not found on PATH. Install Claude Code "
                       "(https://claude.com/claude-code) and log in, or ask "
                       "Claude in a Selene chat to run this instead.")
    if stage and (model is None and effort is None):
        model, effort = model_for(stage)

    args = [claude_bin, "-p", prompt, "--dangerously-skip-permissions"]
    if model:
        args += ["--model", model]
    if effort:
        args += ["--effort", effort]

    try:
        proc = subprocess.run(args, cwd=workdir, capture_output=True,
                              text=True, timeout=timeout)
        logpath = _write_log(stage, prompt, proc)
        if proc.returncode != 0:
            tail = (proc.stderr or proc.stdout or "").strip()[-400:]
            # An older CLI won't know --effort/--model; retry without them
            # rather than failing the whole run over a flag.
            if ("--effort" in tail or "--model" in tail or
                    "unknown option" in tail.lower()) and (model or effort):
                log("  NOTE: this CLI rejected --model/--effort — retrying "
                    "with defaults. Update Claude Code to use model routing.")
                return invoke_claude(prompt, workdir, timeout=timeout,
                                     model=None, effort=None)
            return False, (f"claude CLI exited {proc.returncode}: {tail}"
                           + (f" · transcript: {logpath}" if logpath else ""))
        if logpath:
            log(f"  transcript: {logpath}")
        return True, "ok"
    except subprocess.TimeoutExpired:
        _write_log(stage, prompt, note=f"TIMED OUT after {timeout}s")
        return False, (f"claude CLI timed out after {timeout}s — the run was "
                       f"killed mid-work; see _logs/")
    except Exception as e:
        _write_log(stage, prompt, note=f"EXCEPTION: {e}")
        return False, f"claude CLI failed: {e}"


# =============================================================================
# SCHEMA VALIDATION
# =============================================================================
# Deliberately dependency-free and small. A schema is a dict:
#   {"field": {"type": "str|int|float|bool|list|dict", "required": True,
#              "min_len": 1, "choices": [...], "items": {<schema or type>}}}
# It exists to catch the failures that actually happen — a missing key, a
# string where a list belongs, an array of the wrong length — not to be a
# complete JSON Schema implementation.

_TYPES = {"str": str, "int": int, "float": (int, float), "bool": bool,
          "list": list, "dict": dict}


def validate(obj, schema, path="root"):
    """Returns a list of human-readable problems (empty means valid)."""
    problems = []
    if not isinstance(obj, dict):
        return [f"{path}: expected a JSON object, got {type(obj).__name__}"]
    for key, rule in (schema or {}).items():
        required = rule.get("required", True)
        if key not in obj or obj[key] is None:
            if required:
                problems.append(f"{path}.{key}: missing")
            continue
        val = obj[key]
        want = rule.get("type")
        if want and not isinstance(val, _TYPES.get(want, object)):
            problems.append(
                f"{path}.{key}: expected {want}, got {type(val).__name__}")
            continue
        if rule.get("choices") and val not in rule["choices"]:
            problems.append(
                f"{path}.{key}: '{val}' is not one of {rule['choices']}")
        if isinstance(val, (list, str)) and "min_len" in rule \
                and len(val) < rule["min_len"]:
            problems.append(
                f"{path}.{key}: needs at least {rule['min_len']} item(s), "
                f"got {len(val)}")
        if isinstance(val, list) and "exact_len" in rule \
                and len(val) != rule["exact_len"]:
            problems.append(
                f"{path}.{key}: needs exactly {rule['exact_len']} item(s), "
                f"got {len(val)}")
        if isinstance(val, list) and isinstance(rule.get("items"), dict):
            for i, item in enumerate(val):
                problems += validate(item, rule["items"], f"{path}.{key}[{i}]")
    return problems


# =============================================================================
# JSON INVOCATION WITH REPAIR
# =============================================================================

def invoke_claude_json(prompt, workdir, out_path, schema=None, stage=None,
                       timeout=600, attempts=2, model=None, effort=None):
    """Run Claude, read the JSON it wrote, validate it, and give it ONE chance
    to fix its own mistake before giving up.

    Returns (ok, result_or_message). On success the second element is the
    parsed, validated object.
    """
    import json

    current = prompt
    last_problem = ""
    for attempt in range(1, attempts + 1):
        if os.path.exists(out_path):
            try:
                os.remove(out_path)        # never validate a stale file
            except OSError:
                pass

        ok, msg = invoke_claude(current, workdir, timeout=timeout,
                                stage=stage, model=model, effort=effort)
        if not ok:
            return False, msg

        if not os.path.exists(out_path):
            last_problem = f"no file was written to {out_path}"
        else:
            try:
                with open(out_path) as f:
                    result = json.load(f)
                problems = validate(result, schema) if schema else []
                if not problems:
                    return True, result
                last_problem = "; ".join(problems[:6])
            except json.JSONDecodeError as e:
                last_problem = f"the file is not valid JSON ({e})"
            except Exception as e:
                last_problem = f"could not read the file ({e})"

        if attempt == attempts:
            break
        log(f"  Output rejected ({last_problem}) — asking for a correction...")
        current = (
            f"{prompt}\n\n---\nYOUR PREVIOUS ATTEMPT WAS REJECTED: "
            f"{last_problem}.\nWrite the corrected JSON object to {out_path} "
            f"again, complete and valid, matching the schema exactly. Do not "
            f"explain the error — just write the corrected file."
        )
    return False, f"invalid output after {attempts} attempt(s): {last_problem}"


# =============================================================================
# VERSIONED PROMPTS
# =============================================================================

def load_prompt(name):
    """Load prompts/<name>.md. Returns (text, version).

    The version header is what makes prompt changes attributable: it is
    stamped into the playbook and QA records, so 'output got better in
    September' can be traced to a specific edit rather than guessed at.
    """
    path = os.path.join(PROMPT_DIR, f"{name}.md")
    with open(path) as f:
        raw = f.read()
    m = VERSION_RE.search(raw)
    version = m.group(1) if m else "unversioned"
    body = VERSION_RE.sub("", raw, count=1).lstrip("\n")
    return body, version


# =============================================================================
# SHARED WEEK CONTEXT
# =============================================================================

def week_context(mem_dir, max_chars=2600):
    """A short brief every agent can read, assembled from memory.

    Previously each agent knew only its own slice: the caption writer had no
    idea what the research found that week, and the prompt writer had never
    read the brand guide. This gives them a common, compact view without
    making every runner parse the repo itself.
    """
    if not mem_dir or not os.path.isdir(mem_dir):
        return "No memory available this run — use best judgment."

    parts = []

    def head(path, lines, label):
        p = os.path.join(mem_dir, path)
        if not os.path.exists(p):
            return
        try:
            with open(p) as f:
                text = "".join(f.readlines()[:lines]).strip()
            if text:
                parts.append(f"{label}:\n{text}")
        except Exception:
            pass

    # Newest research report — what the market did this week.
    reports_dir = os.path.join(mem_dir, "reports")
    if os.path.isdir(reports_dir):
        try:
            newest = sorted(os.listdir(reports_dir))[-1]
            head(os.path.join("reports", newest), 25,
                 f"THIS WEEK'S RESEARCH ({newest})")
        except Exception:
            pass

    head("objections.md", 20, "BUYER OBJECTIONS worth answering")
    head("trends.md", 12, "RECENT TRENDS")

    # What actually happened after publishing — the only feedback in the
    # system that comes from real audiences rather than our own judgment.
    try:
        import memory_digests
        parts.append(memory_digests.outcomes_digest(mem_dir, limit=5))
    except Exception:
        pass

    if not parts:
        return "Memory is present but empty — use best judgment."
    out = "\n\n".join(parts)
    return out[:max_chars] + ("\n[...truncated]" if len(out) > max_chars else "")
