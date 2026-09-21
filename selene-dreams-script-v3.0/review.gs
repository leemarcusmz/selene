/**
 * review.gs — Selene Dreams · the approval screen
 * ============================================================================
 * VERSION 2.5 — 2026-09-16          (page footer shows REVIEW_BUILD)
 *
 * WHAT THIS IS
 *   The single human gate in the pipeline. Every post that has finished
 *   generating (Generation Status D=Done) and captioning (G=Done) and has not
 *   yet been dealt with (J blank / "Not Started") is drawn here, and you
 *   approve, drop slides, reorder, reroll, or reject. Approved posts publish
 *   themselves (publish_runner.py) on the scheduled date.
 *
 * WHERE IT LIVES
 *   Apps Script allows exactly ONE doGet per project, so this is routed from
 *   picker.gs:  ?view=review  ->  doGetReview_()
 *   Same web-app URL, same access. Edit the EXISTING deployment -> New version.
 *
 * WHAT IT WRITES  (Generation Status tab, gid 654976467, data from row 4)
 *   J  Post Status   -> "Scheduled" | "Rejected" | "" (cancel)
 *   K  Scheduled Date
 *   N  User Remark(s)-> reject reason
 *   P  Approved Slides -> e.g. "3,1,2" in DISPLAYED order (created if absent)
 *   D  -> "Ready" on reroll (trigger.gs fires the webhook; generate.py redoes
 *         the slide named in the last REROLL remark)
 *   Generated Caption tab col B is rewritten in place if you edit the caption.
 *   Column O (post URL) is written by publish_runner, never by this page.
 *   EDU sheet (RV_EDU_SHEET_ID) Generation Status: K Approved/Rejected/Review,
 *   L cleared on unapprove, P "Approved Slides" (v2.5), N remark, O reroll
 *   instruction. Its Generated Caption col B on caption edit.
 *
 * WHAT IT READS FOR THE CALENDAR
 *   AI carousel (AI): this sheet — J/K/L/O.
 *   Educational (ED): the educational queue sheet (RV_EDU_SHEET_ID) — K/L/M
 *     on its Generation Status tab, permalink from its queue col R.
 *   Reel / Trial reel (RE/TR): optional GET <Mac>/calendar via WEBHOOK_URL's
 *     host, ONLY when Script Property RV_CALENDAR_EXTERNAL = '1'. Not built on
 *     the Mac yet (2026-09-09); leave the property unset until it is. The page
 *     degrades silently to AI+ED. See rvCalendarExternal_().
 *
 * COSTS
 *   Drop = free.  Reroll = $0.24 (one image). RV_MAX_REROLLS bounds the
 *   slot-machine, not the wallet.
 *
 * CHANGELOG
 *   2.5  2026-09-16  Seven review-page fixes from Marcus's 2026-09-16 list.
 *                    Build 2026-09-16.a.
 *                    1 FIX: approving an EDUCATIONAL post left it in WAITING ON
 *                      YOU. The server wrote K=Approved fine (#10/#11 confirmed
 *                      on the sheet) but the client success handler read
 *                      r.kept.length, which the edu reply never had — a
 *                      TypeError before removePending/refresh ran. Second click
 *                      then said "already Approved". Handler now branches on
 *                      r.lane and every approve reply carries kept.
 *                    1 NEW: SCHEDULED sidebar group — AI rows J=Scheduled and
 *                      edu rows K=Approved/Scheduled, sorted by date. Opens a
 *                      read-only view (slides in approved order + caption) with
 *                      Reschedule/Cancel (AI) or Unapprove (edu: K back to
 *                      Review, L cleared — reviewCancel handles 'ED-' ids).
 *                    2 NEW: click any slide to enlarge (lightbox, ‹ › keys,
 *                      Open in Drive for the full file).
 *                    3+4 NEW: Drop / Undo drop and ◀ ▶ move buttons are visible
 *                      on every slide in BOTH lanes; the final-order strip
 *                      (drag) now shows for edu too. Edu keeps its cover fixed
 *                      at slide 1 (the title lives on it — reroll it instead).
 *                      Edu approve writes col P "Approved Slides" on the edu
 *                      Generation Status tab; publish_edu.py v1.1 honours it
 *                      (blank P = all slides, as before).
 *                    5 FIX: AI reroll never reached the Mac. reviewReroll set
 *                      D=Ready with setValue(), and an installable on-edit
 *                      trigger does NOT fire for script edits — row 27 sat at
 *                      Ready since 2026-09-08. reviewReroll now calls Code.gs's
 *                      sendWebhook() itself after flushing; on failure D goes
 *                      back to Done and the page says the Mac was unreachable.
 *                      HONEST LABEL: generate.py has no single-slide mode — a
 *                      reroll regenerates EVERY slide of the post ($0.24 × N)
 *                      and re-runs the caption. The UI now says so. NEW
 *                      reviewUnreroll(n) withdraws a reroll still at Ready
 *                      (D back to Done) — the REGENERATING row is clickable.
 *                    7 NEW: the calendar day panel shows each post's slides
 *                      (lazy thumbnails), not just its title.
 *                    (6 — this week's missing rows — was a prompt_runner
 *                      failure on the Mac, not this page; see the chat.)
 *   2.4  2026-09-15  FIX: educational posts showed "0 slides" and no images.
 *                    rvDriveIds_() only recognised /file/d/<id> links, but the
 *                    educational renderer writes uc?id=<id> links to col Q, so
 *                    every ED post reached the page with an empty slideIds and
 *                    nothing to thumbnail (no error, just blank). The parser now
 *                    accepts /file/d/, uc?id=, open?id=, thumbnail?id= and bare
 *                    ids, de-duplicated in slide order. Build 2026-09-15.a.
 *   2.2  2026-09-14  Educational rerolls now happen ON THE PAGE. Each ED slide
 *                    carries a Reroll button that opens a one-line comment box;
 *                    that comment IS the instruction, which is why this cannot be
 *                    the AI lane's single click. Submitting writes col O as
 *                    '<n> reroll: <why>' and that lane regenerates on its next
 *                    tick (~16 min) - still no webhook. The row stays in the
 *                    queue showing the current image until the new one lands.
 *   2.1  2026-09-14  BOTH LANES ON ONE PAGE. Educational carousels now appear
 *                    in the approval queue beside the AI ones, not just on the
 *                    calendar. They carry id 'ED-<n>' so they can never collide
 *                    with an AI row of the same number, and every surface
 *                    labels them EDUCATIONAL.
 *                    • rvEduPending_() reads the educational sheet: render E=Done,
 *                      caption H=Done, K blank or 'Review'. Slides come from
 *                      Generation Queue col Q, so the existing thumbnail path is
 *                      reused unchanged.
 *                    • Approve writes K='Approved' — that lane picks its own
 *                      Thursday, so ED cards show no date picker. Reject writes
 *                      K='Rejected' (inert: only 'Approved' publishes). Reroll
 *                      writes col O in that lane's grammar '<n> reroll: <why>'
 *                      and its server picks it up within 16 minutes — no webhook.
 *                    • Slides are rendered with text baked in, so drop/reorder is
 *                      disabled for ED; approve / reject / reroll only.
 *                    • Weekly Action emails: '[SELENE DREAMS] Weekly Action -
 *                      Carousel Review', with Date, Flow Hub and a Weekly Brief
 *                      covering both lanes. Digest sends once a week
 *                      (RV_DIGEST_DOW); publish failures still mail immediately.
 *   2.3  2026-09-14  Weekly Action digest now goes to RV_DIGEST_EMAILS —
 *                    Marcus + Charles, the same two the picker invites — rather
 *                    than RV_NOTIFY_EMAIL alone. Publish-failure mail is
 *                    unchanged and stays Marcus-only: it is an operational
 *                    alert, not a review worklist. Keep RV_DIGEST_EMAILS in
 *                    step with picker.gs TEAMMATE_EMAILS by hand.
 *   2.0  2026-09-09  REDESIGN (Claude Design round 2, desktop + mobile).
 *                    • One responsive page. >= 900px: 3-column desktop
 *                      (sidebar queue + month calendar | main pane).
 *                      < 900px: two tabs (Queue / Calendar) + a pushed post
 *                      detail screen; menus and pickers are bottom sheets.
 *                    • Sidebar groups: NEEDS ATTENTION (J=Hold), WAITING ON
 *                      YOU, REGENERATING (rows mid-reroll).
 *                    • Calendar shows a COUNT per day + type dots (AI/ED/RE/
 *                      TR); click a day for the day panel with per-post
 *                      actions (Cancel / Retry / Reschedule / open on IG).
 *                      Every day selectable; several posts per day allowed;
 *                      the date picker defaults to the next open Tue/Thu/Sat.
 *                    • Per-slide "···" menu: Reroll (attempt n of 2), Move
 *                      earlier/later, Make cover, Open in Drive.
 *                    • Reject reason inline, required. Caption QA notes
 *                      collapsible. Cover label + cover-changed warning.
 *                    • Failed posts open read-only with a plain-language
 *                      reason (rvFailureReason_) above the raw remark and
 *                      Retry now / Reschedule / Cancel.
 *                    • NEW server function reviewReschedule(n, date) and
 *                      reviewState() (full page state for client refresh).
 *                    • REMOVED the posting kit and manual post-URL entry:
 *                      publish_runner fills column O. reviewRecordUrl() is
 *                      kept as a server function for emergencies but has no
 *                      UI.
 *                    • Page returns instantly; thumbnails load lazily via
 *                      reviewThumb() for the SELECTED post only, 2 at a time.
 *                    • Fonts: Archivo + IBM Plex Mono from Google Fonts with
 *                      system fallbacks (HtmlService allows the stylesheet).
 *   1.7  2026-08-26  Slide REORDER at review; approve saves col P in the
 *                    displayed order; first kept slide = cover.
 *   1.6  2026-08-26  FIX: page hung — thumbnails now load after paint.
 *   1.5  2026-08-25  FIX: notification email linked a dead deployment.
 *   1.4  2026-08-25  Scheduled section + email notifications (reviewNotifyTick).
 *   1.3  2026-08-24  DriveApp thumbnail tried first.
 *   1.2  2026-08-24  Thumbnail failure reporting; no full-file fallback.
 *   1.1  2026-08-21  Every global namespaced RV_/rv (the globals rule).
 *   1.0  2026-08-21  First build.
 *
 * GLOBALS RULE: every global here is prefixed RV_ / rv / review. All .gs
 * files share one scope; a collision is a SyntaxError that kills every
 * trigger in the project.
 * ============================================================================
 */

var REVIEW_BUILD = '2026-09-16.a';

// ── Sheet geometry ──────────────────────────────────────────────────────────
var RV_GS_TAB          = 'Generation Status';
var RV_QUEUE_TAB       = 'Generation Queue';
var RV_CAPTION_TAB     = 'Generated Caption';
var RV_GS_HEADER_ROW   = 3;            // data starts at row 4
var RV_GS_FIRST_ROW    = 4;

// Generation Status columns (1-based)
var RV_GSC = { NUM:2, PROMPTS:3, IMG:4, IMG_D:5, IMG_T:6, CAP:7, CAP_D:8, CAP_T:9,
            POST:10, SCHED:11, POSTED:12, SYSREM:13, USERREM:14, POSTURL:15,
            SLIDES:16 };   // P — created on demand

// Generation Queue columns (1-based)
var RV_QC  = { NUM:1, YEAR:2, MONTH:3, FABRIC:4, PTYPE:5, VARIANT:6,
            P1:7, P5:11, CREDITS:12, FOLDER:13, IMAGE_URLS:14, CAROUSEL:15, NOTES:16 };

// Generated Caption columns (1-based)
var RV_CC  = { NUM:1, CAPTION:2, ALT1:3, ALT5:7, REMARK:8 };
var RV_CAPTION_HEADER_ROW = 1;

// Educational queue sheet (the other lane). Read for the calendar AND, since
// v2.1, for the approval queue itself. Its ids are prefixed 'ED-' everywhere on
// this page so an educational #16 is never mistaken for an AI #16.
var RV_EDU_SHEET_ID     = '1DoOtov9T1A7qqJvPy-IhJC8OzQjweM0PdpOC_jJ8hEw';
var RV_EDU_GS_TAB       = 'Generation Status';
var RV_EDU_QUEUE_TAB    = 'Generation Queue';
var RV_EDU_CAPTION_TAB  = 'Generated Caption';
var RV_EDU_FIRST_ROW    = 4;
var RV_EDU_PREFIX       = 'ED-';
// Edu Generation Status: B # · C Topic# · E render · H caption · K POST
//                        L sched date · M post date · N sys remark · O user remark
var RV_EDUC = { NUM:2, TOPIC:3, RENDER:5, CAP:8, POST:11, SCHED:12, POSTED:13,
             SYSREM:14, USERREM:15, SLIDES:16 };   // P — created on demand (v2.5)
var RV_EDU_HEADER_ROW   = 3;
var RV_EDU_SCHEDULED    = 'Scheduled';
// Edu Generation Queue: A # · D Topic# · E Type · F Series · P folder
//                       Q slide Drive ids · R permalink
var RV_EDUQ = { NUM:1, TOPIC:4, TYPE:5, SERIES:6, FOLDER:16, URLS:17, URL:18 };
// Edu Generated Caption: A # · B caption · C..I alt 1-7 · J written · K remark
var RV_EDU_CC = { NUM:1, CAPTION:2 };
// K values. Only 'Approved' publishes, so anything else parks the row.
var RV_EDU_APPROVED = 'Approved';
var RV_EDU_REJECTED = 'Rejected';
var RV_EDU_REVIEW   = 'Review';

// ── Policy ──────────────────────────────────────────────────────────────────
var RV_MAX_REROLLS       = 2;
var RV_NOTIFY_EMAIL      = 'lee.marcusmz@gmail.com';   // publish-failure emails (operational, Marcus only)

// Who gets the WEEKLY ACTION digest. This is a review worklist, so it goes to
// the same people the picker invites — keep this list identical to picker.gs's
// TEAMMATE_EMAILS. They are separate constants because the two files are
// separate Apps Script sources; if you add a teammate, add them in BOTH.
var RV_DIGEST_EMAILS     = [
  'lee.marcusmz@gmail.com',
  'holongcharles.lee@gmail.com',
];
var RV_DIGEST_DOW        = 1;      // Monday. The Weekly Action digest goes out on this day.
var RV_FLOW_HUB_FALLBACK = 'https://claude.ai/code/artifact/0c53a3c8-42fb-456f-92ab-595922714512';
var RV_COST_PER_IMAGE    = 0.24;   // mirrors config.py
var RV_IG_MIN_CAROUSEL   = 2;      // 1 kept slide -> single-image post
var RV_IG_MAX_CAROUSEL   = 10;
var RV_THUMB_WIDTH       = 900;    // px pulled from Drive for the preview
var RV_CACHE_SEC         = 21600;  // 6h — Drive thumbs are the slow part
var RV_CADENCE_DOW       = [2, 4, 6];   // Tue / Thu / Sat (JS getDay: 0 = Sun)
var RV_POST_TIME_LABEL   = '21:00 NY';
var RV_IG_HANDLE         = 'selenedreams_official';

// Row maths (see [[selene-generation-status]])
function rvGsRow_(n)    { return Number(n) + 3; }
function rvQueueRow_(n) { return Number(n) + 1; }

// ── Sheet handles ───────────────────────────────────────────────────────────

function rvSs_()        { return SpreadsheetApp.getActiveSpreadsheet(); }
function rvGsSheet_()   { return rvSs_().getSheetByName(RV_GS_TAB); }
function rvQueueSheet_(){ return rvSs_().getSheetByName(RV_QUEUE_TAB); }
function rvCapSheet_()  { return rvSs_().getSheetByName(RV_CAPTION_TAB); }

/** Column P ("Approved Slides") — create the header once, idempotently. */
function rvEnsureSlidesCol_() {
  var sh = rvGsSheet_();
  if (sh.getMaxColumns() < RV_GSC.SLIDES) {
    sh.insertColumnsAfter(sh.getMaxColumns(), RV_GSC.SLIDES - sh.getMaxColumns());
  }
  var cell = sh.getRange(RV_GS_HEADER_ROW, RV_GSC.SLIDES);
  if (String(cell.getValue()).trim() === '') cell.setValue('Approved Slides');
}

// ── Reading a row ───────────────────────────────────────────────────────────

/**
 * Drive file ids out of a queue "Image URLs" cell, in slide order.
 * The AI lane writes https://drive.google.com/file/d/<id>/view links; the
 * educational lane (render_runner_edu.py) writes https://drive.google.com/uc?id=<id>.
 * Both must resolve — v2.3 only matched /file/d/, which is why every ED post
 * showed "0 slides" with no error. Also accepts open?id=, thumbnail?id= and
 * a bare id on its own line. De-duplicated, order preserved.
 */
function rvDriveIds_(cellValue) {
  var out = [], seen = {};
  String(cellValue || '').split(/[\s,]+/).forEach(function (tok) {
    tok = tok.trim(); if (!tok) return;
    var m = tok.match(/\/file\/d\/([A-Za-z0-9_\-]{10,})/)
         || tok.match(/[?&]id=([A-Za-z0-9_\-]{10,})/)
         || (/^[A-Za-z0-9_\-]{20,}$/.test(tok) ? [null, tok] : null);
    if (m && !seen[m[1]]) { seen[m[1]] = 1; out.push(m[1]); }
  });
  return out;
}

/** A Drive image as a data: URL at RV_THUMB_WIDTH, cached 6h. */
function rvDriveThumb_(fileId) {
  var cache = CacheService.getUserCache();
  var key   = 'rvthumb_' + fileId + '_' + RV_THUMB_WIDTH;
  var hit   = cache.get(key);
  if (hit) return hit;

  var errs = [];
  // ATTEMPT 1 — DriveApp's own thumbnail (no REST API needed on the Cloud project).
  try {
    var t = DriveApp.getFileById(fileId).getThumbnail();
    if (t) {
      var d1 = 'data:' + t.getContentType() + ';base64,' + Utilities.base64Encode(t.getBytes());
      return rvCacheThumb_(cache, key, d1);
    }
    errs.push('DriveApp: no thumbnail');
  } catch (e1) {
    errs.push('DriveApp: ' + String(e1 && e1.message || e1));
  }
  // ATTEMPT 2 — Drive REST thumbnailLink (bigger, when the API is enabled).
  try {
    var token = ScriptApp.getOAuthToken();
    var meta  = UrlFetchApp.fetch(
      'https://www.googleapis.com/drive/v3/files/' + fileId + '?fields=thumbnailLink',
      { headers: { Authorization: 'Bearer ' + token }, muteHttpExceptions: true });
    if (meta.getResponseCode() !== 200) {
      errs.push('REST meta HTTP ' + meta.getResponseCode());
    } else {
      var link = JSON.parse(meta.getContentText()).thumbnailLink;
      if (!link) {
        errs.push('REST: no thumbnailLink');
      } else {
        var img = UrlFetchApp.fetch(link.replace(/=s\d+$/, '=s' + RV_THUMB_WIDTH),
          { headers: { Authorization: 'Bearer ' + token }, muteHttpExceptions: true });
        if (img.getResponseCode() !== 200) {
          errs.push('REST img HTTP ' + img.getResponseCode());
        } else {
          var bl = img.getBlob();
          return rvCacheThumb_(cache, key,
            'data:' + bl.getContentType() + ';base64,' + Utilities.base64Encode(bl.getBytes()));
        }
      }
    }
  } catch (e2) {
    errs.push('REST: ' + String(e2 && e2.message || e2));
  }
  // NO FULL-FILE FALLBACK, deliberately: the generated PNGs are ~20 MB each.
  return 'ERR:' + errs.join(' | ');
}

function rvCacheThumb_(cache, key, dataUrl) {
  if (dataUrl.length < 95000) {          // CacheService caps a value at 100KB
    try { cache.put(key, dataUrl, RV_CACHE_SEC); } catch (e) {}
  }
  return dataUrl;
}

/** The caption row for post #n, or null. */
function rvCaptionFor_(n) {
  var sh = rvCapSheet_();
  if (!sh) return null;
  var col = sh.getRange(1, RV_CC.NUM, Math.max(sh.getLastRow(), 1), 1).getValues();
  for (var i = RV_CAPTION_HEADER_ROW; i < col.length; i++) {
    if (String(col[i][0]).trim() === String(n)) {
      var row  = i + 1;
      var vals = sh.getRange(row, 1, 1, RV_CC.REMARK).getValues()[0];
      return {
        row: row,
        caption: String(vals[RV_CC.CAPTION - 1] || ''),
        alts: vals.slice(RV_CC.ALT1 - 1, RV_CC.ALT5).map(function (v) { return String(v || ''); }),
        remark: String(vals[RV_CC.REMARK - 1] || '')
      };
    }
  }
  return null;
}

/** Caption QA remark cell -> list of notes. The remark is free text joined
 * with " | " or newlines by caption_runner; split on either. */
function rvQaNotes_(remark) {
  return String(remark || '').split(/\s*\|\s*|\n+/).map(function (s) { return s.trim(); })
    .filter(function (s) { return s; });
}

/** Per-slide reroll counts from the system remark ("REROLL slide 3 (attempt 1 of 2)"). */
function rvRerollCounts_(sysrem) {
  var out = {}, re = /REROLL slide (\d+)\b/g, m;
  while ((m = re.exec(String(sysrem || ''))) !== null) out[m[1]] = (out[m[1]] || 0) + 1;
  return out;
}

/** Last system remark entry (they are joined with " | "). */
function rvLastRemark_(sysrem) {
  var s = String(sysrem || '');
  return s ? s.split(' | ').pop() : '';
}

/** Plain-language reason for a publish failure, from the raw remark. */
function rvFailureReason_(remark) {
  var r = String(remark || '');
  if (/too large|file size|8 ?MB/i.test(r))   return 'Instagram rejected the image — file too large.';
  if (/aspect|ratio|dimension/i.test(r))       return 'Instagram rejected the image — aspect ratio out of range.';
  if (/token|OAuth|code 190|expired session/i.test(r)) return 'Instagram access token expired — re-authorise on the Mac.';
  if (/rate|throttl|code 4\b|too many/i.test(r)) return 'Instagram rate limit hit — retry later.';
  if (/ngrok|tunnel|ECONN|timed? ?out|unreachable|502|503/i.test(r)) return 'The Mac was unreachable at publish time.';
  if (/caption|hashtag/i.test(r))              return 'Instagram rejected the caption.';
  return 'Publish failed — see the remark below.';
}

/** All Generation Status data rows as objects (one read). */
function rvGsRows_() {
  var gs = rvGsSheet_();
  var last = gs.getLastRow();
  if (last < RV_GS_FIRST_ROW) return [];
  var width = Math.max(RV_GSC.SLIDES, gs.getLastColumn());
  var rows = gs.getRange(RV_GS_FIRST_ROW, 1, last - RV_GS_FIRST_ROW + 1, width).getValues();
  var out = [];
  for (var i = 0; i < rows.length; i++) {
    var r = rows[i];
    var n = String(r[RV_GSC.NUM - 1]).trim();
    if (!n) continue;
    out.push({
      n: n, gsRow: RV_GS_FIRST_ROW + i,
      img:  String(r[RV_GSC.IMG - 1] || '').trim(),
      cap:  String(r[RV_GSC.CAP - 1] || '').trim(),
      post: String(r[RV_GSC.POST - 1] || '').trim(),
      sched: rvDateStr_(r[RV_GSC.SCHED - 1]),
      posted: rvDateStr_(r[RV_GSC.POSTED - 1]),
      sysrem: String(r[RV_GSC.SYSREM - 1] || ''),
      userrem: String(r[RV_GSC.USERREM - 1] || ''),
      url: String(r[RV_GSC.POSTURL - 1] || '').trim(),
      slides: String(r[RV_GSC.SLIDES - 1] || '').trim()
    });
  }
  return out;
}

/** Queue rows indexed by #. */
function rvQueueMap_() {
  var q = rvQueueSheet_();
  var vals = q.getRange(1, 1, Math.max(q.getLastRow(), 1), RV_QC.NOTES).getValues();
  var map = {};
  for (var i = 1; i < vals.length; i++) {
    var n = String(vals[i][RV_QC.NUM - 1]).trim();
    if (n) map[n] = vals[i];
  }
  return map;
}

function rvTitle_(qr, n) {
  if (!qr) return 'Post #' + n;
  return [qr[RV_QC.FABRIC - 1], qr[RV_QC.PTYPE - 1], qr[RV_QC.VARIANT - 1]]
    .map(function (v) { return String(v || '').trim(); }).filter(String).join(' · ') || ('Post #' + n);
}

/** A sheet cell (Date or string) -> 'yyyy-MM-dd' or ''. */
function rvDateStr_(v) {
  if (!v) return '';
  if (Object.prototype.toString.call(v) === '[object Date]') {
    return Utilities.formatDate(v, rvSs_().getSpreadsheetTimeZone(), 'yyyy-MM-dd');
  }
  var s = String(v).trim();
  var m = s.match(/^(\d{4})-(\d{2})-(\d{2})/);
  return m ? m[1] + '-' + m[2] + '-' + m[3] : s;
}

/**
 * Every post waiting on a decision: images Done, caption Done, J untouched.
 * No images — the page fetches thumbnails itself (reviewThumb) for the post
 * that is open.
 */
function rvPending_() {
  var rows = rvGsRows_(), qmap = rvQueueMap_(), out = [];
  rows.forEach(function (r) {
    if (r.img !== 'Done' || r.cap !== 'Done') return;
    if (r.post && r.post !== 'Not Started') return;
    var qr = qmap[r.n];
    var capO = rvCaptionFor_(r.n);
    out.push({
      n: r.n, lane: 'ai', num: r.n, title: rvTitle_(qr, r.n),
      fabric: qr ? String(qr[RV_QC.FABRIC - 1] || '') : '',
      folder: qr ? String(qr[RV_QC.FOLDER - 1] || '') : '',
      slideIds: rvDriveIds_(qr ? qr[RV_QC.IMAGE_URLS - 1] : ''),
      rerolls: rvRerollCounts_(r.sysrem),
      caption: capO ? capO.caption : '',
      qaNotes: capO ? rvQaNotes_(capO.remark) : [],
      hasCaption: !!capO
    });
  });
  return out;
}

/** Rows mid-reroll: last remark is a REROLL and D is Ready/Processing. */
function rvRegenerating_() {
  var rows = rvGsRows_(), qmap = rvQueueMap_(), out = [];
  rows.forEach(function (r) {
    if (r.post && r.post !== 'Not Started') return;
    if (r.img !== 'Ready' && r.img !== 'Processing') return;
    var m = rvLastRemark_(r.sysrem).match(/REROLL slide (\d+) \(attempt (\d+) of (\d+)\)/);
    if (!m) return;
    out.push({ n: r.n, title: rvTitle_(qmap[r.n], r.n), slide: Number(m[1]),
               attempt: Number(m[2]), max: Number(m[3]), img: r.img,
               since: (rvLastRemark_(r.sysrem).match(/^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2})\]/) || [])[1] || '' });
  });
  return out;
}

/** Failed publishes (J=Hold) — the NEEDS ATTENTION group, with slides for the read-only view. */
function rvAttention_() {
  var rows = rvGsRows_(), qmap = rvQueueMap_(), out = [];
  rows.forEach(function (r) {
    if (r.post !== 'Hold') return;
    var qr = qmap[r.n];
    var capO = rvCaptionFor_(r.n);
    var last = rvLastRemark_(r.sysrem);
    out.push({
      n: r.n, title: rvTitle_(qr, r.n), when: r.sched, slides: r.slides || 'all',
      slideIds: rvDriveIds_(qr ? qr[RV_QC.IMAGE_URLS - 1] : ''),
      caption: capO ? capO.caption : '',
      reason: rvFailureReason_(last), remark: last
    });
  });
  return out;
}

/**
 * Rows the runner owns right now: J=Scheduled and J=Hold. Kept for the
 * notification tick (reviewNotifyTick) which predates the calendar.
 */
function rvScheduled_() {
  var rows = rvGsRows_(), qmap = rvQueueMap_(), out = [];
  rows.forEach(function (r) {
    if (r.post !== 'Scheduled' && r.post !== 'Hold') return;
    out.push({ n: r.n, status: r.post, when: r.sched, slides: r.slides || 'all',
               title: rvTitle_(qmap[r.n], r.n), lastRemark: rvLastRemark_(r.sysrem) });
  });
  return out;
}

/**
 * v2.5 — the SCHEDULED sidebar group. AI rows J=Scheduled plus educational
 * rows K=Approved (no date yet — that lane books its Thursday on its next
 * tick) or K=Scheduled. Carries slide ids + approved order + caption so the
 * page can show the post read-only. Sorted by date, undated last.
 */
function rvScheduledFull_() {
  var out = [];
  var rows = rvGsRows_(), qmap = rvQueueMap_();
  rows.forEach(function (r) {
    if (r.post !== 'Scheduled') return;
    var qr = qmap[r.n];
    var capO = rvCaptionFor_(r.n);
    out.push({
      n: r.n, lane: 'ai', num: r.n, title: rvTitle_(qr, r.n), when: r.sched,
      status: 'Scheduled', slides: r.slides || '',
      slideIds: rvDriveIds_(qr ? qr[RV_QC.IMAGE_URLS - 1] : ''),
      caption: capO ? capO.caption : ''
    });
  });
  var ss = rvEduSs_();
  if (ss) {
    try {
      var gs = ss.getSheetByName(RV_EDU_GS_TAB), q = ss.getSheetByName(RV_EDU_QUEUE_TAB);
      var last = gs ? gs.getLastRow() : 0;
      if (gs && q && last >= RV_EDU_FIRST_ROW) {
        var width = Math.max(RV_EDUC.SLIDES, gs.getLastColumn());
        var ers = gs.getRange(RV_EDU_FIRST_ROW, 1, last - RV_EDU_FIRST_ROW + 1, width).getValues();
        var qv = q.getRange(1, 1, Math.max(q.getLastRow(), 1), RV_EDUQ.URL).getValues();
        var eq = {};
        for (var i = 1; i < qv.length; i++) {
          var qn = String(qv[i][RV_EDUQ.NUM - 1]).trim();
          if (qn) eq[qn] = qv[i];
        }
        ers.forEach(function (r) {
          var num = String(r[RV_EDUC.NUM - 1]).trim();
          if (!num) return;
          var post = String(r[RV_EDUC.POST - 1] || '').trim();
          if (post !== RV_EDU_APPROVED && post !== RV_EDU_SCHEDULED) return;
          var qr = eq[num];
          var title = qr
            ? ['Educational', qr[RV_EDUQ.TYPE - 1], qr[RV_EDUQ.SERIES - 1]]
                .map(function (v) { return String(v || '').trim(); }).filter(String).join(' · ')
            : 'Educational #' + num;
          out.push({
            n: RV_EDU_PREFIX + num, lane: 'edu', num: num, title: title,
            when: rvDateStr_(r[RV_EDUC.SCHED - 1]), status: post,
            slides: String(r[RV_EDUC.SLIDES - 1] || '').trim(),
            slideIds: rvDriveIds_(qr ? qr[RV_EDUQ.URLS - 1] : ''),
            caption: rvEduCaptionFor_(ss, num)
          });
        });
      }
    } catch (e) {
      Logger.log('scheduled: edu sheet unavailable — ' + (e && e.message || e));
    }
  }
  out.sort(function (a, b) {
    if (!a.when && !b.when) return 0;
    if (!a.when) return 1;
    if (!b.when) return -1;
    return a.when < b.when ? -1 : (a.when > b.when ? 1 : 0);
  });
  return out;
}

// ── Calendar ────────────────────────────────────────────────────────────────
// One flat list of dated items across lanes. Each: {type, n, title, date,
// time, status: 'sched'|'pub'|'fail', url, lane}. The page groups by date.

function rvCalendarAI_() {
  var rows = rvGsRows_(), qmap = rvQueueMap_(), out = [];
  rows.forEach(function (r) {
    var it = null;
    if (r.post === 'Scheduled' && r.sched) it = { status: 'sched', date: r.sched };
    else if (r.post === 'Hold' && r.sched)  it = { status: 'fail',  date: r.sched };
    else if (r.post === 'Done' && (r.posted || r.sched)) it = { status: 'pub', date: r.posted || r.sched };
    if (!it) return;
    var qr = qmap[r.n];
    out.push({ type: 'AI', lane: 'ai', n: r.n, title: rvTitle_(qr, r.n),
               date: it.date, time: RV_POST_TIME_LABEL, status: it.status,
               url: r.url, slides: r.slides || 'all',
               slideIds: rvDriveIds_(qr ? qr[RV_QC.IMAGE_URLS - 1] : '') });
  });
  return out;
}

/** Flow Hub link for the Weekly Action emails. Script Property wins, so the
 * destination changes without a redeploy. */
function rvFlowHub_() {
  return PropertiesService.getScriptProperties().getProperty('FLOW_HUB_URL') ||
         RV_FLOW_HUB_FALLBACK;
}

/** 'MM/DD/YYYY' in the spreadsheet's timezone. */
function rvTodayUS_() {
  return Utilities.formatDate(new Date(), rvSs_().getSpreadsheetTimeZone(), 'MM/dd/yyyy');
}

/** True for an id this page minted for the educational lane ('ED-16'). */
function rvIsEdu_(n) { return String(n).indexOf(RV_EDU_PREFIX) === 0; }

/** 'ED-16' -> '16'. */
function rvEduNum_(n) { return String(n).slice(RV_EDU_PREFIX.length); }

/** The educational spreadsheet, or null when it cannot be opened. Every caller
 * degrades to the AI lane alone rather than failing the page. */
function rvEduSs_() {
  try { return SpreadsheetApp.openById(RV_EDU_SHEET_ID); }
  catch (e) {
    Logger.log('edu sheet unavailable — ' + (e && e.message || e));
    return null;
  }
}

/** Caption for an educational post. That tab is A # · B caption, data row 2. */
function rvEduCaptionFor_(ss, num) {
  var sh = ss.getSheetByName(RV_EDU_CAPTION_TAB);
  if (!sh) return '';
  var last = sh.getLastRow();
  if (last < 2) return '';
  var vals = sh.getRange(2, 1, last - 1, RV_EDU_CC.CAPTION).getValues();
  for (var i = 0; i < vals.length; i++) {
    if (String(vals[i][RV_EDU_CC.NUM - 1]).trim() === String(num)) {
      return String(vals[i][RV_EDU_CC.CAPTION - 1] || '');
    }
  }
  return '';
}

/**
 * Educational carousels waiting on a decision: render Done, caption Done, and
 * K either blank or 'Review'. Shaped like rvPending_ so the page renders both
 * lanes through one path — but flagged lane:'edu', which switches off the slide
 * menu (text is baked into these renders) and the date picker (that lane books
 * its own Thursday).
 */
function rvEduPending_() {
  var out = [];
  var ss = rvEduSs_();
  if (!ss) return out;
  try {
    var gs = ss.getSheetByName(RV_EDU_GS_TAB), q = ss.getSheetByName(RV_EDU_QUEUE_TAB);
    if (!gs || !q) return out;
    var last = gs.getLastRow();
    if (last < RV_EDU_FIRST_ROW) return out;
    var rows = gs.getRange(RV_EDU_FIRST_ROW, 1, last - RV_EDU_FIRST_ROW + 1,
                           RV_EDUC.USERREM).getValues();
    var qv = q.getRange(1, 1, Math.max(q.getLastRow(), 1), RV_EDUQ.URL).getValues();
    var qmap = {};
    for (var i = 1; i < qv.length; i++) {
      var qn = String(qv[i][RV_EDUQ.NUM - 1]).trim();
      if (qn) qmap[qn] = qv[i];
    }
    rows.forEach(function (r) {
      var num = String(r[RV_EDUC.NUM - 1]).trim();
      if (!num) return;
      if (String(r[RV_EDUC.RENDER - 1] || '').trim() !== 'Done') return;
      if (String(r[RV_EDUC.CAP - 1] || '').trim() !== 'Done') return;
      var post = String(r[RV_EDUC.POST - 1] || '').trim();
      if (post && post !== RV_EDU_REVIEW) return;       // already decided
      var qr = qmap[num];
      var title = qr
        ? ['Educational', qr[RV_EDUQ.TYPE - 1], qr[RV_EDUQ.SERIES - 1]]
            .map(function (v) { return String(v || '').trim(); }).filter(String).join(' · ')
        : 'Educational #' + num;
      out.push({
        n: RV_EDU_PREFIX + num, lane: 'edu', num: num, title: title,
        fabric: '', folder: qr ? String(qr[RV_EDUQ.FOLDER - 1] || '') : '',
        slideIds: rvDriveIds_(qr ? qr[RV_EDUQ.URLS - 1] : ''),
        rerolls: {},
        caption: rvEduCaptionFor_(ss, num),
        qaNotes: [],
        hasCaption: true
      });
    });
  } catch (e) {
    Logger.log('edu pending unavailable — ' + (e && e.message || e));
  }
  return out;
}

function rvCalendarEdu_() {
  var out = [];
  try {
    var ss = SpreadsheetApp.openById(RV_EDU_SHEET_ID);
    var gs = ss.getSheetByName(RV_EDU_GS_TAB), q = ss.getSheetByName(RV_EDU_QUEUE_TAB);
    if (!gs || !q) return out;
    var last = gs.getLastRow();
    if (last < RV_EDU_FIRST_ROW) return out;
    var rows = gs.getRange(RV_EDU_FIRST_ROW, 1, last - RV_EDU_FIRST_ROW + 1,
                           Math.max(RV_EDUC.SLIDES, gs.getLastColumn())).getValues();
    var qv = q.getRange(1, 1, Math.max(q.getLastRow(), 1), RV_EDUQ.URL).getValues();
    var qmap = {};
    for (var i = 1; i < qv.length; i++) {
      var qn = String(qv[i][RV_EDUQ.NUM - 1]).trim();
      if (qn) qmap[qn] = qv[i];
    }
    var tz = rvSs_().getSpreadsheetTimeZone();
    var ds = function (v) {
      if (!v) return '';
      if (Object.prototype.toString.call(v) === '[object Date]') return Utilities.formatDate(v, tz, 'yyyy-MM-dd');
      var m = String(v).match(/^(\d{4})-(\d{2})-(\d{2})/); return m ? m[0] : '';
    };
    rows.forEach(function (r) {
      var n = String(r[RV_EDUC.NUM - 1]).trim();
      if (!n) return;
      var post = String(r[RV_EDUC.POST - 1] || '').trim();
      var sched = ds(r[RV_EDUC.SCHED - 1]), posted = ds(r[RV_EDUC.POSTED - 1]);
      var it = null;
      if (post === 'Scheduled' && sched) it = { status: 'sched', date: sched };
      else if (post === 'Hold' && sched)  it = { status: 'fail',  date: sched };
      else if (post === 'Posted' && (posted || sched)) it = { status: 'pub', date: posted || sched };
      if (!it) return;
      var qr = qmap[n];
      var title = qr ? ['Edu', qr[RV_EDUQ.TYPE - 1], qr[RV_EDUQ.SERIES - 1]]
        .map(function (v) { return String(v || '').trim(); }).filter(String).join(' · ') : 'Edu #' + n;
      out.push({ type: 'ED', lane: 'edu', n: n, title: title, date: it.date,
                 time: RV_POST_TIME_LABEL, status: it.status,
                 url: qr ? String(qr[RV_EDUQ.URL - 1] || '') : '',
                 slides: String(r[RV_EDUC.SLIDES - 1] || '').trim(),
                 slideIds: rvDriveIds_(qr ? qr[RV_EDUQ.URLS - 1] : '') });
    });
  } catch (e) {
    Logger.log('calendar: edu sheet unavailable — ' + (e && e.message || e));
  }
  return out;
}

/**
 * Reels / trial reels live on the Mac (no sheet, by design). The Mac may
 * expose GET /calendar returning [{type:'RE'|'TR', title, date, time, status,
 * url}]. Not built as of 2026-09-09 — this degrades silently.
 */
function rvCalendarExternal_() {
  try {
    // Off unless Script Property RV_CALENDAR_EXTERNAL = '1': a sleeping Mac
    // would otherwise hold every page load until UrlFetch gives up.
    if (PropertiesService.getScriptProperties().getProperty('RV_CALENDAR_EXTERNAL') !== '1') return [];
    if (typeof WEBHOOK_URL !== 'string' || WEBHOOK_URL.indexOf('http') !== 0) return [];
    var base = WEBHOOK_URL.replace(/\/webhook\/?$/, '');
    var resp = UrlFetchApp.fetch(base + '/calendar', {
      method: 'get', muteHttpExceptions: true,
      headers: { 'ngrok-skip-browser-warning': 'true' }
    });
    if (resp.getResponseCode() !== 200) return [];
    var arr = JSON.parse(resp.getContentText());
    if (!Array.isArray(arr)) return [];
    return arr.filter(function (it) { return it && it.date; }).map(function (it) {
      return { type: it.type === 'TR' ? 'TR' : 'RE', lane: 'reel', n: String(it.n || ''),
               title: String(it.title || 'Reel'), date: String(it.date).slice(0, 10),
               time: String(it.time || ''), status: it.status === 'pub' ? 'pub' : (it.status === 'fail' ? 'fail' : 'sched'),
               url: String(it.url || ''), slides: '', slideIds: [] };
    });
  } catch (e) { return []; }
}

function rvCalendar_() {
  return rvCalendarAI_().concat(rvCalendarEdu_()).concat(rvCalendarExternal_());
}

/** Next open cadence day (Tue/Thu/Sat) strictly after today, 'yyyy-MM-dd'. */
function rvNextCadence_() {
  var tz = rvSs_().getSpreadsheetTimeZone();
  var d = new Date();
  for (var i = 1; i <= 7; i++) {
    var c = new Date(d.getTime() + i * 86400000);
    var dow = Number(Utilities.formatDate(c, tz, 'u')) % 7;   // 'u' = 1..7 Mon..Sun
    if (RV_CADENCE_DOW.indexOf(dow) !== -1) return Utilities.formatDate(c, tz, 'yyyy-MM-dd');
  }
  return Utilities.formatDate(d, tz, 'yyyy-MM-dd');
}

/** Everything the page needs. Called at render and by the client to refresh. */
function reviewState() {
  var tz = rvSs_().getSpreadsheetTimeZone();
  return {
    build: REVIEW_BUILD,
    today: Utilities.formatDate(new Date(), tz, 'yyyy-MM-dd'),
    defaultDate: rvNextCadence_(),
    handle: RV_IG_HANDLE,
    cost: RV_COST_PER_IMAGE, maxRerolls: RV_MAX_REROLLS,
    pending: rvPending_().concat(rvEduPending_()),
    regen: rvRegenerating_(),
    attention: rvAttention_(),
    scheduled: rvScheduledFull_(),
    calendar: rvCalendar_()
  };
}

// ── Actions called from the page ────────────────────────────────────────────
// All take the post number as a string and return {ok, ...}. A LockService
// lock guards every write: two devices on the same link would otherwise
// interleave and half-write a decision.

function rvWithLock_(fn) {
  var lock = LockService.getScriptLock();
  try { lock.waitLock(20000); } catch (e) {
    return { ok: false, error: 'Someone else is saving right now. Try again in a moment.' };
  }
  try { return fn(); }
  catch (err) { return { ok: false, error: String(err && err.message || err) }; }
  finally { try { lock.releaseLock(); } catch (e) {} }
}

function rvLocate_(n) {
  var gs   = rvGsSheet_();
  var row  = rvGsRow_(n);
  var got  = String(gs.getRange(row, RV_GSC.NUM).getValue()).trim();
  if (got !== String(n)) {
    // Row maths assumes nothing was inserted. Scan rather than write to the
    // wrong post — the one mistake that must never happen.
    var last = gs.getLastRow();
    var col  = gs.getRange(RV_GS_FIRST_ROW, RV_GSC.NUM, last - RV_GS_FIRST_ROW + 1, 1).getValues();
    for (var i = 0; i < col.length; i++) {
      if (String(col[i][0]).trim() === String(n)) return { sheet: gs, row: RV_GS_FIRST_ROW + i };
    }
    throw new Error('Post #' + n + ' is not on the Generation Status tab.');
  }
  return { sheet: gs, row: row };
}

function rvNote_(sheet, row, msg) {
  var cell = sheet.getRange(row, RV_GSC.SYSREM);
  var prev = String(cell.getValue() || '');
  var stamp = Utilities.formatDate(new Date(), rvSs_().getSpreadsheetTimeZone(), 'yyyy-MM-dd HH:mm');
  cell.setValue((prev ? prev + ' | ' : '') + '[' + stamp + '] REVIEW: ' + msg);
}

function rvValidDate_(s) {
  return /^\d{4}-\d{2}-\d{2}$/.test(String(s || '').trim());
}

/**
 * APPROVE. keptSlides is 1-based positions into the ORIGINAL slide list, in
 * the DISPLAYED order (e.g. [3,1,2]). publish_runner posts P verbatim, so the
 * first entry is the cover.
 */
/** Find an educational row by post number. Throws with a readable message. */
function rvEduLocate_(num) {
  var ss = rvEduSs_();
  if (!ss) throw new Error('The educational sheet could not be opened.');
  var gs = ss.getSheetByName(RV_EDU_GS_TAB);
  if (!gs) throw new Error('Educational Generation Status tab is missing.');
  var last = gs.getLastRow();
  var col = gs.getRange(RV_EDU_FIRST_ROW, RV_EDUC.NUM,
                        Math.max(last - RV_EDU_FIRST_ROW + 1, 1), 1).getValues();
  for (var i = 0; i < col.length; i++) {
    if (String(col[i][0]).trim() === String(num)) {
      return { ss: ss, sheet: gs, row: RV_EDU_FIRST_ROW + i };
    }
  }
  throw new Error('Educational post #' + num + ' is not on its Generation Status tab.');
}

/** Append-only system remark on the educational row, that lane's format. */
function rvEduNote_(t, msg) {
  var tz = rvSs_().getSpreadsheetTimeZone();
  var stamp = Utilities.formatDate(new Date(), tz, 'yyyy-MM-dd HH:mm');
  var cell = t.sheet.getRange(t.row, RV_EDUC.SYSREM);
  var prev = String(cell.getValue() || '').trim();
  cell.setValue((prev ? prev + ' | ' : '') + '[' + stamp + '] REVIEW: ' + msg);
}

/** Rewrite the caption on the educational Generated Caption tab, if changed. */
function rvEduSetCaption_(ss, num, caption) {
  var sh = ss.getSheetByName(RV_EDU_CAPTION_TAB);
  if (!sh) return false;
  var last = sh.getLastRow();
  if (last < 2) return false;
  var vals = sh.getRange(2, RV_EDU_CC.NUM, last - 1, 1).getValues();
  for (var i = 0; i < vals.length; i++) {
    if (String(vals[i][0]).trim() === String(num)) {
      sh.getRange(i + 2, RV_EDU_CC.CAPTION).setValue(caption);
      return true;
    }
  }
  return false;
}

/**
 * APPROVE an educational carousel. That lane books its own next Thursday, so
 * there is no date to set here — K='Approved' is the whole decision.
 */
function rvEduApprove_(num, finalCaption, keptSlides) {
  var t = rvEduLocate_(num);
  var cur = String(t.sheet.getRange(t.row, RV_EDUC.POST).getValue() || '').trim();
  if (cur && cur !== RV_EDU_REVIEW) {
    return { ok: false, error: 'Educational #' + num + ' is already ' + cur + '.' };
  }
  // v2.5 — kept slides in displayed order. Blank = every slide (publish_edu's
  // default), so an old client that sends nothing still behaves as before.
  var kept = (keptSlides || []).map(Number).filter(function (v) { return v > 0; });
  if (kept.length && kept.length < RV_IG_MIN_CAROUSEL) {
    return { ok: false, error: 'An educational post needs at least ' + RV_IG_MIN_CAROUSEL + ' slides.' };
  }
  if (kept.length > RV_IG_MAX_CAROUSEL) {
    return { ok: false, error: 'Instagram allows at most ' + RV_IG_MAX_CAROUSEL + ' slides.' };
  }
  if (typeof finalCaption === 'string' && finalCaption.trim() &&
      finalCaption !== rvEduCaptionFor_(t.ss, num)) {
    if (rvEduSetCaption_(t.ss, num, finalCaption)) rvEduNote_(t, 'caption edited at review');
  }
  rvEduEnsureSlidesCol_(t.sheet);
  t.sheet.getRange(t.row, RV_EDUC.SLIDES).setValue(kept.join(','));
  t.sheet.getRange(t.row, RV_EDUC.POST).setValue(RV_EDU_APPROVED);
  rvEduNote_(t, 'approved at review — ' + (kept.length ? kept.length + ' slide(s) in order ' + kept.join(',') : 'all slides') +
                ', takes the next Thursday ' + RV_POST_TIME_LABEL + ' slot');
  return { ok: true, lane: 'edu', status: 'Approved', when: '', kind: 'carousel', kept: kept };
}

/** Column P ("Approved Slides") on the EDU Generation Status tab — idempotent. */
function rvEduEnsureSlidesCol_(sh) {
  if (sh.getMaxColumns() < RV_EDUC.SLIDES) {
    sh.insertColumnsAfter(sh.getMaxColumns(), RV_EDUC.SLIDES - sh.getMaxColumns());
  }
  var cell = sh.getRange(RV_EDU_HEADER_ROW, RV_EDUC.SLIDES);
  if (String(cell.getValue()).trim() === '') cell.setValue('Approved Slides');
}

/**
 * v2.5 — UNAPPROVE an educational carousel: K back to Review, L cleared, P
 * cleared. publish_edu re-reads K right before it posts, so this works until
 * the Thursday slot actually fires.
 */
function rvEduCancel_(num) {
  var t = rvEduLocate_(num);
  var cur = String(t.sheet.getRange(t.row, RV_EDUC.POST).getValue() || '').trim();
  if (cur !== RV_EDU_APPROVED && cur !== RV_EDU_SCHEDULED) {
    return { ok: false, error: 'Educational #' + num + ' is ' + (cur || 'not approved') + ' — nothing to cancel.' };
  }
  t.sheet.getRange(t.row, RV_EDUC.POST).setValue(RV_EDU_REVIEW);
  t.sheet.getRange(t.row, RV_EDUC.SCHED).setValue('');
  if (t.sheet.getMaxColumns() >= RV_EDUC.SLIDES) t.sheet.getRange(t.row, RV_EDUC.SLIDES).setValue('');
  rvEduNote_(t, 'unapproved from the review page (was ' + cur + ') — back to Review');
  return { ok: true, lane: 'edu' };
}

/** REJECT an educational carousel. Only 'Approved' publishes, so this parks it. */
function rvEduReject_(num, reason) {
  var why = String(reason || '').trim();
  if (!why) return { ok: false, error: 'A reason is required — one line is enough.' };
  var t = rvEduLocate_(num);
  t.sheet.getRange(t.row, RV_EDUC.POST).setValue(RV_EDU_REJECTED);
  rvEduNote_(t, 'rejected at review — ' + why);
  return { ok: true, lane: 'edu', status: 'Rejected' };
}

/**
 * REROLL one slide of an educational carousel. No webhook: the instruction goes
 * into col O in that lane's grammar and its server picks it up on the next tick
 * (within ~16 minutes). A remark already consumed is prefixed '[done …]', so
 * that value is replaced rather than appended to — otherwise the whole cell
 * stays ignored.
 */
function rvEduReroll_(num, slideIndex, comment) {
  var idx = Number(slideIndex);
  if (!(idx > 0)) return { ok: false, error: 'Which slide?' };
  var why = String(comment || '').trim().replace(/[|\n]+/g, ' ');
  if (!why) return { ok: false, error: 'Say what you want different — that comment is the instruction.' };
  var t = rvEduLocate_(num);
  var cell = t.sheet.getRange(t.row, RV_EDUC.USERREM);
  var prev = String(cell.getValue() || '').trim();
  var line = idx + ' reroll: ' + why;
  cell.setValue((!prev || prev.indexOf('[done') === 0) ? line : prev + ' | ' + line);
  t.sheet.getRange(t.row, RV_EDUC.POST).setValue(RV_EDU_REVIEW);
  rvEduNote_(t, 'reroll requested at review — slide ' + idx + ': ' + why);
  return { ok: true, lane: 'edu', status: 'Rerolling', cost: RV_COST_PER_IMAGE,
           note: 'queued — that lane regenerates within ~16 minutes' };
}

function reviewApprove(n, keptSlides, finalCaption, scheduledDate) {
  if (rvIsEdu_(n)) {
    return rvWithLock_(function () { return rvEduApprove_(rvEduNum_(n), finalCaption, keptSlides); });
  }
  return rvWithLock_(function () {
    rvEnsureSlidesCol_();
    var kept = (keptSlides || []).map(Number).filter(function (v) { return v > 0; });
    if (!kept.length) return { ok: false, error: 'Every slide is dropped — use Reject instead.' };
    if (kept.length > RV_IG_MAX_CAROUSEL) {
      return { ok: false, error: 'Instagram allows at most ' + RV_IG_MAX_CAROUSEL + ' slides.' };
    }
    var t = rvLocate_(n);
    var cur = String(t.sheet.getRange(t.row, RV_GSC.POST).getValue() || '').trim();
    if (cur && cur !== 'Not Started') {
      return { ok: false, error: 'Post #' + n + ' is already ' + cur + '.' };
    }
    var when = String(scheduledDate || '').trim();
    if (!rvValidDate_(when)) when = rvNextCadence_();

    t.sheet.getRange(t.row, RV_GSC.POST).setValue('Scheduled');
    t.sheet.getRange(t.row, RV_GSC.SCHED).setValue(when);
    t.sheet.getRange(t.row, RV_GSC.SLIDES).setValue(kept.join(','));

    var capO = rvCaptionFor_(n);
    if (capO && typeof finalCaption === 'string' && finalCaption !== capO.caption) {
      rvCapSheet_().getRange(capO.row, RV_CC.CAPTION).setValue(finalCaption);
      rvNote_(t.sheet, t.row, 'caption edited at review');
    }
    var kind = kept.length >= RV_IG_MIN_CAROUSEL ? 'carousel' : 'single image';
    rvNote_(t.sheet, t.row, 'approved — ' + kept.length + ' slide(s) (' + kind + '), scheduled ' + when);
    return { ok: true, status: 'Scheduled', kept: kept, when: when, kind: kind };
  });
}

/** REJECT. The reason is the payload — it is what teaches the rubric. */
function reviewReject(n, reason) {
  if (rvIsEdu_(n)) {
    return rvWithLock_(function () { return rvEduReject_(rvEduNum_(n), reason); });
  }
  return rvWithLock_(function () {
    var t = rvLocate_(n);
    var why = String(reason || '').trim();
    if (!why) return { ok: false, error: 'A reason is required — one line is enough.' };
    t.sheet.getRange(t.row, RV_GSC.POST).setValue('Rejected');
    var cell = t.sheet.getRange(t.row, RV_GSC.USERREM);
    var prev = String(cell.getValue() || '');
    cell.setValue((prev ? prev + ' | ' : '') + 'Rejected at review: ' + why);
    rvNote_(t.sheet, t.row, 'rejected — ' + why);
    return { ok: true, status: 'Rejected' };
  });
}

/**
 * REROLL one slide. Flips the row back to image generation and records which
 * slide to redo, so generate.py regenerates that prompt alone.
 */
function reviewReroll(n, slideIndex, comment) {
  if (rvIsEdu_(n)) {
    return rvWithLock_(function () { return rvEduReroll_(rvEduNum_(n), slideIndex, comment); });
  }
  return rvWithLock_(function () {
    var t = rvLocate_(n);
    var idx = Number(slideIndex);
    if (!(idx > 0)) return { ok: false, error: 'Which slide?' };
    var sysrem = String(t.sheet.getRange(t.row, RV_GSC.SYSREM).getValue() || '');
    var done = rvRerollCounts_(sysrem)[String(idx)] || 0;
    if (done >= RV_MAX_REROLLS) {
      return { ok: false, error: 'Slide ' + idx + ' has already been rerolled ' + done + ' times. Drop it instead.' };
    }
    var img = String(t.sheet.getRange(t.row, RV_GSC.IMG).getValue() || '').trim();
    if (img !== 'Done') {
      return { ok: false, error: 'Post #' + n + ' images are ' + (img || 'blank') + ', not Done — nothing to reroll yet.' };
    }
    rvNote_(t.sheet, t.row, 'REROLL slide ' + idx + ' (attempt ' + (done + 1) + ' of ' + RV_MAX_REROLLS + ')');
    t.sheet.getRange(t.row, RV_GSC.IMG).setValue('Ready');
    // v2.5 — an installable on-edit trigger does NOT fire for a script's own
    // setValue(), so this page must send the webhook itself (Code.gs's
    // sendWebhook, same project). Flush first: generate.py re-reads D and
    // skips the row unless it already says Ready.
    SpreadsheetApp.flush();
    var sent = 'sendWebhook missing — Code.gs not loaded?';
    try {
      if (typeof sendWebhook === 'function') sent = sendWebhook(rvQueueRow_(n));
    } catch (e) { sent = String(e && e.message || e); }
    if (sent !== 'ok') {
      t.sheet.getRange(t.row, RV_GSC.IMG).setValue('Done');
      rvNote_(t.sheet, t.row, 'reroll NOT sent — ' + sent + ' — images left as they were');
      return { ok: false, error: 'The Mac did not take the reroll (' + sent + '). Nothing changed — is Start Selene AI running?' };
    }
    return { ok: true, status: 'Rerolling', cost: RV_COST_PER_IMAGE, attempt: done + 1, max: RV_MAX_REROLLS };
  });
}

/**
 * v2.5 — WITHDRAW a reroll that never started (D still Ready, last remark a
 * REROLL). Puts D back to Done so the row returns to WAITING ON YOU with the
 * images it already has. Refuses once the Mac has picked it up (Processing).
 */
function reviewUnreroll(n) {
  if (rvIsEdu_(n)) return { ok: false, error: 'Educational rerolls are withdrawn on their sheet (col O).' };
  return rvWithLock_(function () {
    var t = rvLocate_(n);
    var img = String(t.sheet.getRange(t.row, RV_GSC.IMG).getValue() || '').trim();
    if (img === 'Processing') return { ok: false, error: 'The Mac is generating right now — wait for it to finish.' };
    if (img !== 'Ready') return { ok: false, error: 'Post #' + n + ' images are ' + (img || 'blank') + ' — no reroll to withdraw.' };
    var sysrem = String(t.sheet.getRange(t.row, RV_GSC.SYSREM).getValue() || '');
    if (!/REROLL slide \d+/.test(rvLastRemark_(sysrem))) {
      return { ok: false, error: 'Post #' + n + ' is Ready for a first generation, not a reroll — leave it.' };
    }
    t.sheet.getRange(t.row, RV_GSC.IMG).setValue('Done');
    rvNote_(t.sheet, t.row, 'reroll withdrawn — kept the existing images');
    return { ok: true };
  });
}

/** RECORD a live post URL by hand. No UI in v2.0 (publish_runner fills O);
 * kept for emergencies — run from the editor if a hand-posted row needs O. */
function reviewRecordUrl(n, url) {
  return rvWithLock_(function () {
    var u = String(url || '').trim();
    if (!/^https?:\/\/(www\.)?instagram\.com\//i.test(u)) {
      return { ok: false, error: 'That does not look like an instagram.com post link.' };
    }
    var t = rvLocate_(n);
    t.sheet.getRange(t.row, RV_GSC.POSTURL).setValue(u);
    t.sheet.getRange(t.row, RV_GSC.POST).setValue('Done');   // trigger.gs stamps Post Date
    rvNote_(t.sheet, t.row, 'post URL recorded by hand');
    return { ok: true, status: 'Done' };
  });
}

/** CANCEL a scheduled or failed post: J and K cleared, back to the review feed. */
function reviewCancel(n) {
  if (rvIsEdu_(n)) {
    return rvWithLock_(function () { return rvEduCancel_(rvEduNum_(n)); });
  }
  return rvWithLock_(function () {
    var t = rvLocate_(n);
    var cur = String(t.sheet.getRange(t.row, RV_GSC.POST).getValue() || '').trim();
    if (cur !== 'Scheduled' && cur !== 'Hold') {
      return { ok: false, error: 'Post #' + n + ' is ' + (cur || 'not scheduled') + ' — nothing to cancel.' };
    }
    t.sheet.getRange(t.row, RV_GSC.POST).setValue('');
    t.sheet.getRange(t.row, RV_GSC.SCHED).setValue('');
    rvNote_(t.sheet, t.row, 'cancelled from the review page (was ' + cur + ')');
    return { ok: true };
  });
}

/** RETRY a publish-failed (Hold) row: J back to Scheduled for the next sweep. */
function reviewRetry(n) {
  return rvWithLock_(function () {
    var t = rvLocate_(n);
    var cur = String(t.sheet.getRange(t.row, RV_GSC.POST).getValue() || '').trim();
    if (cur !== 'Hold') return { ok: false, error: 'Post #' + n + ' is ' + (cur || 'blank') + ', not Hold.' };
    t.sheet.getRange(t.row, RV_GSC.POST).setValue('Scheduled');
    rvNote_(t.sheet, t.row, 'retry requested — back to Scheduled');
    return { ok: true };
  });
}

/** v2.0 — RESCHEDULE a Scheduled or Hold row to a new date; J becomes Scheduled. */
function reviewReschedule(n, date) {
  if (rvIsEdu_(n)) return { ok: false, error: 'Educational posts always take the next free Thursday — unapprove instead.' };
  return rvWithLock_(function () {
    var when = String(date || '').trim();
    if (!rvValidDate_(when)) return { ok: false, error: 'Pick a date first.' };
    var t = rvLocate_(n);
    var cur = String(t.sheet.getRange(t.row, RV_GSC.POST).getValue() || '').trim();
    if (cur !== 'Scheduled' && cur !== 'Hold') {
      return { ok: false, error: 'Post #' + n + ' is ' + (cur || 'not scheduled') + ' — approve it instead.' };
    }
    t.sheet.getRange(t.row, RV_GSC.POST).setValue('Scheduled');
    t.sheet.getRange(t.row, RV_GSC.SCHED).setValue(when);
    rvNote_(t.sheet, t.row, 'rescheduled to ' + when + (cur === 'Hold' ? ' after a failed publish' : ''));
    return { ok: true, when: when };
  });
}

/** One slide's thumbnail (data: URL, or 'ERR:...') for the page's lazy loader. */
function reviewThumb(fileId) {
  return rvDriveThumb_(String(fileId || ''));
}

/** A Drive link for one slide (never the bytes — the PNGs are ~20 MB). */
function reviewSlideFull(fileId) {
  try {
    var f = DriveApp.getFileById(fileId);
    return { ok: true, name: f.getName(), url: 'https://drive.google.com/file/d/' + fileId + '/view' };
  } catch (e) {
    return { ok: false, error: String(e && e.message || e) };
  }
}

// ── Page ────────────────────────────────────────────────────────────────────

function doGetReview_() {
  var state;
  try { state = reviewState(); }
  catch (e) {
    return HtmlService.createHtmlOutput(
      '<p style="font:15px system-ui;padding:32px">Could not load the queue: ' +
      rvEsc_(String(e && e.message || e)) + '</p>');
  }
  return HtmlService.createHtmlOutput(rvPageHtml_(state))
    .setTitle('Selene Review')
    .addMetaTag('viewport', 'width=device-width, initial-scale=1, viewport-fit=cover');
}

function reviewUrl_() {
  // ScriptApp.getService().getUrl() is NOT trustworthy from a time trigger
  // (it once returned a dead deployment). PICKER_URL is the known-good address.
  var stored = PropertiesService.getScriptProperties().getProperty('PICKER_URL');
  var base = stored || ScriptApp.getService().getUrl() || '';
  return base ? base + '?view=review' : '(open the picker link and add ?view=review)';
}

function rvPageHtml_(state) {
  var json = JSON.stringify(state).replace(/<\//g, '<\\/');
  return '<!DOCTYPE html><html><head><meta charset="utf-8">' +
    '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">' +
    '<link rel="preconnect" href="https://fonts.googleapis.com">' +
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>' +
    '<link href="https://fonts.googleapis.com/css2?family=Archivo:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">' +
    '<style>' + rvCss_() + '</style></head><body>' +
    '<div id="app"></div>' +
    '<div id="sheetwrap" class="sheetwrap" hidden><div class="scrim" data-close="1"></div><div id="sheet" class="sheet"></div></div>' +
    '<div id="lb" class="lb" hidden></div>' +
    '<div id="toast" class="toast"></div>' +
    '<script>var RV_STATE=' + json + ';</script>' +
    '<script>' + rvJs_() + '</script>' +
    '</body></html>';
}

// ── CSS ─────────────────────────────────────────────────────────────────────
// Desktop (>= 900px): sidebar | main. Mobile: tabs + pushed detail; sheets.
function rvCss_() { return `
*{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#F5F3EF;--ink:#273F22;--soft:#6f7768;--line:#ded9cc;--card:#fff;--ecru:#E8E4D8;
--ok:#3d6b34;--danger:#c2492f;--dangerbg:#f9ebe6;--sage:#7C896F;--sagebg:#f1f3ee;--gold:#8a6d3b;
--wedge:#335875;--apr:#b8552f;--aprbg:#f7e9e2;--mut:#f1efe8;--dim:#9a9384;
--sans:Archivo,-apple-system,"Segoe UI",system-ui,sans-serif;--mono:"IBM Plex Mono",ui-monospace,Menlo,monospace}
html,body{background:var(--bg);color:var(--ink);font-family:var(--sans);-webkit-text-size-adjust:100%}
button{font:inherit;cursor:pointer;color:inherit;background:none;border:0}
a{color:var(--wedge)}
.mono{font-family:var(--mono)}
.lab{font:600 9.5px/1 var(--mono);color:var(--soft);text-transform:uppercase;letter-spacing:.11em}
.lab.red{color:var(--danger)}.lab.sage{color:var(--sage)}.lab.ok{color:var(--ok)}
.stripe{background:repeating-linear-gradient(45deg,#E8E4D8 0 7px,#efece3 7px 14px)}
@keyframes spin{to{transform:rotate(360deg)}}
.spin{width:18px;height:18px;border-radius:50%;border:2px solid var(--line);border-top-color:var(--sage);animation:spin .9s linear infinite;flex:none}
.btn{display:inline-flex;align-items:center;justify-content:center;gap:7px;height:42px;padding:0 18px;border-radius:8px;font:600 13px/1 var(--sans);white-space:nowrap;border:1.5px solid var(--ink);background:var(--ink);color:var(--bg)}
.btn.ghost{background:#fff;color:var(--ink)}.btn.soft{background:transparent;border-color:var(--line);color:var(--soft)}
.btn.danger{background:var(--danger);border-color:var(--danger);color:#fff}
.btn.dangerline{background:transparent;border-color:var(--danger);color:var(--danger)}
.btn.link{border:0;background:none;color:var(--soft);text-decoration:underline;text-underline-offset:3px;font-weight:500;padding:0 6px}
.btn:disabled{opacity:.45;cursor:default}
.btn.small{height:36px;padding:0 12px;font-size:12px}
/* ── header ── */
.top{display:flex;align-items:center;justify-content:space-between;gap:14px;padding:18px 24px;border-bottom:2px solid var(--ink);background:var(--bg)}
.brand{font:600 19px/1.1 var(--sans)}
.top .sub{font:500 11px/1.4 var(--mono);color:var(--soft);text-transform:uppercase;letter-spacing:.09em;margin-top:5px}
.top .auto{font:500 11px/1.4 var(--mono);color:var(--ok);text-align:right}
.tabs{display:none}
/* ── layout ── */
.grid{display:grid;grid-template-columns:308px minmax(0,1fr);align-items:start;min-height:calc(100vh - 78px)}
.side{border-right:1px solid var(--line);padding:16px 0 22px;position:sticky;top:0;max-height:100vh;overflow:auto}
.main{min-width:0}
/* ── sidebar ── */
.grp{padding:0 18px 9px}.grp+.grp{padding-top:20px}
.qrow{display:flex;gap:11px;align-items:center;padding:11px 18px;border-left:3px solid transparent;cursor:pointer;min-height:56px}
.qrow:hover{background:#faf9f5}
.qrow.on{background:var(--ecru);border-left-color:var(--ink)}
.qrow.att{background:var(--dangerbg);border-left-color:var(--danger)}
.qrow.att.on{border-left-color:var(--ink)}
.qrow.regen{background:var(--sagebg);border-left-color:var(--sage)}
.qrow.regen.on{border-left-color:var(--ink)}
.qrow.sched{border-left-color:transparent}.qrow.sched .qm{color:var(--ok)}.qrow.sched.on{border-left-color:var(--ink)}
.qthumb{width:34px;height:34px;flex:none;border-radius:6px;border:1px solid var(--line);overflow:hidden}
.qthumb img{width:100%;height:100%;object-fit:cover;display:block}
.qmain{min-width:0;flex:1}
.qt{font:600 12.5px/1.3 var(--sans);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.qm{font:500 10.5px/1.4 var(--mono);color:var(--soft)}
.qrow.att .qm{color:var(--danger)}
.qchev{color:var(--dim);font-size:17px;display:none}
.empty-side{padding:12px 18px;font:400 12px/1.5 var(--sans);color:var(--dim)}
/* ── calendar ── */
.calwrap{border-top:1px solid var(--line);margin-top:18px;padding:16px 18px 0}
.calhead{display:flex;align-items:center;justify-content:space-between;margin-bottom:10px}
.calhead .nav{width:34px;height:34px;display:flex;align-items:center;justify-content:center;color:var(--soft);font-size:17px;border-radius:6px}
.calhead .nav:hover{background:var(--ecru)}
.calttl{text-align:center}
.calttl .m{font:600 10px/1 var(--mono);text-transform:uppercase;letter-spacing:.11em}
.calttl .c{font:500 10px/1.6 var(--mono);color:var(--dim)}
.dow{display:grid;grid-template-columns:repeat(7,1fr);gap:3px;margin-bottom:4px}
.dow div{font:600 8.5px/1.6 var(--mono);text-align:center;color:#b6b0a2}.dow div.cad{color:var(--ink)}
.days{display:grid;grid-template-columns:repeat(7,1fr);gap:3px}
.day{position:relative;aspect-ratio:1/1;border:1px solid #e6e2d8;background:#faf9f5;border-radius:5px;cursor:pointer;padding:3px;min-height:38px}
.day.has{background:#fff;border-color:var(--line)}
.day.out{background:var(--mut)}.day.out .num{color:var(--dim)}
.day.today{border-color:var(--ink)}
.day.sel{border:2px solid var(--ink);background:var(--ecru)}
.day:hover{border-color:var(--sage)}
.day .num{font:400 9px/1.4 var(--mono);color:var(--soft);display:inline-block;padding:0 3px;border-radius:3px}
.day.cad .num{font-weight:600;color:var(--ink)}
.day.today .num{background:var(--ink);color:var(--bg)}
.day .cnt{font:600 13px/1.1 var(--sans);text-align:center;margin-top:1px}
.day.fail .cnt{color:var(--danger)}
.day .marks{display:flex;gap:2px;justify-content:center;margin-top:3px;flex-wrap:wrap}
.mark{width:5px;height:5px;border-radius:50%;border:1px solid transparent}
.mark.AI{background:var(--ink);border-color:var(--ink)}.mark.ED{background:var(--wedge);border-color:var(--wedge)}
.mark.RE{background:var(--apr);border-color:var(--apr)}.mark.TR{background:var(--gold);border-color:var(--gold)}
.mark.fail{background:transparent!important;border-color:var(--danger)!important}
.legend{display:grid;grid-template-columns:1fr 1fr;gap:5px 10px;margin-top:12px}
.legend div{display:flex;align-items:center;gap:6px;font:400 10.5px/1.3 var(--sans);color:var(--soft)}
.tag{width:16px;height:16px;border-radius:4px;color:var(--bg);font:600 8px/16px var(--mono);text-align:center;flex:none}
.tag.AI{background:var(--ink)}.tag.ED{background:var(--wedge)}.tag.RE{background:var(--apr)}.tag.TR{background:var(--gold)}
.tag.big{width:26px;height:26px;border-radius:5px;font-size:9.5px;line-height:26px}
.failring{width:16px;height:16px;border-radius:50%;border:2px solid var(--danger);flex:none}
/* ── main pane ── */
.phead{border-bottom:1px solid var(--line);padding:16px 24px;display:flex;align-items:center;gap:16px;flex-wrap:wrap;background:var(--bg)}
.ptitle{font:600 16px/1.2 var(--sans)}
.pmeta{font:500 10.5px/1.5 var(--mono);color:var(--soft)}
.pacts{display:flex;align-items:flex-start;gap:10px;margin-left:auto}
.datecol{display:flex;flex-direction:column;gap:6px}
.datenote{font:400 10.5px/1.3 var(--mono);color:var(--gold);max-width:170px}
.back{display:none}
.rejectbox,.rerollbox{display:none;padding:16px 24px;border-bottom:1px solid var(--line);background:#fff}
.rejectbox.on,.rerollbox.on{display:block}
.rejectbox input{width:100%;font:400 13px/1.5 var(--sans);padding:11px 13px;border:1.5px solid var(--line);border-radius:8px;background:var(--bg);color:var(--ink);margin-top:8px}
.rejectbox .hint{font:500 11.5px/1.4 var(--mono);color:var(--danger);margin-top:7px;min-height:16px}
.rejectbox .row{display:flex;gap:9px;margin-top:14px}
.orderwrap{padding:18px 24px 0}
.orderrow{display:flex;align-items:center;gap:12px;flex-wrap:wrap}
.order{display:flex;gap:6px;align-items:flex-end}
.oth{display:flex;flex-direction:column;align-items:center;gap:4px}
.oth .box{position:relative;width:46px;height:46px;border-radius:6px;border:2px solid var(--sage);overflow:hidden;cursor:grab}
.oth .box img{width:100%;height:100%;object-fit:cover;display:block}
.oth.cover .box{border-color:var(--ink)}
.oth .box .n{position:absolute;bottom:-1px;right:-1px;background:var(--sage);color:var(--bg);border-radius:4px 0 4px 0;padding:1px 5px;font:600 9px/1.5 var(--mono)}
.oth.cover .box .n{background:var(--ink)}
.oth .cl{font:600 8.5px/1 var(--mono);text-transform:uppercase;letter-spacing:.09em;visibility:hidden}
.oth.cover .cl{visibility:visible}
.oth.dragover .box{outline:2px dashed var(--gold);outline-offset:2px}
.coverwarn{display:none;margin-top:12px;background:var(--aprbg);border-left:3px solid var(--apr);border-radius:0 6px 6px 0;padding:9px 13px;font:400 12px/1.4 var(--sans);color:var(--apr)}
.coverwarn.on{display:block}
.rail{padding:16px 24px 0;display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:14px}
.slide{position:relative}
.shot{position:relative;aspect-ratio:1/1;border-radius:10px;border:2px solid var(--line);overflow:hidden;background:var(--mut)}
.slide.cover .shot{border-color:var(--ink)}
.slide.dropped .shot{border-color:#dcd8ce}
.shot img{width:100%;height:100%;object-fit:cover;display:block}
.slide.dropped .shot img{filter:grayscale(1)}
.badge{position:absolute;top:7px;left:7px;background:rgba(255,255,255,.92);color:var(--soft);border-radius:4px;padding:2px 7px;font:600 9.5px/1.5 var(--mono);z-index:2}
.slide.cover .badge{background:var(--ink);color:var(--bg)}
.ph{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:8px;padding:14px;text-align:center}
.ph .t{font:500 10px/1.3 var(--mono);color:var(--soft)}
.ph .e{font:400 9px/1.4 var(--mono);color:var(--dim);word-break:break-word}
.ph .t.b{font:600 11px/1.3 var(--sans);color:var(--ink)}
.ph a{font:600 11px/1 var(--sans);text-decoration:underline;text-underline-offset:2px;cursor:pointer}
.dropflag{position:absolute;inset:0;display:none;align-items:center;justify-content:center;background:rgba(20,26,18,.62);color:var(--bg);font:600 11px/1 var(--mono);letter-spacing:.1em;z-index:3}
.slide.dropped .dropflag{display:flex}
.sbar{display:flex;align-items:center;gap:8px;margin-top:7px}
.sbar .drop{flex:1;height:34px;border:1.5px solid var(--line);border-radius:6px;color:var(--soft);font:600 11.5px/1 var(--sans)}
.slide.dropped .sbar .drop{background:var(--gold);border-color:var(--gold);color:var(--bg)}
.sbar .more{height:34px;padding:0 10px;border:1.5px solid var(--line);border-radius:6px;color:var(--soft);font:600 11.5px/1 var(--mono)}
.sbar .mv{height:34px;width:32px;flex:none;border:1.5px solid var(--line);border-radius:6px;color:var(--soft);font:600 11px/1 var(--sans)}
.sbar .mv:disabled,.sbar .drop:disabled{opacity:.35;cursor:default}
.shot.zoom{cursor:zoom-in}
/* v2.5 lightbox */
.lb{position:fixed;inset:0;z-index:60}.lb[hidden]{display:none}
.lbscrim{position:absolute;inset:0;background:rgba(20,26,18,.86)}
.lbbox{position:absolute;inset:0;display:flex;flex-direction:column;pointer-events:none}
.lbhead{pointer-events:auto;display:flex;align-items:center;gap:12px;padding:12px 18px;color:var(--bg)}
.lbhead .lbt{font:600 14px/1.3 var(--sans);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;min-width:0}
.lbhead .lbm{font:500 10.5px/1.4 var(--mono);color:#cfcabd;white-space:nowrap}
.lbhead .btn{margin-left:auto;background:transparent;color:var(--bg);border-color:#8c9483}
.lbx{width:40px;height:40px;font-size:26px;color:var(--bg);flex:none}
.lbimg{flex:1;min-height:0;display:flex;align-items:center;justify-content:center;position:relative;padding:0 64px 24px}
.lbimg img{pointer-events:auto;max-width:100%;max-height:100%;object-fit:contain;border-radius:8px;box-shadow:0 20px 60px rgba(0,0,0,.5)}
.lbmsg{color:var(--bg);font:500 12px/1.4 var(--mono);display:flex;gap:10px;align-items:center}
.lbnav{pointer-events:auto;position:absolute;top:50%;transform:translateY(-50%);width:52px;height:64px;color:var(--bg);font-size:38px;border-radius:8px}
.lbnav:hover{background:rgba(255,255,255,.12)}.lbnav.l{left:8px}.lbnav.r{right:8px}
/* v2.5 day-panel slide strip */
.daystrip{display:flex;gap:5px;margin-top:8px;overflow-x:auto;padding-bottom:2px}
.dth{width:52px;height:52px;flex:none;border-radius:6px;border:1px solid var(--line);overflow:hidden;cursor:zoom-in;display:flex;align-items:center;justify-content:center}
.dth img{width:100%;height:100%;object-fit:cover;display:block}
.dth .n{font:600 10px/1 var(--mono);color:var(--dim)}
.sbar .more.on{background:var(--ink);border-color:var(--ink);color:var(--bg)}
.menu{position:absolute;top:100%;right:0;z-index:8;width:214px;background:#fff;border:2px solid var(--ink);border-radius:9px;box-shadow:0 10px 26px rgba(39,63,34,.18);padding:6px;margin-top:5px}
.mi{padding:8px 10px;border-radius:6px;cursor:pointer;font:500 12.5px/1.2 var(--sans)}
.mi:hover{background:#faf9f5}.mi.off{color:#b6b0a2;cursor:default;background:#f4f2ec}
.mi b{display:block;font-weight:600}.mi small{display:block;font:500 10px/1.4 var(--mono);color:var(--soft)}
.mi.off small{color:#b6b0a2}
.dots{display:none}
.capwrap{padding:22px 24px 26px}
.caplab{display:flex;align-items:baseline;gap:10px;margin-bottom:8px}
.caplab .h{font:400 11.5px/1 var(--sans);color:var(--dim)}
textarea.cap{width:100%;font:400 13.5px/1.65 var(--sans);color:var(--ink);background:#fff;border:1.5px solid var(--line);border-radius:10px;padding:14px 16px;min-height:110px;resize:vertical}
.qa{margin-top:10px;border-top:1px solid #e2ddd0;padding-top:10px}
.qa .tg{font:500 11.5px/1 var(--mono);color:var(--soft);cursor:pointer;height:32px;display:flex;align-items:center}
.qa ul{list-style:none;display:none;flex-direction:column;gap:6px;margin-top:4px}
.qa.on ul{display:flex}
.qa li{display:flex;gap:9px;align-items:flex-start;font:400 12px/1.45 var(--sans);color:var(--soft)}
.qa li:before{content:"";width:5px;height:5px;border-radius:50%;background:var(--gold);margin-top:6px;flex:none}
.qa .note{display:none;font:400 10.5px/1.4 var(--mono);color:var(--dim);margin-top:8px}.qa.on .note{display:block}
.foot{text-align:center;font:400 10.5px/1.6 var(--mono);color:var(--dim);padding:24px 16px}
.mainempty{padding:64px 46px;text-align:center}
.mainempty .h{font:600 17px/1.3 var(--sans)}
.mainempty .p{font:400 13px/1.6 var(--sans);color:var(--soft);margin-top:12px;max-width:460px;margin-left:auto;margin-right:auto}
.regenpane{padding:60px 34px;display:flex;flex-direction:column;align-items:center;text-align:center;gap:12px}
.regenpane .h{font:600 15px/1.3 var(--sans)}.regenpane .p{font:400 12.5px/1.5 var(--sans);color:var(--soft);max-width:330px}
/* failed post */
.failbanner{background:var(--dangerbg);border-bottom:2px solid var(--danger);padding:16px 24px}
.failbanner .r{font:600 14px/1.35 var(--sans);color:var(--danger)}
.failbanner .p{font:400 12px/1.5 var(--sans);color:var(--soft);margin-top:5px}
.failbanner .raw{font:400 10px/1.5 var(--mono);color:var(--dim);margin-top:9px;word-break:break-word}
.ro .shot{opacity:.82}
.rolab{padding:16px 24px 0;display:flex;align-items:center;gap:10px}
.rolab span:last-child{flex:1;height:1px;background:#e2ddd0}
.rocap{background:#f4f2ec;border:1.5px solid #e4e0d6;border-radius:10px;padding:13px 15px;font:400 13px/1.6 var(--sans);color:var(--soft);white-space:pre-wrap}
/* sheets / dialogs */
.sheetwrap{position:fixed;inset:0;z-index:50}
.sheetwrap[hidden]{display:none}
.scrim{position:absolute;inset:0;background:rgba(20,26,18,.42)}
.sheet{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);width:min(420px,calc(100vw - 32px));max-height:88vh;overflow:auto;background:var(--bg);border:2px solid var(--ink);border-radius:12px;padding:22px 22px 20px}
.sheet .grab{display:none}
.sheet .h{font:600 16px/1.3 var(--sans)}
.sheet .s{font:500 10.5px/1.5 var(--mono);color:var(--soft);margin-top:3px}
.sheet .p{font:400 13px/1.6 var(--sans);color:var(--soft);margin-top:9px}
.sheet .att{font:500 10.5px/1 var(--mono);color:var(--gold);margin-top:12px}
.sheet .row{display:flex;gap:9px;margin-top:18px}
.sheet .row .btn{flex:1}
.sheet .list{margin-top:14px;border-top:1px solid #e2ddd0}
.sheet .li{min-height:52px;display:flex;align-items:center;gap:10px;border-bottom:1px solid #ede9df;cursor:pointer;padding:6px 0}
.sheet .li.off{cursor:default}.sheet .li.off b,.sheet .li.off small{color:#b6b0a2}
.sheet .li div{flex:1}.sheet .li b{font:600 14px/1.3 var(--sans)}.sheet .li small{display:block;font:500 10.5px/1.5 var(--mono);color:var(--soft)}
.sheet .li .ch{color:var(--dim);font-size:16px}
.sheet .dayitem{padding:13px 0;border-bottom:1px solid #ede9df;display:flex;gap:11px;align-items:flex-start}
.sheet .dayitem .t{font:600 13.5px/1.3 var(--sans)}
.sheet .dayitem .m{font:500 10.5px/1.5 var(--mono);color:var(--soft)}
.sheet .dayitem .m.pub{color:var(--ok)}.sheet .dayitem .m.fail{color:var(--danger)}
.sheet .dayitem .acts{display:flex;gap:7px;margin-top:9px;flex-wrap:wrap}
.sheet .note{font:400 11px/1.5 var(--sans);color:var(--dim);margin-top:12px}
.sheet .pick{margin-top:8px}
.sheet .pick .days{gap:3px}.sheet .pick .day{min-height:44px}
.sheet .picknote{font:400 12px/1.45 var(--sans);color:var(--gold);margin-top:12px;min-height:16px}
.sheet .full{width:100%;margin-top:14px;height:48px}
.sheet .full+.full{margin-top:8px;height:46px}
.toast{position:fixed;left:50%;bottom:22px;transform:translate(-50%,300%);opacity:0;background:var(--ink);color:#fff;font:500 12.5px/1.4 var(--sans);padding:12px 20px;border-radius:24px;transition:transform .22s ease;max-width:88vw;text-align:center;z-index:99}
.toast.show{transform:translate(-50%,0);opacity:1}.toast.bad{background:var(--danger)}
@media(prefers-reduced-motion:reduce){.toast{transition:none}}
/* ── MOBILE ── */
@media(max-width:899px){
  body{padding-bottom:env(safe-area-inset-bottom)}
  .top{display:block;padding:12px 16px 0;border-bottom:0;position:sticky;top:0;z-index:5}
  .brand{font-size:17px}.top .sub{margin-top:3px;text-transform:none;letter-spacing:0}
  .top .auto{display:none}
  .tabs{display:flex;gap:4px;padding:10px 0;border-bottom:2px solid var(--ink)}
  .tabs button{flex:1;height:44px;border-radius:8px;background:#fff;border:1px solid var(--line);color:var(--soft);font:600 13.5px/1 var(--sans)}
  .tabs button.on{background:var(--ink);border-color:var(--ink);color:var(--bg)}
  .grid{display:block;min-height:0}
  .side{border:0;padding:0 0 30px;position:static;max-height:none;overflow:visible}
  .qrow{padding:11px 16px}.qthumb{width:44px;height:44px;border-radius:8px}
  .qt{font-size:13.5px}.qchev{display:block}
  .calwrap{border:0;margin:0;padding:14px 14px 0}
  .day{min-height:60px;border-radius:8px;padding:4px}.day .num{font-size:10px}.day .cnt{font-size:15px;margin-top:2px}
  .legend{gap:7px 12px;margin-top:16px}.legend div{font-size:11.5px}.tag{width:18px;height:18px;font-size:8.5px;line-height:18px}
  body.v-queue .top,body.v-cal .top{display:block}
  body.v-queue .grid .side .calwrap,body.v-cal .grid .side .qlist{display:none}
  body.v-queue .main,body.v-cal .main{display:none}
  body.v-post .top,body.v-post .side{display:none}
  body.v-post .main{display:block;padding-bottom:96px}
  .phead{position:sticky;top:0;z-index:5;padding:0 8px;height:56px;flex-wrap:nowrap;gap:4px;border-bottom:1px solid var(--line)}
  .back{display:flex;width:44px;height:44px;align-items:center;justify-content:center;font-size:22px;flex:none}
  .ptitle{font-size:14.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .pmeta{font-size:9.5px}
  .phead .pacts{position:fixed;left:0;right:0;bottom:0;z-index:6;margin:0;background:var(--bg);border-top:2px solid var(--ink);padding:10px 12px calc(10px + env(safe-area-inset-bottom));align-items:center;gap:8px}
  .datecol{flex:none}.datenote{display:none}
  .pacts .approve{flex:1}
  .pacts .btn.dangerline{border:0;background:none;padding:0 6px;width:auto}
  .rejectbox,.rerollbox{position:fixed;left:0;right:0;bottom:82px;z-index:6;border-top:1px solid var(--line);padding:16px}
  .orderwrap{padding:12px 16px 0}.orderrow{gap:9px}.order{gap:7px;overflow-x:auto;max-width:100%}
  .oth .box{width:64px;height:64px;border-radius:8px}
  .rail{display:flex;overflow-x:auto;scroll-snap-type:x mandatory;-webkit-overflow-scrolling:touch;padding:12px 0 0;gap:0}
  .slide{flex:0 0 100%;scroll-snap-align:center}
  .shot{border-radius:0;border-left:0;border-right:0;border-width:1px}
  .sbar{padding:0 16px}.sbar .drop,.sbar .more,.sbar .mv{height:44px}.sbar .more,.sbar .mv{width:44px}
  .lbimg{padding:0 8px 16px}.lbnav{width:40px;height:56px;font-size:30px}.lbhead{flex-wrap:wrap;gap:8px}.lbhead .btn{margin-left:0}
  .menu{display:none}
  .dots{display:flex;align-items:center;justify-content:center;gap:8px;padding:11px 0 0}
  .dots i{width:7px;height:7px;border-radius:50%;background:#cfcabd}.dots i.on{background:var(--ink)}
  .dots span{font:500 10.5px/1 var(--mono);color:var(--soft);margin-left:6px}
  .capwrap{padding:18px 16px 20px}
  .regenpane,.mainempty{padding:60px 26px}
  .failbanner{padding:14px 16px}
  .rolab{padding:16px 16px 0}
  .sheet{left:0;right:0;top:auto;bottom:0;transform:none;width:auto;max-height:86vh;border:0;border-radius:20px 20px 0 0;padding:10px 16px calc(26px + env(safe-area-inset-bottom))}
  .sheet .grab{display:block;width:38px;height:4px;border-radius:2px;background:var(--line);margin:0 auto 14px}
}
@media(min-width:900px){
  body.v-post .main{display:block}
}
`; }

// ── Client JS ───────────────────────────────────────────────────────────────
// Rendered entirely client-side from RV_STATE. No template literals or
// backticks inside this string (it lives in one).
function rvJs_() { return `
var S = RV_STATE; S.scheduled = S.scheduled || [];
var MOBILE = window.matchMedia('(max-width:899px)');
var UI = { view: 'queue', sel: null, month: S.today.slice(0, 7), menu: null, busy: false };
var ORD = {}, DROP = {}, CAP = {}, DATE = {}, REJ = {}, QA = {}, CUR = {}, THUMB = {};
var RRL = {};   // post -> slide index whose reroll comment box is open (educational only)
var LB = null;  // lightbox: {ids:[], labels:[], i} (v2.5)
var DAYOPEN = null;   // date whose day panel is open, so thumbnails can patch it (v2.5)
var TYPES = { AI: 'AI carousel', ED: 'Educational', RE: 'Reel', TR: 'Trial reel' };
var CAD = [2, 4, 6];
var DOWS = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];
var MONTHS = ['January','February','March','April','May','June','July','August','September','October','November','December'];

function esc(s){return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}
function pad(n){return (n<10?'0':'')+n;}
function fmtShort(d){ if(!d) return ''; var p=d.split('-'); var dt=new Date(Number(p[0]),Number(p[1])-1,Number(p[2])); return DOWS[(dt.getDay()+6)%7]+' '+p[1]+'-'+p[2]; }
function fmtLong(d){ var p=d.split('-'); var dt=new Date(Number(p[0]),Number(p[1])-1,Number(p[2])); return DOWS[(dt.getDay()+6)%7]+' '+d; }
function toast(msg,bad){var t=document.getElementById('toast');t.textContent=msg;t.className='toast show'+(bad?' bad':'');clearTimeout(t._h);t._h=setTimeout(function(){t.className='toast';},3400);}
function lock(on){UI.busy=on;document.body.style.cursor=on?'progress':'';}
function run(fn){ var a=[].slice.call(arguments,1); var ok=a.pop(), bad=a.pop(); lock(true);
  var r=google.script.run.withSuccessHandler(function(res){lock(false);ok(res);}).withFailureHandler(function(e){lock(false);(bad||function(m){toast(m,true);})(String(e&&e.message||e));});
  r[fn].apply(r,a); }

/* ── post helpers ── */
function post(n){ for(var i=0;i<S.pending.length;i++) if(S.pending[i].n===n) return S.pending[i]; return null; }
function att(n){ for(var i=0;i<S.attention.length;i++) if(S.attention[i].n===n) return S.attention[i]; return null; }
function sch(n){ for(var i=0;i<S.scheduled.length;i++) if(S.scheduled[i].n===n) return S.scheduled[i]; return null; }
function regenOf(n){ for(var i=0;i<S.regen.length;i++) if(S.regen[i].n===n) return S.regen[i]; return null; }
function isEdu(p){ return p&&p.lane==='edu'; }
function orderOf(x){ var o=String(x.slides||'').split(',').map(Number).filter(function(v){return v>0&&v<=x.slideIds.length;}); if(!o.length) o=x.slideIds.map(function(_,i){return i+1;}); return o; }
function ord(p){ if(!ORD[p.n]){ ORD[p.n]=[]; for(var i=1;i<=p.slideIds.length;i++) ORD[p.n].push(i);} return ORD[p.n]; }
function dropped(n,i){ return !!(DROP[n]&&DROP[n][i]); }
function kept(p){ return ord(p).filter(function(i){return !dropped(p.n,i);}); }
function dateFor(n){ return DATE[n]||S.defaultDate; }
function capFor(p){ return CAP[p.n]!=null?CAP[p.n]:p.caption; }

/* ── calendar index ── */
function calIndex(){ var m={}; S.calendar.forEach(function(it){ (m[it.date]=m[it.date]||[]).push(it); }); return m; }
function monthCells(mk){ var y=Number(mk.slice(0,4)), m=Number(mk.slice(5,7))-1; var first=new Date(y,m,1); var lead=(first.getDay()+6)%7; var start=new Date(y,m,1-lead); var cells=[]; for(var i=0;i<42;i++){ var d=new Date(start.getFullYear(),start.getMonth(),start.getDate()+i); cells.push({key:d.getFullYear()+'-'+pad(d.getMonth()+1)+'-'+pad(d.getDate()),num:d.getDate(),out:d.getMonth()!==m,dow:d.getDay()}); if(i>=34&&d.getMonth()!==m&&d.getDay()===0) break; } return cells; }
function shiftMonth(mk,n){ var y=Number(mk.slice(0,4)), m=Number(mk.slice(5,7))-1+n; var d=new Date(y,m,1); return d.getFullYear()+'-'+pad(d.getMonth()+1); }
function monthStats(mk,idx){ var out=0,q=0; Object.keys(idx).forEach(function(k){ if(k.slice(0,7)!==mk) return; idx[k].forEach(function(it){ if(it.status==='pub') out++; else q++; }); }); return out+' out · '+q+' queued'; }
function renderMonth(mk,idx,opts){ opts=opts||{}; var cells=monthCells(mk); var h='';
  h+='<div class="calhead"><button class="nav" data-act="'+(opts.nav||'month')+'" data-d="-1">‹</button><div class="calttl"><div class="m">'+MONTHS[Number(mk.slice(5,7))-1]+' '+mk.slice(0,4)+'</div><div class="c">'+(opts.sub!=null?opts.sub:monthStats(mk,idx))+'</div></div><button class="nav" data-act="'+(opts.nav||'month')+'" data-d="1">›</button></div>';
  h+='<div class="dow">'+DOWS.map(function(d,i){return '<div class="'+(CAD.indexOf((i+1)%7)>-1?'cad':'')+'">'+d+'</div>';}).join('')+'</div><div class="days">';
  cells.forEach(function(c){ var items=idx[c.key]||[]; var fail=items.some(function(x){return x.status==='fail';});
    var cls='day'+(items.length?' has':'')+(c.out?' out':'')+(c.key===S.today?' today':'')+(CAD.indexOf(c.dow)>-1?' cad':'')+(fail?' fail':'')+(opts.sel===c.key?' sel':'');
    h+='<div class="'+cls+'" data-act="'+(opts.dayAct||'day')+'" data-date="'+c.key+'"><span class="num">'+pad(c.num)+'</span>';
    if(items.length){ h+='<div class="cnt">'+items.length+'</div><div class="marks">'+items.slice(0,4).map(function(x){return '<i class="mark '+x.type+(x.status==='fail'?' fail':'')+'"></i>';}).join('')+'</div>'; }
    h+='</div>'; });
  return h+'</div>'; }
function legendHtml(){ return '<div class="legend">'+Object.keys(TYPES).map(function(k){return '<div><span class="tag '+k+'">'+k+'</span>'+TYPES[k]+'</div>';}).join('')+'<div><span class="failring"></span>publish failed</div></div>'; }

/* ── render ── */
function render(){ var app=document.getElementById('app'); var idx=calIndex();
  var nAtt=S.attention.length, nPend=S.pending.length;
  var sub = nPend? nPend+' post'+(nPend===1?'':'s')+' ready for you' : 'Nothing waiting.'; if(nAtt) sub+=' · '+nAtt+' needs attention';
  var h='<header class="top"><div><div class="brand">Selene Dreams Post Review</div><div class="sub">'+esc(sub)+'</div>'+
    '<div class="tabs"><button data-act="tab" data-v="queue" class="'+(UI.view!=='cal'?'on':'')+'">Queue ('+(nPend+nAtt)+')</button><button data-act="tab" data-v="cal" class="'+(UI.view==='cal'?'on':'')+'">Calendar</button></div></div>'+
    '<div class="auto">publishing is automatic<br>Tue / Thu / Sat · 21:00 America/New_York</div></header>';
  h+='<div class="grid"><aside class="side"><div class="qlist">';
  if(nAtt){ h+='<div class="grp lab red">needs attention</div>'; S.attention.forEach(function(a){ var on=UI.sel&&UI.sel.kind==='att'&&UI.sel.n===a.n; h+='<div class="qrow att'+(on?' on':'')+'" data-act="sel" data-kind="att" data-n="'+a.n+'"><div class="qthumb stripe">'+thumbImg(a.slideIds[0])+'</div><div class="qmain"><div class="qt">'+esc(a.title)+'</div><div class="qm">row '+a.n+' · publish failed'+(a.when?' · '+fmtShort(a.when):'')+'</div></div><span class="qchev">›</span></div>'; }); }
  h+='<div class="grp lab">waiting on you</div>';
  if(!nPend) h+='<div class="empty-side">Nothing waiting on you.</div>';
  S.pending.forEach(function(p){ var on=UI.sel&&UI.sel.kind==='post'&&UI.sel.n===p.n; h+='<div class="qrow'+(on?' on':'')+'" data-act="sel" data-kind="post" data-n="'+p.n+'"><div class="qthumb stripe">'+thumbImg(p.slideIds[0])+'</div><div class="qmain"><div class="qt">'+esc(p.title)+'</div><div class="qm">'+(p.lane==='edu'?'EDUCATIONAL':'AI carousel')+' · row '+p.num+' · '+p.slideIds.length+' slide'+(p.slideIds.length===1?'':'s')+'</div></div><span class="qchev">›</span></div>'; });
  if(S.regen.length){ h+='<div class="grp lab sage">regenerating</div>'; S.regen.forEach(function(r){ var on=UI.sel&&UI.sel.kind==='regen'&&UI.sel.n===r.n; h+='<div class="qrow regen'+(on?' on':'')+'" data-act="sel" data-kind="regen" data-n="'+r.n+'"><span class="spin"></span><div class="qmain"><div class="qt">'+esc(r.title)+'</div><div class="qm">row '+r.n+' · '+(r.img==='Processing'?'generating now':'waiting for the Mac')+' · asked for slide '+r.slide+' · attempt '+r.attempt+' of '+r.max+'</div></div><span class="qchev">›</span></div>'; }); }
  if(S.scheduled.length){ h+='<div class="grp lab ok">scheduled</div>'; S.scheduled.forEach(function(s){ var on=UI.sel&&UI.sel.kind==='sched'&&UI.sel.n===s.n; h+='<div class="qrow sched'+(on?' on':'')+'" data-act="sel" data-kind="sched" data-n="'+s.n+'"><div class="qthumb stripe">'+thumbImg(s.slideIds[orderOf(s)[0]-1])+'</div><div class="qmain"><div class="qt">'+esc(s.title)+'</div><div class="qm">'+(s.lane==='edu'?'EDUCATIONAL':'AI carousel')+' · row '+s.num+' · '+(s.when?fmtShort(s.when)+' 21:00 NY':'next free Thursday')+'</div></div><span class="qchev">›</span></div>'; }); }
  h+='<div class="foot mfoot">'+footText()+'</div></div>';
  h+='<div class="calwrap">'+renderMonth(UI.month,idx,{})+legendHtml()+'<div class="foot mfoot">'+footText()+'</div></div></aside>';
  h+='<main class="main">'+renderMain()+'</main></div>';
  app.innerHTML=h;
  document.body.className='v-'+UI.view;
  // desktop side footers are noise; mobile shows one per tab
  if(!MOBILE.matches){ var fs=app.querySelectorAll('.mfoot'); for(var i=0;i<fs.length;i++) fs[i].style.display='none'; }
  if(UI.sel&&UI.sel.kind==='post'){ var p=post(UI.sel.n); if(p) loadThumbs(p.slideIds); }
  if(UI.sel&&UI.sel.kind==='att'){ var a=att(UI.sel.n); if(a) loadThumbs(a.slideIds); }
  if(UI.sel&&UI.sel.kind==='sched'){ var sc=sch(UI.sel.n); if(sc) loadThumbs(sc.slideIds); }
  loadThumbs(S.pending.concat(S.attention).map(function(x){return x.slideIds[0];}).concat(S.scheduled.map(function(x){return x.slideIds[orderOf(x)[0]-1];})).filter(Boolean));
  wireRail();
}
function footText(){ return 'review build '+esc(S.build)+' · drop is free · reroll regenerates the whole post at $'+S.cost.toFixed(2)+' a slide · approved posts publish themselves'; }
function thumbImg(id){ var t=id&&THUMB[id]; return (t&&t.status==='ok')?'<img src="'+t.data+'" alt="">':''; }

function renderMain(){
  if(!UI.sel){ if(!S.pending.length) return emptyMain(); UI.sel={kind:'post',n:S.pending[0].n}; }
  if(UI.sel.kind==='att'){ var a=att(UI.sel.n); if(!a){UI.sel=null;return renderMain();} return renderFailed(a); }
  if(UI.sel.kind==='regen'){ var rg=regenOf(UI.sel.n); if(!rg){UI.sel=null;return renderMain();} var waiting=rg.img!=='Processing';
    return '<div class="phead"><button class="back" data-act="back">‹</button><div><div class="ptitle">'+esc(rg.title)+'</div><div class="pmeta">row '+rg.n+' · reroll asked for slide '+rg.slide+' · attempt '+rg.attempt+' of '+rg.max+(rg.since?' · since '+esc(rg.since):'')+'</div></div>'+(waiting?'<div class="pacts"><button class="btn ghost" data-act="unreroll" data-n="'+rg.n+'">Withdraw reroll · keep current images</button></div>':'')+'</div>'+
      '<div class="regenpane"><span class="spin" style="width:26px;height:26px"></span><div class="h">'+(waiting?'Waiting for the Mac to pick this up.':'The Mac is regenerating this post now.')+'</div><div class="p">A reroll regenerates every slide of the post and re-runs the caption — generate.py has no single-slide mode. The row returns to Waiting on you when the new images land.'+(waiting?' If it has been sitting here for more than a few minutes, the Mac or the tunnel was down when it was sent — withdraw it and reroll again, or just drop the slide.':'')+'</div></div>'; }
  if(UI.sel.kind==='sched'){ var sc=sch(UI.sel.n); if(!sc){UI.sel=null;return renderMain();} return renderScheduled(sc); }
  var p=post(UI.sel.n); if(!p){ UI.sel=null; return S.pending.length?renderMain():emptyMain(); }
  return renderPost(p);
}
function renderScheduled(s){ var edu=(s.lane==='edu'); var order=orderOf(s);
  var h='<div class="phead"><button class="back" data-act="back">‹</button><div style="min-width:0"><div class="ptitle">'+esc(s.title)+'</div><div class="pmeta">'+(edu?'EDUCATIONAL':'AI carousel')+' · row '+s.num+' · '+s.status+' · '+(s.when?'posts '+fmtShort(s.when)+' 21:00 NY':'takes the next free Thursday 21:00 NY')+' · '+order.length+' slide'+(order.length===1?'':'s')+'</div></div>';
  h+='<div class="pacts">'+(edu?'<button class="btn soft" data-act="cancel" data-n="'+s.n+'">Unapprove · back to review</button>':'<button class="btn ghost" data-act="resched" data-n="'+s.n+'">Reschedule</button><button class="btn soft" data-act="cancel" data-n="'+s.n+'">Cancel · back to review</button>')+'</div></div>';
  h+='<div class="rolab"><span class="lab">slides in publish order · read-only · click to enlarge</span><span></span></div><div class="rail ro" id="rail">';
  order.forEach(function(i,pos){ var id=s.slideIds[i-1]; if(!id) return; h+='<figure class="slide'+(pos===0?' cover':'')+'" data-i="'+i+'"><div class="shot stripe zoom" data-act="zoom" data-kind="sched" data-n="'+s.n+'" data-i="'+i+'"><span class="badge">slide '+i+(pos===0?' · cover':'')+'</span>'+thumbBody(id,i)+'</div></figure>'; });
  h+='</div><div class="dots" id="dots"></div><div class="capwrap"><div class="caplab"><span class="lab">caption · read-only</span><span class="h">'+(edu?'unapprove to edit':'cancel to edit')+'</span></div><div class="rocap">'+esc(s.caption)+'</div><div class="foot">'+footText()+'</div></div>';
  return h; }
function emptyMain(){ return '<div class="phead" style="display:none"></div><div class="mainempty"><div class="h">Nothing waiting on you.</div><div class="p">Posts appear here once images and caption have both finished. A row stuck on ERROR never reaches this screen — check the Generation Status tab.</div></div><div class="foot">'+footText()+'</div>'; }

function renderPost(p){ var isEdu=(p.lane==='edu'); var o=ord(p), k=kept(p), idx=calIndex(); var d=dateFor(p.n); var onDay=(idx[d]||[]).length;
  var coverNum=k.length?k[0]:null; var coverMoved=k.length&&coverNum!==1;
  var kind=(k.length>=2?'carousel of '+k.length:(k.length===1?'single image':'nothing kept'));
  var meta=(isEdu?'EDUCATIONAL':'AI carousel')+' · row '+p.num+' · '+p.slideIds.length+(isEdu?' rendered':' generated')+' · '+(o.length-k.length)+' dropped · '+kind+(isEdu?' · books its own Thursday':'');
  var h='<div class="phead"><button class="back" data-act="back">‹</button><div style="min-width:0"><div class="ptitle">'+esc(p.title)+'</div><div class="pmeta">'+meta+'</div></div>';
  h+='<div class="pacts">'+(isEdu?'':'<div class="datecol"><button class="btn ghost" data-act="date" data-n="'+p.n+'"><svg width="15" height="15" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"><rect x="1.6" y="3.2" width="12.8" height="11.2" rx="1.6"></rect><path d="M1.6 6.6h12.8"></path><path d="M5 1.6v3"></path><path d="M11 1.6v3"></path></svg>'+fmtShort(d)+'</button>'+(onDay?'<div class="datenote">'+onDay+' post'+(onDay===1?'':'s')+' already on '+fmtShort(d)+'</div>':'')+'</div>');
  var canApprove=isEdu?k.length>=2:k.length>0;
  h+='<button class="btn approve" data-act="approve" data-n="'+p.n+'"'+(canApprove?'':' disabled')+'>'+(canApprove?'Approve '+k.length+' slide'+(k.length===1?' (single image)':'s'):(isEdu&&k.length===1?'Keep at least 2 slides':'Nothing left to post'))+'</button>';
  h+='<button class="btn dangerline" data-act="rejectopen" data-n="'+p.n+'">Reject</button></div></div>';
  h+='<div class="rejectbox'+(REJ[p.n]?' on':'')+'"><div class="lab red">why?</div><input type="text" id="why" placeholder="A few words — this is what trains the rubric" maxlength="200"><div class="hint" id="whyhint"></div><div class="row"><button class="btn danger" data-act="rejectgo" data-n="'+p.n+'">Confirm reject</button><button class="btn soft" data-act="rejectcancel" data-n="'+p.n+'">Cancel</button></div></div>';
  if(isEdu){ h+='<div class="rerollbox'+(RRL[p.n]?' on':'')+'"><div class="lab">reroll slide '+(RRL[p.n]||'')+' — what do you want different?</div><input type="text" id="rrlwhy" placeholder="e.g. warmer, show the lamp on the nightstand" maxlength="200"><div class="hint" id="rrlhint">your comment is the instruction the new image is generated from</div><div class="row"><button class="btn" data-act="edrrlgo" data-n="'+p.n+'">Request reroll</button><button class="btn soft" data-act="edrrlcancel" data-n="'+p.n+'">Cancel</button></div></div>'; }
  h+='<div class="orderwrap"><div class="orderrow"><span class="lab">final order · '+(MOBILE.matches?'use ◀ ▶ to move a slide':'drag to reorder, or use ◀ ▶')+(isEdu?' · cover stays first (its title is baked in — reroll it instead)':'')+'</span><div class="order" id="order">';
  o.forEach(function(i,pos){ if(dropped(p.n,i)) return; var isCover=(i===coverNum); h+='<div class="oth'+(isCover?' cover':'')+'" draggable="'+((isEdu&&i===1)?'false':'true')+'" data-i="'+i+'"><div class="box stripe">'+thumbImg(p.slideIds[i-1])+'<span class="n">'+i+'</span></div><span class="cl">cover</span></div>'; });
  h+='</div></div><div class="coverwarn'+(coverMoved?' on':'')+'">Slide '+coverNum+' is now your cover / grid thumbnail.</div></div>';
  h+='<div class="rail" id="rail">';
  o.forEach(function(i){ var id=p.slideIds[i-1]; var isCover=(i===coverNum); var dr=dropped(p.n,i); var menuOn=UI.menu&&UI.menu.n===p.n&&UI.menu.i===i; var pos=o.indexOf(i); var lockCover=(isEdu&&i===1);
    h+='<figure class="slide'+(isCover?' cover':'')+(dr?' dropped':'')+'" data-i="'+i+'"><div class="shot stripe zoom" data-act="zoom" data-kind="post" data-n="'+p.n+'" data-i="'+i+'"><span class="badge">slide '+i+(isCover?' · cover':'')+'</span>'+thumbBody(id,i)+'<div class="dropflag">DROPPED</div></div>';
    h+='<div class="sbar"><button class="mv" data-act="moveL" data-n="'+p.n+'" data-i="'+i+'" title="Move earlier"'+(!canMove(p,i,-1)?' disabled':'')+'>◀</button>';
    h+='<button class="drop" data-act="drop" data-n="'+p.n+'" data-i="'+i+'"'+(lockCover?' disabled title="the cover carries the title — reroll it instead"':'')+'>'+(dr?'Undo drop':(lockCover?'Cover · fixed':'Drop'))+'</button>';
    h+='<button class="mv" data-act="moveR" data-n="'+p.n+'" data-i="'+i+'" title="Move later"'+(!canMove(p,i,1)?' disabled':'')+'>▶</button>';
    h+='<button class="more'+(menuOn?' on':'')+'" data-act="menu" data-n="'+p.n+'" data-i="'+i+'">···</button></div>';
    if(menuOn&&!MOBILE.matches) h+=menuHtml(p,i);
    h+='</figure>'; });
  h+='</div><div class="dots" id="dots"></div>';
  h+='<div class="capwrap"><div class="caplab"><span class="lab">caption</span><span class="h">edit inline · saves with Approve</span></div><textarea class="cap" id="cap" data-n="'+p.n+'" rows="6" spellcheck="true">'+esc(capFor(p))+'</textarea>';
  if(p.qaNotes.length){ h+='<div class="qa'+(QA[p.n]?' on':'')+'"><div class="tg" data-act="qa" data-n="'+p.n+'">Caption QA · '+p.qaNotes.length+' note'+(p.qaNotes.length===1?'':'s')+' '+(QA[p.n]?'▴':'▾')+'</div><ul>'+p.qaNotes.map(function(q){return '<li>'+esc(q)+'</li>';}).join('')+'</ul><div class="note">notes stay until the QA agent re-runs — editing the caption does not clear them</div></div>'; }
  h+='<div class="foot">'+footText()+'</div></div>';
  return h; }

function thumbBody(id,i){ var t=THUMB[id]; if(t&&t.status==='ok') return '<img src="'+t.data+'" alt="slide '+i+'">';
  if(t&&t.status==='err') return '<div class="ph"><span class="t b">slide did not load</span><span class="e">'+esc(t.err)+'</span><a data-act="rethumb" data-id="'+esc(id)+'">retry</a></div>';
  return '<div class="ph"><span class="spin"></span><span class="t">slide '+i+' · loading…</span></div>'; }

/* v2.5 — can slide i move one step in dir (-1 earlier / +1 later)? Edu keeps
 * the cover (slide 1) pinned at position 0, so nothing moves into or out of it. */
function moveTarget(p,i,dir){ var o=ord(p); var at=o.indexOf(i); if(at<0||dropped(p.n,i)) return -1; if(isEdu(p)&&i===1) return -1;
  for(var j=at+dir;j>=0&&j<o.length;j+=dir){ if(dropped(p.n,o[j])) continue; if(isEdu(p)&&o[j]===1) return -1; return j; } return -1; }
function canMove(p,i,dir){ return moveTarget(p,i,dir)>=0; }
function doMove(p,i,dir){ var to=moveTarget(p,i,dir); if(to<0) return false; var o=ord(p); var at=o.indexOf(i); o.splice(at,1); o.splice(to,0,i); return true; }
function menuItems(p,i){ var done=p.rerolls[String(i)]||0; var k=kept(p); var isCover=k.length&&k[0]===i; var dr=dropped(p.n,i); var n=p.slideIds.length;
  if(isEdu(p)) return [
    {act:'edrrlopen',t:'Reroll this slide',s:'say what you want different',off:false},
    {act:'zoom',t:'Enlarge',s:'',off:false},
    {act:'drive',t:'Open in Drive ↗',s:'',off:false}
  ];
  return [
    {act:'reroll',t:'Reroll · regenerates all '+n+' slides ($'+(S.cost*n).toFixed(2)+')',s:done>=S.maxRerolls?'reroll limit reached':'attempt '+(done+1)+' of '+S.maxRerolls+' · caption re-runs too',off:done>=S.maxRerolls},
    {act:'moveL',t:'Move earlier',s:'',off:!canMove(p,i,-1)},
    {act:'moveR',t:'Move later',s:'',off:!canMove(p,i,1)},
    {act:'cover',t:'Make cover',s:isCover?'already the cover':(dr?'undo drop first':''),off:isCover||dr},
    {act:'zoom',t:'Enlarge',s:'',off:false},
    {act:'drive',t:'Open in Drive ↗',s:'',off:false}
  ]; }

/* ── v2.5 lightbox ── */
function zoomList(kind,n){ var x=null, ids=[], labels=[];
  if(kind==='post'){ x=post(n); if(x) ord(x).forEach(function(i){ if(dropped(x.n,i)) return; ids.push(x.slideIds[i-1]); labels.push('slide '+i); }); }
  else if(kind==='att'){ x=att(n); if(x) orderOf(x).forEach(function(i){ ids.push(x.slideIds[i-1]); labels.push('slide '+i); }); }
  else if(kind==='sched'){ x=sch(n); if(x) orderOf(x).forEach(function(i){ ids.push(x.slideIds[i-1]); labels.push('slide '+i); }); }
  else if(kind==='cal'){ S.calendar.forEach(function(it){ if(it.lane+'-'+it.n!==n) return; x=it; orderOf(it).forEach(function(i){ ids.push(it.slideIds[i-1]); labels.push('slide '+i); }); }); }
  return {x:x, ids:ids, labels:labels, title:x?x.title:''}; }
function openZoom(kind,n,i){ var z=zoomList(kind,n); if(!z.ids.length) return; var at=0; if(kind==='post'||kind==='att'||kind==='sched'||kind==='cal'){ var x=z.x; var id=x&&x.slideIds[i-1]; at=Math.max(0,z.ids.indexOf(id)); }
  LB={ids:z.ids,labels:z.labels,i:at,title:z.title}; loadThumbs(z.ids); renderZoom(); }
function renderZoom(){ var w=document.getElementById('lb'); if(!LB){ w.hidden=true; w.innerHTML=''; return; } var id=LB.ids[LB.i]; var t=THUMB[id];
  var body=(t&&t.status==='ok')?'<img src="'+t.data+'" alt="">':(t&&t.status==='err'?'<div class="lbmsg">slide did not load · '+esc(t.err)+'</div>':'<div class="lbmsg"><span class="spin"></span> loading…</div>');
  w.innerHTML='<div class="lbscrim" data-lb="close"></div><div class="lbbox"><div class="lbhead"><div class="lbt">'+esc(LB.title)+'</div><div class="lbm">'+esc(LB.labels[LB.i])+' · '+(LB.i+1)+' of '+LB.ids.length+' · preview at 900px</div><a class="btn ghost small" href="https://drive.google.com/file/d/'+esc(id)+'/view" target="_blank" rel="noopener">full file in Drive ↗</a><button class="lbx" data-lb="close" title="close">×</button></div>'+
    '<div class="lbimg">'+(LB.ids.length>1?'<button class="lbnav l" data-lb="prev">‹</button>':'')+body+(LB.ids.length>1?'<button class="lbnav r" data-lb="next">›</button>':'')+'</div></div>';
  w.hidden=false; }
function zoomStep(d){ if(!LB) return; LB.i=(LB.i+d+LB.ids.length)%LB.ids.length; renderZoom(); }
function menuHtml(p,i){ return '<div class="menu">'+menuItems(p,i).map(function(m){return '<div class="mi'+(m.off?' off':'')+'" data-act="'+(m.off?'':m.act)+'" data-n="'+p.n+'" data-i="'+i+'"><b>'+esc(m.t)+'</b>'+(m.s?'<small>'+esc(m.s)+'</small>':'')+'</div>';}).join('')+'</div>'; }

function renderFailed(a){ var h='<div class="phead"><button class="back" data-act="back">‹</button><div style="min-width:0"><div class="ptitle">'+esc(a.title)+'</div><div class="pmeta">row '+a.n+' · slides '+esc(a.slides)+(a.when?' · was '+fmtShort(a.when)+' 21:00 NY':'')+'</div></div>';
  h+='<div class="pacts"><button class="btn danger approve" data-act="retry" data-n="'+a.n+'">Retry now</button><button class="btn ghost" data-act="resched" data-n="'+a.n+'">Reschedule</button><button class="btn soft" data-act="cancel" data-n="'+a.n+'">Cancel</button></div></div>';
  h+='<div class="failbanner"><div class="r">'+esc(a.reason)+'</div><div class="p">Nothing was posted. Retry sends the same slides again; reschedule moves it to another evening.</div>'+(a.remark?'<div class="raw">last system remark · '+esc(a.remark)+'</div>':'')+'</div>';
  h+='<div class="rolab"><span class="lab">slides · read-only</span><span></span></div><div class="rail ro" id="rail">';
  var order=String(a.slides||'').split(',').map(function(x){return Number(x);}).filter(function(x){return x>0;}); if(!order.length) order=a.slideIds.map(function(_,i){return i+1;});
  order.forEach(function(i,pos){ var id=a.slideIds[i-1]; if(!id) return; h+='<figure class="slide'+(pos===0?' cover':'')+'" data-i="'+i+'"><div class="shot stripe zoom" data-act="zoom" data-kind="att" data-n="'+a.n+'" data-i="'+i+'"><span class="badge">slide '+i+(pos===0?' · cover':'')+'</span>'+thumbBody(id,i)+'</div></figure>'; });
  h+='</div><div class="dots" id="dots"></div><div class="capwrap"><div class="caplab"><span class="lab">caption · read-only</span></div><div class="rocap">'+esc(a.caption)+'</div><div class="foot">'+footText()+'</div></div>';
  return h; }

/* ── thumbnails: lazy, two in flight ── */
var TQ=[], TACTIVE=0;
function loadThumbs(ids){ ids.forEach(function(id){ if(!id||THUMB[id]) return; THUMB[id]={status:'loading'}; TQ.push(id); }); pumpThumbs(); }
function pumpThumbs(){ while(TACTIVE<2&&TQ.length){ (function(id){ TACTIVE++; google.script.run.withSuccessHandler(function(r){ TACTIVE--; if(r&&r.indexOf('data:')===0) THUMB[id]={status:'ok',data:r}; else THUMB[id]={status:'err',err:String(r||'empty response').replace(/^ERR:/,'')}; patchThumb(id); pumpThumbs(); }).withFailureHandler(function(e){ TACTIVE--; THUMB[id]={status:'err',err:String(e&&e.message||e)}; patchThumb(id); pumpThumbs(); }).reviewThumb(id); })(TQ.shift()); } }
function patchThumb(id){ // cheap: re-render only if this id is on screen
  if(LB&&LB.ids.indexOf(id)>-1) renderZoom();
  if(DAYOPEN){ var items=calIndex()[DAYOPEN]||[]; if(items.some(function(it){return (it.slideIds||[]).indexOf(id)>-1;})) daySheet(DAYOPEN); }
  var cur=UI.sel&&(UI.sel.kind==='post'?post(UI.sel.n):(UI.sel.kind==='att'?att(UI.sel.n):(UI.sel.kind==='sched'?sch(UI.sel.n):null)));
  var onScreen=cur&&cur.slideIds.indexOf(id)>-1; var isFirst=S.pending.concat(S.attention).concat(S.scheduled).some(function(x){return x.slideIds[0]===id||x.slideIds[orderOf(x)[0]-1]===id;});
  if(onScreen||isFirst) render(); }

/* ── mobile carousel dots ── */
function wireRail(){ var rail=document.getElementById('rail'); var dots=document.getElementById('dots'); if(!rail||!dots) return; var slides=rail.querySelectorAll('.slide'); if(!slides.length){dots.innerHTML='';return;}
  function upd(){ var w=rail.clientWidth||1; var i=Math.min(slides.length-1,Math.max(0,Math.round(rail.scrollLeft/w))); var h=''; for(var k=0;k<slides.length;k++) h+='<i class="'+(k===i?'on':'')+'"></i>'; dots.innerHTML=h+'<span>slide '+slides[i].getAttribute('data-i')+' · '+slides.length+'</span>'; }
  rail.addEventListener('scroll',upd,{passive:true}); upd(); }

/* ── sheets ── */
function openSheet(html){ var w=document.getElementById('sheetwrap'); DAYOPEN=null; document.getElementById('sheet').innerHTML='<div class="grab"></div>'+html; w.hidden=false; }
function closeSheet(){ document.getElementById('sheetwrap').hidden=true; DAYOPEN=null; }
function pickerSheet(opts){ var idx=calIndex(); var mk=opts.month||opts.sel.slice(0,7); var onDay=(idx[opts.sel]||[]).length;
  openSheet('<div class="h">'+esc(opts.title||'Post on')+'</div><div class="pick" id="pick" data-sel="'+opts.sel+'" data-month="'+mk+'">'+renderMonth(mk,idx,{sel:opts.sel,nav:'pickmonth',dayAct:'pickday',sub:'posts at 21:00 New York'})+'</div><div class="picknote" id="picknote">'+(onDay?onDay+' post'+(onDay===1?'':'s')+' already on '+fmtShort(opts.sel)+' — that\\'s fine.':'')+'</div><button class="btn full" data-act="pickuse" data-n="'+opts.n+'" data-mode="'+opts.mode+'">Use '+fmtShort(opts.sel)+'</button><button class="btn soft full" data-close="1">Cancel</button>');
}
function daySheet(date){ var items=calIndex()[date]||[]; DAYOPEN=date; var h='<div style="display:flex;align-items:baseline;justify-content:space-between"><span class="h">'+fmtLong(date)+'</span><span class="s">'+items.length+' post'+(items.length===1?'':'s')+'</span></div>';
  if(!items.length) h+='<div class="p">Nothing on this day.</div>';
  var want=[];
  h+='<div class="list">'+items.map(function(it){ var m=it.status==='pub'?'published':(it.status==='fail'?'publish failed':'scheduled'); var acts=''; var key=it.lane+'-'+it.n;
    var schedId=(it.lane==='edu'?'ED-':'')+it.n; var open=(it.status==='sched'&&sch(schedId))?'<button class="btn ghost small" data-act="selsched" data-n="'+schedId+'">Open</button>':'';
    if(it.lane==='ai'){ if(it.status==='sched') acts=open+'<button class="btn soft small" data-act="cancel" data-n="'+it.n+'">Cancel</button>'; if(it.status==='fail') acts='<button class="btn danger small" data-act="retry" data-n="'+it.n+'">Retry now</button><button class="btn ghost small" data-act="resched" data-n="'+it.n+'">Reschedule</button><button class="btn soft small" data-act="cancel" data-n="'+it.n+'">Cancel</button>'; }
    if(it.lane==='edu'&&it.status==='sched') acts=open+'<button class="btn soft small" data-act="cancel" data-n="ED-'+it.n+'">Unapprove</button>';
    if(it.url) acts+='<a class="btn ghost small" href="'+esc(it.url)+'" target="_blank" rel="noopener">open on Instagram ↗</a>';
    if(it.lane==='reel'&&it.status!=='pub') acts+='<span class="s" style="align-self:center">managed in the reel lane</span>';
    var strip=''; var ord2=orderOf(it); if((it.slideIds||[]).length){ strip='<div class="daystrip">'+ord2.map(function(i){ var id=it.slideIds[i-1]; want.push(id); var t=THUMB[id]; return '<div class="dth stripe" data-act="zoom" data-kind="cal" data-n="'+key+'" data-i="'+i+'" title="slide '+i+'">'+((t&&t.status==='ok')?'<img src="'+t.data+'" alt="">':'<span class="n">'+i+'</span>')+'</div>'; }).join('')+'</div>'; }
    return '<div class="dayitem"><span class="tag big '+it.type+'">'+it.type+'</span><div style="flex:1;min-width:0"><div class="t">'+esc(it.title)+'</div><div class="m '+it.status+'">'+(it.n?'row '+esc(it.n)+' · ':'')+m+(it.time?' · '+esc(it.time):'')+(ord2.length&&(it.slideIds||[]).length?' · '+ord2.length+' slide'+(ord2.length===1?'':'s'):'')+'</div>'+strip+'<div class="acts">'+acts+'</div></div></div>'; }).join('')+'</div>';
  h+='<div class="note">Every day is selectable when approving; the bold columns are only a nudge toward Tue / Thu / Sat. Several posts on one day are allowed. Tap a slide to enlarge it.</div><button class="btn soft full" data-close="1">Close</button>';
  openSheet(h); DAYOPEN=date; loadThumbs(want.filter(Boolean)); }
function menuSheet(p,i){ openSheet('<div class="h">Slide '+i+'</div><div class="s">row '+p.n+(kept(p)[0]===i?' · currently the cover':'')+'</div><div class="list">'+menuItems(p,i).map(function(m){return '<div class="li'+(m.off?' off':'')+'" data-act="'+(m.off?'':m.act)+'" data-n="'+p.n+'" data-i="'+i+'"><div><b>'+esc(m.t)+'</b>'+(m.s?'<small>'+esc(m.s)+'</small>':'')+'</div><span class="ch">'+(m.off?'':'›')+'</span></div>';}).join('')+'</div><button class="btn soft full" data-close="1">Cancel</button>'); }
function confirmSheet(title,p,att2,okLabel,okAct,n,i,danger){ openSheet('<div class="h">'+esc(title)+'</div><div class="p">'+esc(p)+'</div>'+(att2?'<div class="att">'+esc(att2)+'</div>':'')+'<div class="row"><button class="btn'+(danger?' danger':'')+'" data-act="'+okAct+'" data-n="'+n+'" data-i="'+(i||'')+'">'+esc(okLabel)+'</button><button class="btn soft" data-close="1">Cancel</button></div>'); }

/* ── state refresh after a write ── */
function refresh(after){ google.script.run.withSuccessHandler(function(st){ S=st; S.scheduled=S.scheduled||[]; if(after) after(); render(); }).withFailureHandler(function(){ render(); }).reviewState(); }
function removePending(n){ S.pending=S.pending.filter(function(p){return p.n!==n;}); if(UI.sel&&UI.sel.n===n) UI.sel=null; }
function selectNext(){ UI.sel=S.pending.length?{kind:'post',n:S.pending[0].n}:null; if(MOBILE.matches) UI.view=UI.sel?'post':'queue'; }

/* ── events ── */
document.addEventListener('click',function(e){
  var lb=e.target.closest('[data-lb]'); if(lb){ var la=lb.getAttribute('data-lb'); if(la==='close'){ LB=null; renderZoom(); } else zoomStep(la==='prev'?-1:1); return; }
  if(e.target.closest('[data-close]')){ closeSheet(); return; }
  var el=e.target.closest('[data-act]'); if(!el) return; var act=el.getAttribute('data-act'); var n=el.getAttribute('data-n'); var i=Number(el.getAttribute('data-i')||0);
  if(!act) return; if(UI.busy&&act!=='tab') return;
  if(act==='tab'){ UI.view=el.getAttribute('data-v'); render(); return; }
  if(act==='back'){ UI.view='queue'; UI.sel=null; render(); return; }
  if(act==='sel'){ var kind=el.getAttribute('data-kind'); UI.sel={kind:kind,n:n}; UI.menu=null; if(MOBILE.matches) UI.view='post'; render(); return; }
  if(act==='selsched'){ closeSheet(); UI.sel={kind:'sched',n:n}; UI.menu=null; if(MOBILE.matches) UI.view='post'; render(); return; }
  if(act==='zoom'){ var zk=el.getAttribute('data-kind')||'post'; UI.menu=null; if(el.classList.contains('mi')||el.classList.contains('li')) closeSheet(); openZoom(zk,n,i); return; }
  if(act==='unreroll'){ run('reviewUnreroll',n,null,function(r){ if(!r.ok){toast(r.error,true);return;} toast('Reroll withdrawn — back in the queue with its current images'); UI.sel=null; refresh(); }); return; }
  if(act==='month'){ UI.month=shiftMonth(UI.month,Number(el.getAttribute('data-d'))); render(); return; }
  if(act==='day'){ daySheet(el.getAttribute('data-date')); return; }
  if(act==='pickmonth'){ var pk=document.getElementById('pick'); var nm=shiftMonth(pk.getAttribute('data-month'),Number(el.getAttribute('data-d'))); pk.setAttribute('data-month',nm); pk.innerHTML=renderMonth(nm,calIndex(),{sel:pk.getAttribute('data-sel'),nav:'pickmonth',dayAct:'pickday',sub:'posts at 21:00 New York'}); return; }
  if(act==='pickday'){ var pk2=document.getElementById('pick'); var d=el.getAttribute('data-date'); pk2.setAttribute('data-sel',d); pk2.innerHTML=renderMonth(pk2.getAttribute('data-month'),calIndex(),{sel:d,nav:'pickmonth',dayAct:'pickday',sub:'posts at 21:00 New York'}); var c=(calIndex()[d]||[]).length; document.getElementById('picknote').textContent=c?c+' post'+(c===1?'':'s')+' already on '+fmtShort(d)+' — that\\'s fine.':''; var ub=document.querySelector('[data-act="pickuse"]'); if(ub) ub.textContent='Use '+fmtShort(d); return; }
  if(act==='date'){ pickerSheet({n:n,sel:dateFor(n),mode:'approve',title:'Post on'}); return; }
  if(act==='resched'){ closeSheet(); var a0=att(n); pickerSheet({n:n,sel:(a0&&a0.when)||S.defaultDate,mode:'resched',title:'Reschedule'}); return; }
  if(act==='pickuse'){ var sel=document.getElementById('pick').getAttribute('data-sel'); var mode=el.getAttribute('data-mode'); closeSheet();
    if(mode==='approve'){ DATE[n]=sel; render(); return; }
    run('reviewReschedule',n,sel,null,function(r){ if(!r.ok){toast(r.error,true);return;} toast('Rescheduled to '+fmtShort(sel)); UI.sel=null; refresh(); }); return; }
  if(act==='drop'){ var pd=post(n); if(pd&&isEdu(pd)&&i===1) return; DROP[n]=DROP[n]||{}; if(DROP[n][i]) delete DROP[n][i]; else DROP[n][i]=true; UI.menu=null; render(); return; }
  if(act==='menu'){ var p=post(n); if(!p) return; if(MOBILE.matches){ menuSheet(p,i); return; } UI.menu=(UI.menu&&UI.menu.n===n&&UI.menu.i===i)?null:{n:n,i:i}; render(); return; }
  if(act==='moveL'||act==='moveR'){ var p2=post(n); if(!p2||!doMove(p2,i,act==='moveL'?-1:1)) return; UI.menu=null; closeSheet(); render(); return; }
  if(act==='cover'){ var p3=post(n); if(isEdu(p3)) return; var o3=ord(p3); var at3=o3.indexOf(i); o3.splice(at3,1); o3.unshift(i); UI.menu=null; closeSheet(); render(); return; }
  if(act==='drive'){ var p4=post(n); var id=p4&&p4.slideIds[i-1]; UI.menu=null; closeSheet(); if(!id) return; window.open('https://drive.google.com/file/d/'+id+'/view','_blank'); return; }
  if(act==='reroll'){ var p5=post(n); var done=(p5.rerolls[String(i)]||0); var cnt=p5.slideIds.length; UI.menu=null; confirmSheet('Reroll slide '+i+'?','The Mac regenerates ALL '+cnt+' slides of this post ($'+(S.cost*cnt).toFixed(2)+') and re-runs the caption — there is no single-slide mode. Your drops and caption edits here are lost. This post leaves the queue until it finishes (a few minutes).','attempt '+(done+1)+' of '+S.maxRerolls+' · Drop is free — prefer it if the rest of the post is fine','Reroll · $'+(S.cost*cnt).toFixed(2),'rerollgo',n,i,false); return; }
  if(act==='rerollgo'){ closeSheet(); var p6=post(n); run('reviewReroll',n,i,null,function(r){ if(!r.ok){toast(r.error,true);return;} toast('Sent to the Mac — regenerating the post'); removePending(n); S.regen.push({n:n,title:p6.title,slide:i,attempt:r.attempt,max:r.max,img:'Ready',since:''}); UI.sel={kind:'regen',n:n}; if(MOBILE.matches) UI.view='queue'; render(); setTimeout(function(){refresh();},2500); }); return; }
  if(act==='edrrlopen'){ closeSheet(); UI.menu=null; RRL[n]=i; REJ[n]=false; render(); var rw=document.getElementById('rrlwhy'); if(rw) rw.focus(); return; }
  if(act==='edrrlcancel'){ RRL[n]=null; render(); return; }
  if(act==='edrrlgo'){ var ri=RRL[n]; var rwhy=(document.getElementById('rrlwhy').value||'').trim();
    if(!rwhy){ document.getElementById('rrlhint').textContent='Say what you want different — that comment is the instruction'; return; }
    run('reviewReroll',n,ri,rwhy,null,function(r){ if(!r.ok){toast(r.error,true);return;}
      toast('Reroll queued for slide '+ri+' — that lane regenerates within ~16 minutes');
      RRL[n]=null; render(); refresh(); }); return; }
  if(act==='rejectopen'){ REJ[n]=true; RRL[n]=null; render(); var w=document.getElementById('why'); if(w) w.focus(); return; }
  if(act==='rejectcancel'){ REJ[n]=false; render(); return; }
  if(act==='rejectgo'){ var why=(document.getElementById('why').value||'').trim(); if(!why){ document.getElementById('whyhint').textContent='A reason is required — one line is enough'; return; }
    run('reviewReject',n,why,null,function(r){ if(!r.ok){toast(r.error,true);return;} toast('Rejected — reason saved to the row',true); REJ[n]=false; removePending(n); selectNext(); render(); refresh(); }); return; }
  if(act==='approve'){ var pa=post(n); var k=kept(pa); if(!k.length||(isEdu(pa)&&k.length<2)) return; var capv=document.getElementById('cap').value; var when=dateFor(n);
    run('reviewApprove',n,k,capv,when,null,function(r){ if(!r.ok){toast(r.error,true);return;} var kk=(r.kept||k);
      if(r.lane==='edu'){ toast('Approved — '+kk.length+' slides, takes the next free Thursday 21:00 NY'); S.scheduled.push({n:n,lane:'edu',num:pa.num,title:pa.title,when:'',status:'Approved',slides:kk.join(','),slideIds:pa.slideIds,caption:capv}); }
      else { toast('Approved — '+kk.length+' slide'+(kk.length===1?'':'s')+', '+r.kind+', posts '+fmtShort(r.when)+' 21:00 NY'); S.calendar.push({type:'AI',lane:'ai',n:n,title:pa.title,date:r.when,time:'21:00 NY',status:'sched',url:'',slides:kk.join(','),slideIds:pa.slideIds}); S.scheduled.push({n:n,lane:'ai',num:pa.num,title:pa.title,when:r.when,status:'Scheduled',slides:kk.join(','),slideIds:pa.slideIds,caption:capv}); }
      removePending(n); selectNext(); render(); refresh(); }); return; }
  if(act==='retry'){ closeSheet(); run('reviewRetry',n,null,function(r){ if(!r.ok){toast(r.error,true);return;} toast('Back in the queue — next sweep picks it up'); S.attention=S.attention.filter(function(a){return a.n!==n;}); if(UI.sel&&UI.sel.n===n) UI.sel=null; render(); refresh(); }); return; }
  if(act==='cancel'){ closeSheet(); var edc=String(n).indexOf('ED-')===0; confirmSheet(edc?'Unapprove educational #'+String(n).slice(3)+'?':'Cancel post #'+n+'?',edc?'It goes back to Waiting on you as Review; its Thursday slot is released.':'It goes back to the review feed with no date.','',edc?'Unapprove':'Cancel the post','cancelgo',n,0,true); return; }
  if(act==='cancelgo'){ closeSheet(); run('reviewCancel',n,null,function(r){ if(!r.ok){toast(r.error,true);return;} toast(String(n).indexOf('ED-')===0?'Unapproved — it is back in Waiting on you':'Cancelled — it is back in the review feed'); if(UI.sel&&UI.sel.n===n) UI.sel=null; refresh(); }); return; }
  if(act==='qa'){ QA[n]=!QA[n]; render(); return; }
  if(act==='rethumb'){ var rid=el.getAttribute('data-id'); delete THUMB[rid]; loadThumbs([rid]); render(); return; }
});
document.addEventListener('input',function(e){ if(e.target&&e.target.id==='cap') CAP[e.target.getAttribute('data-n')]=e.target.value; if(e.target&&e.target.id==='why') document.getElementById('whyhint').textContent=''; });
document.addEventListener('keydown',function(e){ if(LB){ if(e.key==='Escape'){ LB=null; renderZoom(); } else if(e.key==='ArrowLeft') zoomStep(-1); else if(e.key==='ArrowRight') zoomStep(1); return; } if(e.key==='Escape'){ closeSheet(); if(UI.menu){UI.menu=null;render();} } });
// close a desktop menu on outside click
document.addEventListener('click',function(e){ if(UI.menu&&!e.target.closest('.menu')&&!e.target.closest('[data-act="menu"]')){ UI.menu=null; render(); } },true);
// desktop drag-to-reorder on the final-order strip
document.addEventListener('dragstart',function(e){ var t=e.target.closest&&e.target.closest('.oth'); if(!t) return; e.dataTransfer.setData('text/plain',t.getAttribute('data-i')); e.dataTransfer.effectAllowed='move'; });
document.addEventListener('dragover',function(e){ var t=e.target.closest&&e.target.closest('.oth'); if(!t) return; e.preventDefault(); t.classList.add('dragover'); });
document.addEventListener('dragleave',function(e){ var t=e.target.closest&&e.target.closest('.oth'); if(t) t.classList.remove('dragover'); });
document.addEventListener('drop',function(e){ var t=e.target.closest&&e.target.closest('.oth'); if(!t||!UI.sel||UI.sel.kind!=='post') return; e.preventDefault(); var from=Number(e.dataTransfer.getData('text/plain')), to=Number(t.getAttribute('data-i')); if(!from||!to||from===to) return; var pp=post(UI.sel.n); if(isEdu(pp)&&(from===1||to===1)){ toast('The educational cover stays first — reroll it instead',true); return; } var o=ord(pp); var a=o.indexOf(from), b=o.indexOf(to); o.splice(a,1); o.splice(b,0,from); render(); });
var LASTM=MOBILE.matches; if(MOBILE.addEventListener) MOBILE.addEventListener('change',function(){ if(MOBILE.matches===LASTM) return; LASTM=MOBILE.matches; UI.menu=null; if(!MOBILE.matches&&UI.view==='cal') UI.view='queue'; render(); });
render();
`; }

// ── Email notifications ─────────────────────────────────────────────────────
// reviewNotifyTick runs on a 30-min time trigger (installReviewNotifications
// creates it). Two mails go out — publish failures to RV_NOTIFY_EMAIL (Marcus
// only, it is an operational alert), and the Weekly Action digest to
// RV_DIGEST_EMAILS (the picker's reviewers). Each at most once per row:
//   • posts that became review-ready (D=Done, G=Done, J untouched)
//   • publishes that FAILED (J=Hold) — the watchdog for the publish stage.
// Sent-state lives in Script Properties and is pruned when rows move on, so
// a rerolled post that becomes ready again notifies again.

function reviewNotifyTick() {
  var props = PropertiesService.getScriptProperties();
  var seen;
  try { seen = JSON.parse(props.getProperty('rv_notified') || '{}'); }
  catch (e) { seen = {}; }
  seen.hold = seen.hold || [];

  var tz  = rvSs_().getSpreadsheetTimeZone();
  var now = new Date();
  var url = reviewUrl_();
  var hub = rvFlowHub_();

  // ── Publish failures mail immediately, any day. A post that failed to go out
  //    should not wait for Monday.
  var sched   = rvScheduled_();
  var holds   = sched.filter(function (p) { return p.status === 'Hold'; });
  var holdNow = holds.map(function (p) { return String(p.n); });
  var newHold = holdNow.filter(function (n) { return seen.hold.indexOf(n) === -1; });
  if (newHold.length) {
    var f = ['Date: ' + rvTodayUS_(), 'Flow Hub: ' + hub, '',
             'PUBLISH FAILED for row(s) ' + newHold.join(', ') + ':'];
    holds.forEach(function (p) {
      if (newHold.indexOf(String(p.n)) !== -1) {
        f.push('  #' + p.n + ' (' + p.title + ') — ' + rvFailureReason_(p.lastRemark) +
               ' [' + p.lastRemark + ']');
      }
    });
    f.push('', 'These sit under NEEDS ATTENTION with Retry / Reschedule / Cancel.',
           '', 'Review Link:', url);
    MailApp.sendEmail({
      to: RV_NOTIFY_EMAIL,
      subject: '[SELENE DREAMS] Publish FAILED - row(s) ' + newHold.join(', '),
      body: f.join('\n')
    });
  }

  // ── The Weekly Action digest: one send per week, on RV_DIGEST_DOW, covering
  //    BOTH lanes. Everything still waiting is listed, not only what is new,
  //    because a weekly mail is a worklist rather than an alert.
  var dow  = Number(Utilities.formatDate(now, tz, 'u'));   // 1 = Mon … 7 = Sun
  var week = Utilities.formatDate(now, tz, 'YYYY-ww');
  if (dow === RV_DIGEST_DOW && seen.digestWeek !== week) {
    var pending = rvPending_().concat(rvEduPending_());    // no images — stays cheap
    var ai  = pending.filter(function (p) { return p.lane !== 'edu'; })
                     .map(function (p) { return p.num; });
    var edu = pending.filter(function (p) { return p.lane === 'edu'; })
                     .map(function (p) { return p.num; });
    var brief;
    if (!pending.length) {
      brief = 'Nothing waiting on you this week.';
    } else {
      var parts = [];
      if (ai.length)  parts.push('AI carousel row(s) ' + ai.join(', '));
      if (edu.length) parts.push('Educational row(s) ' + edu.join(', '));
      brief = pending.length + ' post(s) ready for review: ' + parts.join(' · ') + '.';
    }
    MailApp.sendEmail({
      to: RV_DIGEST_EMAILS.join(','),
      subject: '[SELENE DREAMS] Weekly Action - Carousel Review',
      body: ['Date: ' + rvTodayUS_(),
             'Flow Hub: ' + hub,
             '',
             'Weekly Brief:',
             brief,
             '',
             'Review Link:',
             url].join('\n')
    });
    seen.digestWeek = week;
  }
  props.setProperty('rv_notified',
                    JSON.stringify({ hold: holdNow, digestWeek: seen.digestWeek || '' }));
}

/** Run ONCE from the editor. Idempotent — replaces any existing trigger. */
function installReviewNotifications() {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === 'reviewNotifyTick') ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger('reviewNotifyTick').timeBased().everyMinutes(30).create();
  Logger.log('reviewNotifyTick installed — checks every 30 minutes. Publish failures\n'
             + 'mail at once; the Weekly Action digest goes out on day ' + RV_DIGEST_DOW
             + ' (1 = Mon). Both to ' + RV_NOTIFY_EMAIL);
}

/** Editor diagnostic: logs what the page would render, without rendering it. */
function reviewDoctor() {
  var st = reviewState();
  Logger.log('build ' + st.build + ' · today ' + st.today + ' · default date ' + st.defaultDate);
  Logger.log('pending ' + st.pending.length + ' · regenerating ' + st.regen.length +
             ' · needs attention ' + st.attention.length + ' · calendar items ' + st.calendar.length);
  st.calendar.forEach(function (it) { Logger.log('  ' + it.type + ' ' + it.date + ' ' + it.status + ' — ' + it.title); });
}

// ── Local HTML escape ───────────────────────────────────────────────────────
// Namespaced rather than reusing picker.gs's esc_: every .gs file in an Apps
// Script project shares ONE global scope.
function rvEsc_(s) {
  return String(s === null || s === undefined ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}
