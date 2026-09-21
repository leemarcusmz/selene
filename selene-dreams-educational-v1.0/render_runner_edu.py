# =============================================================================
# render_runner_edu.py — renders approved carousels (backgrounds + typography)
# VERSION 1.4 — 2026-09-10
# CHANGELOG
#   1.4  2026-09-10  CANDIDATES (Marcus's picker model, 2026-09-10). A GEN slide
#                    now generates C.GEN_CANDIDATES_COVER images for the cover
#                    and C.GEN_CANDIDATES_INTERIOR for an interior; candidate A
#                    goes under the type, every candidate is saved to the Row's
#                    Drive folder, recorded in Generation Queue col T as JSON
#                    ({slide: {A: drive:id, B: drive:id, chosen: A}}), and
#                    appended to the Image Library with the slide's brief as its
#                    description (ours = No) so nothing generated is wasted.
#                    A contact sheet (row{n}_candidates.jpg) of the raw
#                    candidates rides along with the strip for the final look;
#                    Marcus answers in column O: "3B", "5 reroll: ...".
#   1.3  2026-09-10  NETWORK RETRY. Four of the first seven live renders died
#                    overnight on Errno 49 / 32 / 54 (Mac network dropped mid
#                    Drive transfer) and were marked ERROR like a merit failure.
#                    A transient error now clears E so the arm stage re-queues
#                    the row under ARM_PER_TICK, up to RENDER_RETRIES times
#                    (counted from the row's own remarks); only then ERROR.
#   1.2  2026-09-01  BUG FIX (blocker): _zone_texts only knew the legacy
#                    templates and fed every other slide a "body" zone, which
#                    none of the reference-set templates have — every
#                    cover_*/bubble_card slide would have raised "title:
#                    required text missing". It now maps title + description for
#                    the whole reference set, renders image_only with no text at
#                    all, and fills outro from the brand constants.
#                    THE SLIDE TEXT CONTRACT (interim, needs Marcus's sign-off):
#                    one slide cell holds BOTH fields, split on the first "|" or
#                    the first line break. "LINEN'S WINTER SECRET | Cozy
#                    durability for the coldest nights." Title only is fine.
#   1.1  2026-08-28  429 quota fix: Image Library loaded once per run.
#   1.0  2026-08-28  First release. E=Ready rows: source each slide's background
#                    (REUSE from Drive / GEN via Replicate with capacity retries /
#                    FLAT), composite the approved text from Post Topic, upload
#                    to 03. Generated Images/Educational/Row {n}. FAIL-OPEN: a
#                    failed generation falls back to a flat brand background and
#                    says so in the remark — a bad background never kills a post.
# =============================================================================
import io, os, re, time, tempfile, requests
from PIL import Image
import config_edu as C
import sheets_edu as S
import library_edu as L
from templates_edu import DEFAULT_PLANS, COVER_TEMPLATES
import renderer_edu as R

def _gen_image(prompt):
    import replicate
    env = C.load_env()
    os.environ.setdefault("REPLICATE_API_TOKEN", env.get("REPLICATE_API_TOKEN", ""))
    last = None
    for attempt, wait in enumerate([0] + C.GEN_RETRY_WAITS[:C.MAX_GEN_RETRIES - 1]):
        if wait: time.sleep(wait)
        try:
            try:
                out = replicate.run(C.REPLICATE_MODEL, input={"prompt": prompt, "aspect_ratio": "4:5"})
            except Exception:
                out = replicate.run(C.REPLICATE_MODEL, input={"prompt": prompt})
            url = out[0] if isinstance(out, (list, tuple)) else out
            url = getattr(url, "url", url)
            data = requests.get(str(url), timeout=120).content
            return Image.open(io.BytesIO(data))
        except Exception as e:
            last = e
    raise RuntimeError(f"generation failed after {C.MAX_GEN_RETRIES} attempts: {last}")

def _candidates(prompt, n):
    """n generations of one prompt (each with its own capacity retries)."""
    out = []
    for _ in range(max(1, n)):
        out.append(_gen_image(prompt))
    return out


def _register_candidates(num, slide_no, brief, cands, out_folder, tmpdir):
    """Save raw candidates to Drive + Image Library. Returns {label: drive:id}."""
    import hashlib, json
    cand_folder = L.ensure_folder("candidates", out_folder)
    lib_ws = S.tab(C.TAB_LIBRARY)
    existing = lib_ws.get_all_values()
    next_id = len(existing)
    rows, ids = [], {}
    for k, img in enumerate(cands):
        label = chr(65 + k)                      # A, B, ...
        local = os.path.join(tmpdir, f"row{num}_slide{slide_no}_cand{label}.jpg")
        R.save_jpeg(img, local)
        fid, _ = L.upload_jpeg(local, os.path.basename(local), cand_folder)
        ids[label] = f"drive:{fid}"
        with open(local, "rb") as fh:
            fp = hashlib.md5(fh.read()).hexdigest()
        folder = f"{C.GENERATED_IMAGES_FOLDER_NAME}/{C.EDU_OUTPUT_SUBFOLDER}/Row {num}/candidates"
        rows.append([f"IMG-{next_id + len(rows):04d}", f"edu gen: Row {num} slide {slide_no}",
                     fp, f"drive:{fid}", f"Row {num}/candidates/{os.path.basename(local)}",
                     "", 0, "", "", "Yes",
                     brief, "", "", "", "", "No", "", folder, "No", brief])
    if rows:
        lib_ws.append_rows(rows, value_input_option="RAW")
    return ids


def _contact_sheet(cand_paths, title, out_path):
    """Raw candidates side by side, labelled 'slide N · A'. None when nothing to show."""
    from PIL import ImageDraw, ImageFont
    if not cand_paths:
        return None
    W, H, PAD, TOP, LBL = 420, 525, 24, 60, 34
    n = len(cand_paths)
    sheet = Image.new("RGB", (PAD + n * (W + PAD), TOP + H + LBL + PAD), (245, 243, 238))
    d = ImageDraw.Draw(sheet)
    try:
        f_title = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 28)
        f_lbl = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 22)
    except Exception:
        f_title = f_lbl = ImageFont.load_default()
    d.text((PAD, 18), title, fill=(40, 60, 40), font=f_title)
    for k, (label, p) in enumerate(cand_paths):
        im = Image.open(p).convert("RGB")
        im.thumbnail((W, H))
        x = PAD + k * (W + PAD)
        sheet.paste(im, (x, TOP))
        d.text((x, TOP + H + 6), label, fill=(90, 90, 90), font=f_lbl)
    sheet.save(out_path, "JPEG", quality=88)
    return out_path


def _parse_source(cell):
    """'[tmpl] KIND rest' -> (template, kind, payload)"""
    m = re.match(r"\[(\w+)\]\s+(FLAT|REUSE|GEN:)\s*(.*)", cell.strip(), re.S)
    if not m: return None
    tmpl, kind, rest = m.group(1), m.group(2).rstrip(":"), m.group(3).strip()
    return tmpl, kind, rest

OUTRO_TITLE = "Selene Dreams"
OUTRO_DESC = "Visit us at selenedreams.com"

# Templates that take a title + one small description line.
TITLE_DESC_TEMPLATES = set(COVER_TEMPLATES) | {"bubble_card", "title_card"}


def _split_text(text):
    """One sheet cell -> (title, description).
    Split on the first '|' if present, else on the first line break.
    A cell with neither is all title."""
    t = (text or "").strip()
    if "|" in t:
        a, b = t.split("|", 1)
        return a.strip(), b.strip()
    parts = t.split("\n", 1)
    return parts[0].strip(), (parts[1].strip().replace("\n", " ") if len(parts) > 1 else "")


def _zone_texts(template, text, slide_index):
    if template == "image_only":
        return {}
    if template == "outro":
        title, desc = _split_text(text)
        return {"title": title or OUTRO_TITLE, "desc": desc or OUTRO_DESC}
    if template in TITLE_DESC_TEMPLATES:
        title, desc = _split_text(text)
        return {"title": title, "desc": desc}
    # --- legacy templates -------------------------------------------------
    if template == "hook_cover": return {"title": text}
    if template == "quote": return {"quote": text}
    if template == "cta": return {"line": text, "footer": "selenedreams.com"}
    if template == "list": return {"number": str(slide_index), "body": text}
    return {"body": text}


def run_ready():
    done = 0
    topics = {t["num"]: t for t in S.topics_rows()}
    lib_cache = None
    for st in S.status_rows():
        if st["render"] != "Ready": continue
        srow = st["row"]; num = st["num"]
        S.set_status(srow, "E", "Processing")
        try:
            q = next(q for q in S.queue_rows() if q["num"] == str(num) or q["num"] == num)
            topic = topics.get(str(st["topic"])) or topics.get(st["topic"])
            if not topic: raise RuntimeError(f"topic {st['topic']} not found in Post Topic sheet")
            texts = [s for s in topic["slides"]]
            root = L.find_folder(C.GENERATED_IMAGES_FOLDER_NAME)
            edu_root = L.ensure_folder(C.EDU_OUTPUT_SUBFOLDER, root)
            out_folder = L.ensure_folder(f"Row {num}", edu_root)
            urls, remarks = [], []
            tmpdir = tempfile.mkdtemp()
            slide_no = 0
            cand_index, cand_paths = {}, []
            for i, cell in enumerate(q["sources"]):
                if not cell.strip(): continue
                parsed = _parse_source(cell)
                if not parsed: raise RuntimeError(f"slide {i+1}: unparseable source cell")
                tmpl, kind, payload = parsed
                slide_no += 1
                bg, flat = None, None
                if kind == "FLAT":
                    flat = payload.split()[0] if payload else C.ECRU
                elif kind == "REUSE":
                    img_id = payload.split()[0]
                    if lib_cache is None: lib_cache = L.library_rows()
                    lib = next((r for r in lib_cache if r["id"] == img_id), None)
                    if not lib: raise RuntimeError(f"slide {slide_no}: {img_id} not in Image Library")
                    bg = Image.open(io.BytesIO(L.download_image(lib["loc"])))
                else:  # GEN -> candidates
                    n_cand = C.GEN_CANDIDATES_COVER if slide_no == 1 else C.GEN_CANDIDATES_INTERIOR
                    try:
                        cands = _candidates(payload, n_cand)
                        bg = cands[0]
                        brief = (topic.get("briefs") or [""] * 7)[slide_no - 1] if slide_no - 1 < len(topic.get("briefs") or []) else ""
                        ids = _register_candidates(num, slide_no, brief or payload, cands, out_folder, tmpdir)
                        cand_index[str(slide_no)] = {**ids, "chosen": "A", "prompt": payload}
                        for label in sorted(ids):
                            cand_paths.append((f"slide {slide_no} · {label}",
                                               os.path.join(tmpdir, f"row{num}_slide{slide_no}_cand{label}.jpg")))
                    except Exception as e:
                        flat, bg = C.ECRU, None
                        remarks.append(f"slide {slide_no} generation failed, used flat fallback ({e})")
                text = texts[slide_no - 1] if slide_no - 1 < len(texts) else ""
                img = R.render_slide(tmpl, _zone_texts(tmpl, text, slide_no), background=bg, flat_color=flat)
                local = os.path.join(tmpdir, f"row{num}_slide{slide_no}.jpg")
                R.save_jpeg(img, local)
                fid, link = L.upload_jpeg(local, os.path.basename(local), out_folder)
                urls.append(f"https://drive.google.com/uc?id={fid}")
            qws = S.tab(C.TAB_QUEUE)
            qws.update_acell(f"P{q['row']}", f"03. Generated Images/{C.EDU_OUTPUT_SUBFOLDER}/Row {num}")
            qws.update_acell(f"Q{q['row']}", "\n".join(urls))
            if cand_index:
                import json
                qws.update_acell(f"T{q['row']}", json.dumps(cand_index))
                sheet = _contact_sheet(cand_paths, f"#{num} · generated candidates · reply in col O: 3B / 5 reroll: ...",
                                       os.path.join(tmpdir, f"row{num}_candidates.jpg"))
                if sheet:
                    L.upload_jpeg(sheet, os.path.basename(sheet), out_folder)
                remarks.append(f"{len(cand_paths)} candidate(s) on {len(cand_index)} generated slide(s); contact sheet in the Row folder")
            S.set_status(srow, "E", "Done")
            S.set_status(srow, "F", S.now_hkt().split()[0])
            S.set_status(srow, "G", S.now_hkt().split()[1])
            S.set_status(srow, "H", "Not Started")
            msg = f"rendered {slide_no} slides"
            if remarks: msg += " — " + "; ".join(remarks)
            S.add_remark(srow, "RENDER", msg)
            done += 1
        except Exception as e:
            if _is_transient(e) and _retries_so_far(srow) < RENDER_RETRIES:
                # BLOCKED, not FLAGGED: the Mac's network dropped mid-render.
                # Clear E so the arm stage re-queues it (under ARM_PER_TICK).
                S.set_status(srow, "E", "")
                S.add_remark(srow, "RENDER", f"re-queued after network error ({e})")
            else:
                S.set_status(srow, "E", "ERROR")
                S.add_remark(srow, "RENDER", f"ERROR: {e}")
    return f"{done} carousel(s) rendered"


RENDER_RETRIES = 3
_TRANSIENT = ("Errno 49", "Errno 32", "Errno 54", "Errno 60", "Errno 8",
              "Connection reset", "Broken pipe", "timed out", "Temporary failure",
              "Can't assign requested address", "[429]", "[503]")


def _is_transient(e):
    s = str(e)
    return isinstance(e, (OSError, requests.RequestException)) or any(t in s for t in _TRANSIENT)


def _retries_so_far(srow):
    try:
        cell = S.tab("Generation Status").acell(f"N{srow}").value or ""
    except Exception:
        return RENDER_RETRIES        # can't read the sheet either: don't loop
    return cell.count("re-queued after network error")
