# =============================================================================
# notify_edu.py — the FINAL LOOK gate: email Marcus the strip, he flips one cell
# VERSION 1.3 — 2026-09-14
# CHANGELOG
#   1.3  2026-09-14  PER-POST MAIL OFF by default (C.EDU_NOTIFY_PER_POST).
#                    review.gs v2.1 draws educational carousels in the same
#                    approval queue as the AI ones, so this lane no longer
#                    mails per post - one weekly digest covers both. Everything
#                    else is unchanged: the strip is still built and uploaded to
#                    Drive (the review page reads the slides from Generation
#                    Queue col Q), and run_pending still sets K=Review, which is
#                    what puts the row on the page.
#   1.2  2026-09-10  CANDIDATES. When a row generated more than one image for a
#                    slide (render_runner v1.4), the contact sheet rides along
#                    as a second attachment and the mail explains the column-O
#                    grammar: "3B" to choose, "5 reroll: comment", "5 new: idea".
#                    Picker reasons (why a library image was chosen) are shown
#                    next to each reused slide.
#   1.1  2026-09-09  THE EMAIL NOW CARRIES THE PROMPTS. Marcus's picker model is
#                    "generate first, show me the prompt, I comment, it rerolls" -
#                    which only works if the prompt that made each picture is in
#                    front of him with the picture. Each slide is listed with its
#                    source (the full GEN prompt, or the reused library id) and
#                    the exact line to paste back to reroll it.
#   1.0  2026-09-09  First release. Marcus's call (2026-09-09): this lane has
#                    no tunnel or Apps Script, so the review screen cannot see
#                    it. Instead, when a row is rendered (E=Done) AND captioned
#                    (H=Done), the runner builds a one-image strip of every
#                    slide, saves it beside the slides in Drive, and emails it
#                    with the caption. Marcus approves by setting K=Approved
#                    from his phone. Mail is Gmail SMTP with an app password read
#                    from the v3.0 .env (SELENE_MAIL_FROM /
#                    SELENE_MAIL_APP_PASSWORD). If mail is not configured the
#                    strip is still saved and K still becomes Review - the
#                    pipeline never stalls on a missing password.
# =============================================================================
import os, re, io, ssl, smtplib, tempfile, shutil
from email.message import EmailMessage
from PIL import Image, ImageDraw, ImageFont
import config_edu as C
import sheets_edu as S
import library_edu as L
import render_runner_edu as RR
from caption_edu import drive_ids


from log_edu import log


def build_strip(paths, title, out_path):
    TW, TH, PAD, LAB, TOP = 300, 375, 20, 44, 58
    try:
        f_hd = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 24)
        f_lab = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 15)
    except Exception:
        f_hd = f_lab = ImageFont.load_default()
    W = PAD + len(paths) * (TW + PAD); H = TOP + TH + LAB + PAD
    sheet = Image.new("RGB", (W, H), (245, 243, 239)); d = ImageDraw.Draw(sheet)
    d.text((PAD, 18), title, font=f_hd, fill=(39, 63, 34))
    for i, p in enumerate(paths):
        cx, cy = PAD + i * (TW + PAD), TOP
        sheet.paste(Image.open(p).convert("RGB").resize((TW, TH), Image.LANCZOS), (cx, cy))
        d.rectangle([cx, cy, cx + TW - 1, cy + TH - 1], outline=(213, 210, 198))
        d.text((cx, cy + TH + 8), f"slide {i + 1}", font=f_lab, fill=(124, 137, 111))
    sheet.save(out_path, "JPEG", quality=88, optimize=True)
    return out_path


def sources_block(q):
    """Each slide with the prompt or library image that actually made it."""
    out = []
    for i, cell in enumerate(q["sources"], 1):
        if not cell.strip():
            continue
        parsed = RR._parse_source(cell)
        if not parsed:
            out.append(f"  SLIDE {i}: (unreadable source cell)"); continue
        tmpl, kind, payload = parsed
        if kind == "GEN":
            out.append(f"  SLIDE {i} [{tmpl}] GENERATED from this prompt:\n      {payload}")
        elif kind == "REUSE":
            out.append(f"  SLIDE {i} [{tmpl}] REUSED from your archive: {payload}")
            # payload = "IMG-0033 (0.82: why...)" when the picker chose it
        else:
            out.append(f"  SLIDE {i} [{tmpl}] flat colour: {payload}")
    return "\n".join(out)


def caption_for(number):
    for r in S.tab(C.TAB_CAPTION).get_all_values()[1:]:
        if r and str(r[0]) == str(number):
            return (r + [""])[1]
    return ""


def send_mail(subject, body, attachment_path, extra_paths=()):
    # The review page is the gate now; the strip has already been uploaded to
    # Drive by the caller, so skipping the send loses nothing.
    if not getattr(C, "EDU_NOTIFY_PER_POST", True):
        return False, "per-post mail off (EDU_NOTIFY_PER_POST) - review page is the gate"
    env = C.load_env()
    sender = env.get("SELENE_MAIL_FROM", "").strip()
    pw = env.get("SELENE_MAIL_APP_PASSWORD", "").replace(" ", "").strip()
    if not sender or not pw:
        return False, "mail not configured (SELENE_MAIL_FROM / SELENE_MAIL_APP_PASSWORD missing in .env)"
    msg = EmailMessage()
    msg["Subject"] = subject; msg["From"] = sender; msg["To"] = C.MAIL_TO
    msg.set_content(body)
    for p in [attachment_path] + [x for x in extra_paths if x]:
        with open(p, "rb") as f:
            msg.add_attachment(f.read(), maintype="image", subtype="jpeg",
                               filename=os.path.basename(p))
    with smtplib.SMTP_SSL(C.SMTP_HOST, C.SMTP_PORT, context=ssl.create_default_context()) as s:
        s.login(sender, pw); s.send_message(msg)
    return True, "sent"


def notify_row(q, st, topic):
    number = q["num"]
    ids = drive_ids(q["urls"])
    if not ids:
        raise RuntimeError("no image URLs on the queue row")
    tmp = tempfile.mkdtemp(prefix=f"selene_notify_{number}_")
    try:
        paths = []
        for i, fid in enumerate(ids, 1):
            p = os.path.join(tmp, f"slide{i}.jpg")
            with open(p, "wb") as f: f.write(L.download_image(f"drive:{fid}"))
            paths.append(p)
        title = f"#{number} · {topic['type']} · {(topic['slides'][0] or '').split('|')[0].strip()}"
        strip = build_strip(paths, title, os.path.join(tmp, f"row{number}_strip.jpg"))
        # save beside the slides so it is findable without the email
        root = L.find_folder(C.GENERATED_IMAGES_FOLDER_NAME)
        edu_root = L.ensure_folder(C.EDU_OUTPUT_SUBFOLDER, root)
        folder = L.ensure_folder(f"Row {number}", edu_root)
        L.upload_jpeg(strip, os.path.basename(strip), folder)
        caption = caption_for(number)
        sheet_url = f"https://docs.google.com/spreadsheets/d/{C.EDU_QUEUE_SHEET_ID}/edit"
        body = (f"Educational carousel #{number} is rendered and captioned.\n\n"
                f"Topic: {topic['type']} · {topic['desc']}\n"
                f"Slides: {len(ids)}\n\n"
                f"CAPTION\n{caption}\n\n"
                f"WHERE EACH IMAGE CAME FROM\n{sources_block(q)}\n\n"
                f"TO APPROVE: open Generation Status and set column K (Post-Status) to Approved.\n"
                f"It will take the next Thursday 21:00 New York slot.\n"
                f"Anything else in K (or leaving it) holds the post.\n\n"
                f"TO REROLL AN IMAGE: put a line like this in column O (User Remark(s)),\n"
                f"saying what you want different. The original prompt plus your comment make\n"
                f"the new one, and only that slide regenerates:\n"
                f"    reroll 3: too dark, want morning light\n"
                f"Several are fine, separated by |. The revised prompt is written back into\n"
                f"the Slide Source cell, so the sheet always shows what actually made the picture.\n\n"
                f"{sheet_url}\n")
        # contact sheet of raw candidates, if the render produced one
        extra = []
        try:
            res = L.drive().files().list(
                q=f"'{folder}' in parents and name = 'row{number}_candidates.jpg' and trashed = false",
                fields="files(id,name)").execute()
            if res.get("files"):
                cp = os.path.join(tmp, f"row{number}_candidates.jpg")
                with open(cp, "wb") as f:
                    f.write(L.download_image(f"drive:{res['files'][0]['id']}"))
                extra.append(cp)
                body += ("\nGENERATED CANDIDATES are on the second attachment (slide N · A / B).\n"
                         "Candidate A is what you see in the strip. To swap one, put the slide number and\n"
                         "letter in column O:   3B\n"
                         "To regenerate with a change:   5 reroll: warmer, show the lamp\n"
                         "To regenerate from a new idea: 5 new: a hand turning the duvet down\n"
                         "Several at once, separated by |. Every candidate is kept in the Image Library.\n")
        except Exception as e:
            body += f"\n(contact sheet not attached: {e})\n"
        sent, why = send_mail(f"[Selene] Final look · #{number} · {topic['type']}", body, strip, extra)
        return sent, why
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def run_pending():
    n = 0
    topics = {str(t["num"]): t for t in S.topics_rows()}
    queue = {str(q["num"]): q for q in S.queue_rows()}
    for st in S.status_rows():
        if st["render"] != "Done" or st["caption"] != "Done" or st["post"]:
            continue
        q = queue.get(str(st["num"]))
        if not q:
            continue
        topic = topics.get(str(q["topic"])) or {"type": q["type"], "desc": "", "slides": [""]}
        try:
            sent, why = notify_row(q, st, topic)
            S.set_status(st["row"], "K", C.POST_REVIEW)
            S.add_remark(st["row"], "NOTIFY",
                         "strip emailed, awaiting final look" if sent else f"strip saved to Drive; {why}")
            log(f"notify #{st['num']}: {'emailed' if sent else why}")
            n += 1
        except Exception as e:
            S.add_remark(st["row"], "NOTIFY", f"ERROR: {e}")
            log(f"notify #{st['num']} ERROR: {e}")
    return f"{n} row(s) sent for final look"


if __name__ == "__main__":
    print(run_pending())
