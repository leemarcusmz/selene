/**
 * Selene Dreams — Generation Queue Bridge
 * ----------------------------------------
 * Polls the `queue/` folder of the private GitHub repo `leemarcusmz/selene-ig-memory`
 * and appends any new prompt rows into the "Generation Queue" tab of the
 * Content Generation Queue spreadsheet.
 *
 * This lets a cloud Cowork session (which cannot reach Google's APIs) drop a
 * small JSON file into GitHub; this script — running on Google's servers with
 * native Sheet access — picks it up within ~5 minutes and writes the row.
 * Marcus's Mac does NOT need to be on.
 *
 * SETUP (one time):
 *   1. Open the sheet → Extensions → Apps Script. Paste this whole file.
 *   2. Project Settings (gear icon) → Script Properties → Add property:
 *          GITHUB_TOKEN  =  <the selene-ig-memory PAT>
 *   3. Back in the editor, run installTrigger() once (authorize when asked).
 *      That schedules processQueue() to run every 5 minutes.
 *   4. Done. To stop it later, run removeTriggers().
 *
 * SECURITY: the token lives only in Script Properties, never in this code.
 * The script only READS the repo and updates its own processed-list; it does
 * not push back to GitHub.
 */

// ---- Config ---------------------------------------------------------------
var REPO        = 'leemarcusmz/selene-ig-memory';
var QUEUE_DIR   = 'queue';                                   // folder in the repo
var BRANCH      = 'main';
var SHEET_ID    = '1GJO1YgfPY1QSTX-7ZhBA4xI7teKsajf04-MVPkMdp9s';
var SHEET_NAME  = 'Generation Queue';
var MAX_PROMPTS = 3;                                         // credit cap (2026-07-20)

// 0-based column indexes, matching append_row.py / the sheet layout.
// (2026-07-22: Reference Image 1-5 and the legacy Status columns were
// deleted from the queue — the bridge writes prompts only.)
var COL = {
  YEAR: 1, MONTH: 2, FABRIC: 3, PRODUCT_TYPE: 4, VARIANT: 5,
  PROMPT: [6, 7, 8, 9, 10]        // G-K  (Prompt 1-5)  — only 1-3 ever filled
};

// ---- Trigger management ---------------------------------------------------
function installTrigger() {
  removeTriggers();
  ScriptApp.newTrigger('processQueue')
    .timeBased()
    .everyMinutes(5)
    .create();
  Logger.log('Trigger installed: processQueue() every 5 minutes.');
}

function removeTriggers() {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === 'processQueue') ScriptApp.deleteTrigger(t);
  });
}

// ---- Main -----------------------------------------------------------------
function processQueue() {
  var lock = LockService.getScriptLock();
  if (!lock.tryLock(30000)) return;   // another run is in progress
  try {
    var token = PropertiesService.getScriptProperties().getProperty('GITHUB_TOKEN');
    if (!token) { Logger.log('ERROR: GITHUB_TOKEN script property not set.'); return; }

    var files = listQueueFiles_(token);          // [{name, download_url}]
    if (!files.length) return;

    var processed = getProcessedSet_();
    var sheet = SpreadsheetApp.openById(SHEET_ID).getSheetByName(SHEET_NAME);
    if (!sheet) { Logger.log('ERROR: sheet tab "' + SHEET_NAME + '" not found.'); return; }

    files.sort(function (a, b) { return a.name < b.name ? -1 : 1; });  // chronological by filename

    files.forEach(function (f) {
      if (processed[f.name]) return;             // already handled
      try {
        var payload = JSON.parse(fetch_(f.download_url, token));
        appendRow_(sheet, payload);
        markProcessed_(f.name);
        Logger.log('Appended queue file: ' + f.name);
      } catch (err) {
        Logger.log('SKIP ' + f.name + ' — ' + err);
        // Not marked processed, so a transient error retries next run.
      }
    });
  } finally {
    lock.releaseLock();
  }
}

// ---- Sheet write ----------------------------------------------------------
function appendRow_(sheet, p) {
  var prompts = (p.prompts || []).map(function (x) {
    return (x && typeof x === 'object' && 'prompt' in x) ? x.prompt : x;
  }).filter(function (s) { return s && String(s).trim(); });

  if (!prompts.length) throw new Error('no prompts in payload');
  if (prompts.length > MAX_PROMPTS) prompts = prompts.slice(0, MAX_PROMPTS);   // enforce cap

  var row = firstEmptyRow_(sheet);
  var now = new Date();
  sheet.getRange(row, COL.YEAR + 1).setValue(p.year || now.getFullYear());
  sheet.getRange(row, COL.MONTH + 1).setValue(
    p.month || now.toLocaleString('en-US', { month: 'long' }));
  sheet.getRange(row, COL.FABRIC + 1).setValue(p.fabric || '');
  sheet.getRange(row, COL.PRODUCT_TYPE + 1).setValue(p.productType || p.product_type || '');
  sheet.getRange(row, COL.VARIANT + 1).setValue(p.variant || '');

  for (var i = 0; i < MAX_PROMPTS; i++) {
    sheet.getRange(row, COL.PROMPT[i] + 1).setValue(prompts[i] || '');
  }
  // Generation is triggered from the Generation Status tab (col D → Ready).
}

/**
 * First row where Year, Fabric AND Prompt 1 are all blank — mirrors
 * append_row.py's occupied-if-any-anchor rule so draft rows aren't overwritten.
 */
function firstEmptyRow_(sheet) {
  var start = 2;
  var last = sheet.getLastRow();
  if (last < start) return start;
  var yearCol   = sheet.getRange(start, COL.YEAR + 1,   last - start + 1, 1).getValues();
  var fabCol    = sheet.getRange(start, COL.FABRIC + 1, last - start + 1, 1).getValues();
  var promptCol = sheet.getRange(start, COL.PROMPT[0] + 1, last - start + 1, 1).getValues();
  for (var i = 0; i < yearCol.length; i++) {
    var occupied = String(yearCol[i][0]).trim() ||
                   String(fabCol[i][0]).trim() ||
                   String(promptCol[i][0]).trim();
    if (!occupied) return start + i;
  }
  return last + 1;
}

// ---- GitHub helpers -------------------------------------------------------
function listQueueFiles_(token) {
  var url = 'https://api.github.com/repos/' + REPO + '/contents/' +
            QUEUE_DIR + '?ref=' + BRANCH;
  var resp = UrlFetchApp.fetch(url, {
    method: 'get',
    muteHttpExceptions: true,
    headers: { Authorization: 'token ' + token, Accept: 'application/vnd.github+json' }
  });
  var code = resp.getResponseCode();
  if (code === 404) return [];                 // queue/ folder doesn't exist yet
  if (code !== 200) throw new Error('GitHub list failed: ' + code + ' ' + resp.getContentText());
  return JSON.parse(resp.getContentText())
    .filter(function (e) { return e.type === 'file' && /\.json$/i.test(e.name); })
    .map(function (e) { return { name: e.name, download_url: e.download_url }; });
}

function fetch_(url, token) {
  var resp = UrlFetchApp.fetch(url, {
    method: 'get',
    muteHttpExceptions: true,
    headers: { Authorization: 'token ' + token }
  });
  if (resp.getResponseCode() !== 200) {
    throw new Error('fetch failed: ' + resp.getResponseCode());
  }
  return resp.getContentText();
}

// ---- Processed-file bookkeeping (Script Properties) -----------------------
function getProcessedSet_() {
  var raw = PropertiesService.getScriptProperties().getProperty('PROCESSED') || '{}';
  try { return JSON.parse(raw); } catch (e) { return {}; }
}

function markProcessed_(name) {
  var set = getProcessedSet_();
  set[name] = Date.now();
  // Keep the last ~400 entries so the property never grows unbounded.
  var keys = Object.keys(set);
  if (keys.length > 400) {
    keys.sort(function (a, b) { return set[a] - set[b]; });
    keys.slice(0, keys.length - 400).forEach(function (k) { delete set[k]; });
  }
  PropertiesService.getScriptProperties().setProperty('PROCESSED', JSON.stringify(set));
}

// ---- Manual test ----------------------------------------------------------
/** Run once to confirm token + repo access without waiting for the trigger. */
function testConnection() {
  var token = PropertiesService.getScriptProperties().getProperty('GITHUB_TOKEN');
  Logger.log(token ? 'Token present.' : 'NO TOKEN SET.');
  Logger.log('Queue files found: ' + JSON.stringify(listQueueFiles_(token)));
}
