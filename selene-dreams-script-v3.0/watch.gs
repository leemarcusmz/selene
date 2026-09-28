/**
 * =============================================================================
 * Selene Dreams — Silence Watchdog
 * watch.gs — VERSION 1.0 — 2026-09-28
 * =============================================================================
 * WHY THIS EXISTS
 *   2026-09-24 → 09-28: nothing published for four days and nothing said so.
 *   The VPS was healthy, the publisher ran every 15 minutes and found
 *   "nothing due", the reel folder was empty after the VPS move, and the
 *   picker email never arrived. Every existing alert watches for FAILURES;
 *   none of them watches for SILENCE. This one does — from Google's cloud, so
 *   it still fires when the VPS is dead, asleep, or never came back.
 *
 * WHAT IT CHECKS (once a day, 09:00 sheet timezone)
 *   1. VPS reachable      — GET <tunnel>/health answers 200 right now.
 *   2. Something posted   — newest "Posted" date in the Posted Content sheet
 *                           (all lanes) OR Generation Status col L OR the
 *                           educational sheet col M is within WD_MAX_QUIET_DAYS.
 *   3. Shortlist arrived  — from Tuesday on, shortlists/shortlist-<monday>.json
 *                           exists in selene-ig-memory (= research + screening
 *                           ran; the picker email depends on it).
 *   4. Queue has fuel     — at least one image row is Scheduled, or one edu
 *                           row is Approved/Scheduled. Otherwise "nothing due"
 *                           forever is guaranteed, however healthy the VPS is.
 *
 * WHAT IT SENDS
 *   ONE email, only when at least one check fails, to WD_EMAIL. Subject
 *   "[SELENE DREAMS] Watchdog: N issue(s)". Nothing when all four pass —
 *   silence from the watchdog means healthy, never "the watchdog is dead":
 *   run wdStatus() from the editor any time for the full report, or set
 *   WD_HEARTBEAT_DOW to a weekday (1=Mon) for a weekly "all clear".
 *
 * INSTALL (once)
 *   1. Apps Script editor → + file → name it watch → paste this whole file.
 *   2. Run wdInstall() once from the editor (approve the permissions).
 *      It creates the daily trigger; running it again replaces, never
 *      duplicates. wdStatus() prints the report to the log without emailing.
 *   3. No deployment needed — this is a time trigger, not a web page.
 *
 * RULES OBEYED
 *   - Every global here is WD_ / wd-prefixed (feedback_gs_globals). It reads
 *     WEBHOOK_URL, GS_* from Code.gs and ghFetch_/PICKER_* from picker.gs,
 *     and RV_EDU_SHEET_ID from review.gs — all shared project scope.
 *   - Never throws out of the trigger: every check is wrapped, and a check
 *     that cannot be evaluated is reported as a failure ("could not check"),
 *     because an unreadable sheet is itself news.
 *
 * VERSION vs BUILD: VERSION moves on features, WD_BUILD on every code change.
 * CHANGELOG
 *   1.0  2026-09-28  First build. Four checks, one email, daily trigger.
 * =============================================================================
 */

var WD_BUILD = '2026-09-28.a';
var WD_EMAIL = 'lee.marcusmz@gmail.com';
var WD_HOUR = 9;                   // daily run, sheet timezone
var WD_MAX_QUIET_DAYS = 3;         // no post for this long = alert
var WD_HEARTBEAT_DOW = 0;          // 0 = never; 1 = Monday "all clear" email
var WD_POSTED_SHEET_ID = '19evO6rmh-O9jMmQVUqu0ctV8Z9RRXArFt2xyP6i0bfE';
var WD_POSTED_TAB = 'Posts';
var WD_EDU_GS_TAB = 'Generation Status';
var WD_EDU_FIRST_ROW = 4;
var WD_EDU_COL_POST_STATUS = 11;   // K
var WD_EDU_COL_POST_DATE = 13;     // M
var WD_TRIGGER_FN = 'wdDailyCheck';

// ── entry points ────────────────────────────────────────────────────────────

/** Time trigger target. Emails only on failure (or weekly heartbeat). */
function wdDailyCheck() {
  var report = wdRunChecks_();
  var failed = report.checks.filter(function (c) { return !c.ok; });
  var tz = SpreadsheetApp.getActiveSpreadsheet().getSpreadsheetTimeZone();
  var dow = parseInt(Utilities.formatDate(new Date(), tz, 'u'), 10);
  var heartbeat = WD_HEARTBEAT_DOW > 0 && dow === WD_HEARTBEAT_DOW;
  if (!failed.length && !heartbeat) {
    Logger.log('watchdog: all clear, no email');
    return;
  }
  var subject = failed.length
    ? '[SELENE DREAMS] Watchdog: ' + failed.length + ' issue(s)'
    : '[SELENE DREAMS] Watchdog: all clear';
  MailApp.sendEmail({ to: WD_EMAIL, subject: subject, body: wdFormat_(report) });
  Logger.log('watchdog: emailed "' + subject + '"');
}

/** Manual: full report to the log, no email. */
function wdStatus() {
  Logger.log(wdFormat_(wdRunChecks_()));
}

/** Manual, once: (re)create the daily trigger. Idempotent. */
function wdInstall() {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === WD_TRIGGER_FN) ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger(WD_TRIGGER_FN).timeBased().atHour(WD_HOUR).everyDays(1).create();
  Logger.log('watchdog: daily trigger installed at ' + WD_HOUR + ':00 (sheet timezone). ' +
             'Build ' + WD_BUILD + '. Run wdStatus() to see the report now.');
}

// ── the checks ──────────────────────────────────────────────────────────────

function wdRunChecks_() {
  var checks = [
    wdSafe_('VPS reachable', wdCheckHealth_),
    wdSafe_('Something posted in the last ' + WD_MAX_QUIET_DAYS + ' days', wdCheckPosted_),
    wdSafe_('This week\'s shortlist arrived', wdCheckShortlist_),
    wdSafe_('Queue has something scheduled', wdCheckQueue_)
  ];
  return { at: new Date(), checks: checks };
}

function wdSafe_(name, fn) {
  try {
    var r = fn();
    return { name: name, ok: !!r.ok, detail: r.detail || '' };
  } catch (e) {
    return { name: name, ok: false, detail: 'could not check: ' + String(e).slice(0, 160) };
  }
}

function wdCheckHealth_() {
  var url = WEBHOOK_URL.replace('/webhook', '/health');
  var resp = UrlFetchApp.fetch(url, {
    method: 'get', muteHttpExceptions: true, followRedirects: true,
    headers: { 'ngrok-skip-browser-warning': 'true' }
  });
  var code = resp.getResponseCode();
  if (code === 200) return { ok: true, detail: 'HTTP 200 from ' + url };
  return { ok: false, detail: 'HTTP ' + code + ' from ' + url +
           (code === 404 ? ' (ngrok tunnel is down or pointing nowhere)' : '') };
}

function wdCheckPosted_() {
  var newest = null, source = '';
  var take = function (d, s) { if (d && (!newest || d > newest)) { newest = d; source = s; } };

  // 1. Posted Content sheet, all lanes (col C "Posted", 'yyyy-MM-dd HH:mm').
  try {
    var ps = SpreadsheetApp.openById(WD_POSTED_SHEET_ID).getSheetByName(WD_POSTED_TAB);
    if (ps && ps.getLastRow() > 1) {
      ps.getRange(2, 2, ps.getLastRow() - 1, 2).getValues().forEach(function (r) {
        take(wdDate_(r[1]), 'Posted Content (' + r[0] + ')');
      });
    }
  } catch (e) { /* fall through to the other sources */ }

  // 2. Image lane: Generation Status col L.
  try {
    var gs = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(GS_SHEET_NAME);
    if (gs && gs.getLastRow() >= GS_FIRST_DATA_ROW) {
      gs.getRange(GS_FIRST_DATA_ROW, GS_COL_POST_DATE, gs.getLastRow() - GS_FIRST_DATA_ROW + 1, 1)
        .getValues().forEach(function (r) { take(wdDate_(r[0]), 'image lane'); });
    }
  } catch (e) { /* ignore */ }

  // 3. Educational lane: its Generation Status col M.
  try {
    var es = SpreadsheetApp.openById(RV_EDU_SHEET_ID).getSheetByName(WD_EDU_GS_TAB);
    if (es && es.getLastRow() >= WD_EDU_FIRST_ROW) {
      es.getRange(WD_EDU_FIRST_ROW, WD_EDU_COL_POST_DATE, es.getLastRow() - WD_EDU_FIRST_ROW + 1, 1)
        .getValues().forEach(function (r) { take(wdDate_(r[0]), 'educational lane'); });
    }
  } catch (e) { /* ignore */ }

  if (!newest) return { ok: false, detail: 'no post date found in any lane' };
  var days = (Date.now() - newest.getTime()) / 86400000;
  var tz = SpreadsheetApp.getActiveSpreadsheet().getSpreadsheetTimeZone();
  var when = Utilities.formatDate(newest, tz, 'EEE d MMM HH:mm');
  return { ok: days <= WD_MAX_QUIET_DAYS,
           detail: 'last post ' + when + ' (' + days.toFixed(1) + ' days ago, ' + source + ')' };
}

function wdCheckShortlist_() {
  var tz = SpreadsheetApp.getActiveSpreadsheet().getSpreadsheetTimeZone();
  var now = new Date();
  var dow = parseInt(Utilities.formatDate(now, tz, 'u'), 10);       // 1=Mon
  if (dow === 1) return { ok: true, detail: 'Monday — research runs today, not judged yet' };
  var monday = new Date(now.getTime() - ((dow - 1) * 86400000));
  var week = Utilities.formatDate(monday, tz, 'yyyy-MM-dd');
  var path = SHORTLIST_DIR + '/shortlist-' + week + '.json';
  var resp = ghFetch_('https://api.github.com/repos/' + PICKER_REPO +
                      '/contents/' + path + '?ref=' + PICKER_BRANCH);
  var code = resp.getResponseCode();
  if (code === 200) return { ok: true, detail: path + ' exists' };
  if (code === 404) return { ok: false, detail: path + ' missing — Monday research or screening did not finish' };
  return { ok: false, detail: 'GitHub answered HTTP ' + code + ' for ' + path };
}

function wdCheckQueue_() {
  var scheduled = 0, eduReady = 0;
  var gs = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(GS_SHEET_NAME);
  if (gs && gs.getLastRow() >= GS_FIRST_DATA_ROW) {
    gs.getRange(GS_FIRST_DATA_ROW, GS_COL_POST_STATUS, gs.getLastRow() - GS_FIRST_DATA_ROW + 1, 1)
      .getValues().forEach(function (r) { if (String(r[0]).trim() === 'Scheduled') scheduled++; });
  }
  try {
    var es = SpreadsheetApp.openById(RV_EDU_SHEET_ID).getSheetByName(WD_EDU_GS_TAB);
    if (es && es.getLastRow() >= WD_EDU_FIRST_ROW) {
      es.getRange(WD_EDU_FIRST_ROW, WD_EDU_COL_POST_STATUS, es.getLastRow() - WD_EDU_FIRST_ROW + 1, 1)
        .getValues().forEach(function (r) {
          var v = String(r[0]).trim();
          if (v === 'Approved' || v === 'Scheduled') eduReady++;
        });
    }
  } catch (e) { /* edu sheet unreadable: judge on the image lane alone */ }
  var detail = scheduled + ' image post(s) scheduled, ' + eduReady + ' educational approved/scheduled';
  if (scheduled + eduReady > 0) return { ok: true, detail: detail };
  return { ok: false, detail: detail + ' — the publisher will say "nothing due" until you approve something on the review page' };
}

// ── helpers ─────────────────────────────────────────────────────────────────

function wdDate_(v) {
  if (v instanceof Date) return isNaN(v.getTime()) ? null : v;
  var s = String(v || '').trim();
  if (!s) return null;
  var d = new Date(s.replace(' ', 'T'));
  return isNaN(d.getTime()) ? null : d;
}

function wdFormat_(report) {
  var tz = SpreadsheetApp.getActiveSpreadsheet().getSpreadsheetTimeZone();
  var lines = ['Selene Dreams watchdog — ' +
               Utilities.formatDate(report.at, tz, 'EEE d MMM yyyy HH:mm') + ' (' + tz + ')', ''];
  report.checks.forEach(function (c) {
    lines.push((c.ok ? 'OK   ' : 'FAIL ') + c.name);
    if (c.detail) lines.push('       ' + c.detail);
  });
  var failed = report.checks.filter(function (c) { return !c.ok; }).length;
  lines.push('');
  lines.push(failed ? failed + ' issue(s). What to do:' : 'All clear.');
  if (failed) {
    lines.push('  VPS down     → ssh vps, then: systemctl --user status selene-server selene-ngrok');
    lines.push('  Nothing posted / empty queue → open the review page and approve posts');
    lines.push('  Shortlist missing → on the VPS: curl -X POST http://127.0.0.1:5001/research -H "Content-Type: application/json" -d \'{"secret":"<WEBHOOK_SECRET>"}\'');
  }
  lines.push('');
  lines.push('watch.gs ' + WD_BUILD + ' · run wdStatus() in Apps Script for this report any time.');
  return lines.join('\n');
}
