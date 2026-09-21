/**
 * Selene Dreams — Google Apps Script Trigger v3.3
 * File: trigger.gs
 *
 * v3.3 (2026-09-14): WEBHOOK_SECRET rotated. The previous value was a
 *   guessable string that sat in ten files (three of them world-readable)
 *   and was the only thing between the public ngrok URL and /publish.
 *   Now a 43-char random token, matching .env and the three launchd
 *   plists on the Mac. picker.gs and review.gs reuse this constant, so
 *   this one line covers all three files. Deploy after saving.
 *
 * v3.2 (2026-09-08): WEBHOOK_URL is FIXED. It had never been filled in — it
 *   still held the ngrok placeholder, so every relay POST that rides this
 *   constant went to a host that does not exist. *.ngrok-free.dev has
 *   WILDCARD DNS, so the bogus name resolved to ngrok's edge and answered
 *   404 — and under muteHttpExceptions a 404 is not an exception, so the
 *   caller logged success. sendWebhook() and sendCaptionWebhook() below
 *   have always guarded for this; the newer relays in picker.gs
 *   (research, screening, pick submission, added 2026-08-12) never reused
 *   the guard, so those three stages failed silently for weeks. Now set to
 *   the reserved static domain. See picker.gs v3.5 for the matching
 *   response-code logging.
 *
 * v3.1 (2026-07-22): the "Generation Status" tab becomes the control panel.
 *   • Image generation is triggered from Generation Status col D (was queue Q).
 *   • Caption generation is requested via Generation Status col G = "Ready"
 *     (picked up by the hourly caption agent; this script only validates).
 *   • Post Status (col J) = "Done" auto-stamps Post Date (col L).
 *   • Errors / notifications go to System Remark(s) (col M).
 *   • Rows are keyed by # (col B) = the Generation Queue # (queue row = # + 1).
 *
 * Retained from v3.0: cascading Fabric → Product Type → Variant dropdowns on
 * the Generation Queue, Done-row hiding, webhook plumbing.
 *
 * SETUP (upgrade from v3.0)
 * ────────────────────────────────────────────────────────────────
 * 1. Extensions > Apps Script → replace trigger.gs content with this file.
 * 2. WEBHOOK_URL below is the RESERVED STATIC ngrok domain — it survives
 *    launcher restarts and must never be returned to a placeholder.
 * 3. Save. Confirm the installable trigger (handleEdit, on edit) is active.
 * 4. Run syncGenerationStatusRows() once (or Selene Tools > Sync Generation
 *    Status) — fills #/No. of Prompts formulas, dropdowns, and backfills
 *    current statuses from existing data.
 */

const WEBHOOK_URL    = 'https://list-salary-freebee.ngrok-free.dev/webhook';
const WEBHOOK_SECRET = 'd8xRhOIJ-7S3DqWgiq0ahJIFCXOYepxM24Xwgt6DwLk';

// ── Generation Queue (data sheet) ───────────────────────────────
const SHEET_NAME    = 'Generation Queue';
const HEADER_ROW    = 1;

const FABRIC_COLUMN       = 4;   // D
const PRODUCT_TYPE_COLUMN = 5;   // E
const VARIANT_COLUMN      = 6;   // F
const QUEUE_PROMPT_FIRST  = 7;   // G
const QUEUE_PROMPT_LAST   = 11;  // K
// (2026-07-22: queue columns L-Q — Reference Image 1-5 and the legacy
// Status — were deleted. Data cols after prompts are now L Credits,
// M Output Folder, N Image URLs, O Carousel ID, P Notes.)
const QUEUE_IMAGE_URLS_COLUMN = 14;  // N

// ── Generation Status (control panel) ───────────────────────────
const GS_SHEET_NAME     = 'Generation Status';
const GS_HEADER_ROW     = 3;   // column-title row
const GS_FIRST_DATA_ROW = 4;   // GS row for # N = N + 3

const GS_COL_NUMBER      = 2;   // B  #
const GS_COL_NUM_PROMPTS = 3;   // C  No. of Prompts
const GS_COL_GEN_STATUS  = 4;   // D  Status (image generation)
const GS_COL_GEN_DATE    = 5;   // E  Completion Date
const GS_COL_GEN_TIME    = 6;   // F  Completion Time
const GS_COL_CAP_STATUS  = 7;   // G  Status (caption)
const GS_COL_CAP_DATE    = 8;   // H  Completion Date
const GS_COL_CAP_TIME    = 9;   // I  Completion Time
const GS_COL_POST_STATUS = 10;  // J  Post Status
const GS_COL_SCHED_DATE  = 11;  // K  Scheduled Date
const GS_COL_POST_DATE   = 12;  // L  Post Date
const GS_COL_SYS_REMARK  = 13;  // M  System Remark(s)
const GS_COL_USER_REMARK = 14;  // N  User Remark(s)

const GEN_STATUSES  = ['Ready', 'Hold', 'Processing', 'Done', 'ERROR'];
const CAP_STATUSES  = ['Not Available', 'Not Started', 'Ready', 'Processing', 'ERROR', 'Done'];
const POST_STATUSES = ['Not Started', 'Scheduled', 'Done'];

// Baseline "show everything" lists for the cascading dropdowns.
const ALL_PRODUCT_TYPES = [
  'Blanket', 'Duvet Set', 'Eye Mask', 'Pillow Case', 'Sheet Set'
];
const ALL_VARIANTS = [
  'Alabaster White', 'Ash Gray', 'Cream White', 'Deep Ocean', 'Desert Sand',
  'Dove Gray', 'Driftwood', 'Frost White', 'Herb Sage', 'Icy White',
  'Ocean Breeze', 'Olive Sage', 'Pewter Gray', 'Shadow Gray', 'Silver Mist',
  'Soft Maple', 'Stone Sage', 'Stone Taupe', 'Terracotta Blush', 'Warm Taupe'
];

// ════════════════════════════════════════════════════════════════
// Menu
// ════════════════════════════════════════════════════════════════

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('Selene Tools')
    .addItem('Sync Generation Status', 'syncGenerationStatusRows')
    .addSeparator()
    .addItem('Hide Done rows', 'hideDoneRows')
    .addItem('Show all rows', 'showAllRows')
    .addSeparator()
    .addItem('Refresh cascading validations', 'refreshAllValidations')
    .addToUi();
}

// ════════════════════════════════════════════════════════════════
// Edit router
// ════════════════════════════════════════════════════════════════

function handleEdit(e) {
  try {
    const sheet = e.source.getActiveSheet();
    const name = sheet.getName();
    if (name === SHEET_NAME) {
      handleQueueEdit(e, sheet);
    } else if (name === GS_SHEET_NAME) {
      handleStatusEdit(e, sheet);
    }
  } catch (error) {
    Logger.log('handleEdit error: ' + error.toString());
  }
}

// ── Generation Queue edits: cascades + manual Done hide ─────────

function handleQueueEdit(e, sheet) {
  const col = e.range.getColumn();
  const row = e.range.getRow();
  if (row === HEADER_ROW) return;

  if (col === FABRIC_COLUMN) {
    handleFabricEdit(e.source, sheet, row, e.value);
    return;
  }
  if (col === PRODUCT_TYPE_COLUMN) {
    handleProductTypeEdit(e.source, sheet, row, e.value);
    return;
  }
  // All status control lives on the Generation Status tab (col D / G / J).
}

// ── Generation Status edits: the control panel ──────────────────

function handleStatusEdit(e, sheet) {
  const col = e.range.getColumn();
  const row = e.range.getRow();
  if (row < GS_FIRST_DATA_ROW) return;

  // D — image generation trigger (same semantics as the old queue Status)
  if (col === GS_COL_GEN_STATUS && e.value === 'Ready') {
    const num = parseInt(sheet.getRange(row, GS_COL_NUMBER).getValue(), 10);
    if (!num || isNaN(num)) {
      writeRemark(sheet, row,
        'IMAGE: cannot start — no # in column B for this row.');
      return;
    }
    const queueRow = num + 1;  // queue # = queue row - 1
    Logger.log('GS row ' + row + ' (#' + num + ') set to Ready — webhook for queue row ' + queueRow);
    const result = sendWebhook(queueRow);
    if (result !== 'ok') {
      sheet.getRange(row, GS_COL_GEN_STATUS).setValue('ERROR');
      writeRemark(sheet, row,
        'IMAGE: webhook failed (' + result + '). Is the Mac server + ngrok running? ' +
        'Fix and set Status back to Ready.');
    } else {
      SpreadsheetApp.getActiveSpreadsheet().toast(
        '#' + num + ' sent for image generation.', 'Selene', 4);
    }
    return;
  }

  // G — caption trigger: fires the local caption runner, same wiring as images
  if (col === GS_COL_CAP_STATUS && e.value === 'Ready') {
    const genStatus = String(
      sheet.getRange(row, GS_COL_GEN_STATUS).getValue() || '').trim();
    if (genStatus !== 'Done') {
      // Images aren't done — captions not available yet.
      sheet.getRange(row, GS_COL_CAP_STATUS).setValue('Not Available');
      writeRemark(sheet, row,
        'CAPTION: cannot start — image generation Status (col D) is "' +
        (genStatus || 'blank') + '", not Done.');
      return;
    }
    const num = parseInt(sheet.getRange(row, GS_COL_NUMBER).getValue(), 10);
    if (!num || isNaN(num)) {
      writeRemark(sheet, row,
        'CAPTION: cannot start — no # in column B for this row.');
      return;
    }
    const result = sendCaptionWebhook(num);
    if (result !== 'ok') {
      sheet.getRange(row, GS_COL_CAP_STATUS).setValue('ERROR');
      writeRemark(sheet, row,
        'CAPTION: webhook failed (' + result + '). Is "Start Selene AI" running? ' +
        'Start it and set Status back to Ready — or ask Claude in a Selene chat.');
    } else {
      SpreadsheetApp.getActiveSpreadsheet().toast(
        '#' + num + ' sent for caption generation.', 'Selene', 4);
    }
    return;
  }

  // J — Post Status: stamp Post Date when set to Done
  if (col === GS_COL_POST_STATUS && e.value === 'Done') {
    const tz = e.source.getSpreadsheetTimeZone();
    sheet.getRange(row, GS_COL_POST_DATE).setValue(
      Utilities.formatDate(new Date(), tz, 'yyyy-MM-dd'));
    return;
  }
}

function writeRemark(sheet, row, message) {
  const cell = sheet.getRange(row, GS_COL_SYS_REMARK);
  const existing = String(cell.getValue() || '').trim();
  const tz = SpreadsheetApp.getActiveSpreadsheet().getSpreadsheetTimeZone();
  const stamp = Utilities.formatDate(new Date(), tz, 'yyyy-MM-dd HH:mm');
  const entry = '[' + stamp + '] ' + message;
  cell.setValue(existing ? existing + ' | ' + entry : entry);
}

// ════════════════════════════════════════════════════════════════
// Sync — fills #/No. of Prompts, dropdowns, and backfills statuses
// ════════════════════════════════════════════════════════════════

/**
 * Idempotent. Safe to re-run any time (menu: Selene Tools > Sync Generation
 * Status). For every prefilled queue row:
 *   B: formula mirroring the queue # (blank until the row has a prompt)
 *   C: formula counting filled Prompt 1-5 cells
 *   D/G/J: dropdown validations
 * Backfill (only into EMPTY cells — never overwrites live statuses):
 *   D: 'Done' when the queue row already has Image URLs
 *   G: 'Done' if the Generated Caption tab has this #, else 'Not Started'
 *      when D is Done, else 'Not Available'
 *   J: 'Not Started'
 */
function syncGenerationStatusRows() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const queue = ss.getSheetByName(SHEET_NAME);
  const gs = ss.getSheetByName(GS_SHEET_NAME);
  if (!queue || !gs) {
    SpreadsheetApp.getUi().alert('Sheet not found: ' +
      (!queue ? SHEET_NAME : GS_SHEET_NAME));
    return;
  }

  const queueLast = queue.getLastRow();               // includes prefilled # rows
  const n = queueLast - HEADER_ROW;                   // number of queue data rows
  if (n < 1) return;

  // Captioned #s from the Generated Caption tab (col A)
  const capDone = {};
  const capSheet = ss.getSheetByName('Generated Caption');
  if (capSheet && capSheet.getLastRow() > 1) {
    capSheet.getRange(2, 1, capSheet.getLastRow() - 1, 1).getValues()
      .forEach(function (r) {
        const v = String(r[0]).trim();
        if (v) capDone[v] = true;
      });
  }

  // Queue Status col is gone — infer Done from a non-empty Image URLs cell.
  const queueImageUrls = queue.getRange(
    HEADER_ROW + 1, QUEUE_IMAGE_URLS_COLUMN, n, 1).getValues();
  const queuePrompts = queue.getRange(
    HEADER_ROW + 1, QUEUE_PROMPT_FIRST, n, 5).getValues();

  const dRange = gs.getRange(GS_FIRST_DATA_ROW, GS_COL_GEN_STATUS, n, 1);
  const gRange = gs.getRange(GS_FIRST_DATA_ROW, GS_COL_CAP_STATUS, n, 1);
  const jRange = gs.getRange(GS_FIRST_DATA_ROW, GS_COL_POST_STATUS, n, 1);
  const dVals = dRange.getValues();
  const gVals = gRange.getValues();
  const jVals = jRange.getValues();

  const bFormulas = [];
  const cFormulas = [];

  for (let i = 0; i < n; i++) {
    const qRow = HEADER_ROW + 1 + i;                  // queue sheet row
    bFormulas.push([
      '=IF(COUNTA(\'' + SHEET_NAME + '\'!G' + qRow + ':K' + qRow + ')=0,"",' +
      '\'' + SHEET_NAME + '\'!A' + qRow + ')'
    ]);
    cFormulas.push([
      '=IF($B' + (GS_FIRST_DATA_ROW + i) + '="","",' +
      'COUNTA(\'' + SHEET_NAME + '\'!G' + qRow + ':K' + qRow + '))'
    ]);

    const hasPrompts = queuePrompts[i].some(function (p) {
      return String(p).trim() !== '';
    });
    if (!hasPrompts) continue;                        // leave statuses alone

    const hasImages = String(queueImageUrls[i][0] || '').trim() !== '';
    const num = String(qRow - 1);

    if (String(dVals[i][0] || '').trim() === '' && hasImages) {
      dVals[i][0] = 'Done';               // backfill: images exist → Done
    }
    if (String(gVals[i][0] || '').trim() === '') {
      const dNow = String(dVals[i][0] || '').trim();
      gVals[i][0] = capDone[num] ? 'Done'
        : (dNow === 'Done' ? 'Not Started' : 'Not Available');
    }
    if (String(jVals[i][0] || '').trim() === '') {
      jVals[i][0] = 'Not Started';
    }
  }

  gs.getRange(GS_FIRST_DATA_ROW, GS_COL_NUMBER, n, 1).setFormulas(bFormulas);
  gs.getRange(GS_FIRST_DATA_ROW, GS_COL_NUM_PROMPTS, n, 1).setFormulas(cFormulas);
  dRange.setValues(dVals);
  gRange.setValues(gVals);
  jRange.setValues(jVals);

  // Dropdowns
  dRange.setDataValidation(SpreadsheetApp.newDataValidation()
    .requireValueInList(GEN_STATUSES, true).setAllowInvalid(false).build());
  gRange.setDataValidation(SpreadsheetApp.newDataValidation()
    .requireValueInList(CAP_STATUSES, true).setAllowInvalid(false).build());
  jRange.setDataValidation(SpreadsheetApp.newDataValidation()
    .requireValueInList(POST_STATUSES, true).setAllowInvalid(false).build());

  ss.toast('Generation Status synced for ' + n + ' row(s).', 'Selene Tools', 4);
}

// ════════════════════════════════════════════════════════════════
// v3.0 utilities (unchanged)
// ════════════════════════════════════════════════════════════════

function hideDoneRows() {
  // v3.1: Done state lives on the Generation Status tab (col D, keyed by #).
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName(SHEET_NAME);
  const gs = ss.getSheetByName(GS_SHEET_NAME);
  if (!sheet || !gs) return;

  const doneNums = {};
  const gsLast = gs.getLastRow();
  if (gsLast >= GS_FIRST_DATA_ROW) {
    const vals = gs.getRange(GS_FIRST_DATA_ROW, GS_COL_NUMBER,
      gsLast - GS_FIRST_DATA_ROW + 1, GS_COL_GEN_STATUS - GS_COL_NUMBER + 1
    ).getValues();
    vals.forEach(function (r) {
      const num = String(r[0]).trim();
      const st = String(r[GS_COL_GEN_STATUS - GS_COL_NUMBER]).trim();
      if (num && st === 'Done') doneNums[num] = true;
    });
  }

  const lastRow = sheet.getLastRow();
  let hidden = 0;
  for (let row = HEADER_ROW + 1; row <= lastRow; row++) {
    if (doneNums[String(row - 1)]) {
      sheet.setRowHeight(row, 21);
      sheet.hideRows(row);
      hidden++;
    }
  }
  ss.toast(hidden + ' Done row(s) hidden.', 'Selene Tools', 3);
}

function showAllRows() {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(SHEET_NAME);
  if (!sheet) return;
  const lastRow = sheet.getLastRow();
  if (lastRow > HEADER_ROW) {
    sheet.showRows(HEADER_ROW + 1, lastRow - HEADER_ROW);
  }
  SpreadsheetApp.getActiveSpreadsheet().toast(
    'All rows shown.', 'Selene Tools', 3
  );
}

function handleFabricEdit(spreadsheet, sheet, row, fabric) {
  const ptCell = sheet.getRange(row, PRODUCT_TYPE_COLUMN);
  const vCell  = sheet.getRange(row, VARIANT_COLUMN);

  ptCell.clearContent();
  vCell.clearContent();

  if (!fabric) {
    ptCell.setDataValidation(
      SpreadsheetApp.newDataValidation()
        .requireValueInList(ALL_PRODUCT_TYPES, true)
        .setAllowInvalid(false)
        .build()
    );
    vCell.setDataValidation(
      SpreadsheetApp.newDataValidation()
        .requireValueInList(ALL_VARIANTS, true)
        .setAllowInvalid(false)
        .build()
    );
    return;
  }

  const rangeName = 'Types_' + fabric;
  const namedRange = spreadsheet.getRangeByName(rangeName);
  if (!namedRange) {
    Logger.log('Named range not found: ' + rangeName);
    return;
  }
  ptCell.setDataValidation(
    SpreadsheetApp.newDataValidation()
      .requireValueInRange(namedRange, true)
      .setAllowInvalid(false)
      .build()
  );
}

function handleProductTypeEdit(spreadsheet, sheet, row, productType) {
  const vCell  = sheet.getRange(row, VARIANT_COLUMN);
  const fabric = sheet.getRange(row, FABRIC_COLUMN).getValue();

  vCell.clearContent();

  if (!fabric || !productType) {
    vCell.setDataValidation(
      SpreadsheetApp.newDataValidation()
        .requireValueInList(ALL_VARIANTS, true)
        .setAllowInvalid(false)
        .build()
    );
    return;
  }

  const rangeName = 'Variants_' + fabric + '_' + String(productType).replace(/ /g, '');
  const namedRange = spreadsheet.getRangeByName(rangeName);
  if (!namedRange) {
    Logger.log('Named range not found: ' + rangeName);
    return;
  }
  vCell.setDataValidation(
    SpreadsheetApp.newDataValidation()
      .requireValueInRange(namedRange, true)
      .setAllowInvalid(false)
      .build()
  );
}

/** POST /caption for a queue # — mirrors sendWebhook but for captions. */
function sendCaptionWebhook(num) {
  if (WEBHOOK_URL.indexOf('YOUR_NGROK_ID') !== -1) {
    Logger.log('ERROR: WEBHOOK_URL has not been updated.');
    return 'not_sent';
  }
  const url = WEBHOOK_URL.replace('/webhook', '/caption');
  const options = {
    method:             'post',
    contentType:        'application/json',
    payload:            JSON.stringify({ number: num, secret: WEBHOOK_SECRET }),
    muteHttpExceptions: true,
    followRedirects:    true,
    headers: { 'ngrok-skip-browser-warning': 'true' }
  };
  try {
    const response = UrlFetchApp.fetch(url, options);
    const code = response.getResponseCode();
    if (code === 200) return 'ok';
    Logger.log('Caption webhook error #' + num + ' — HTTP ' + code + ': ' +
      response.getContentText());
    return 'error_' + code;
  } catch (error) {
    Logger.log('Caption webhook failed for #' + num + ': ' + error.toString());
    return 'exception';
  }
}

function sendWebhook(rowIndex) {
  if (WEBHOOK_URL.indexOf('YOUR_NGROK_ID') !== -1) {
    Logger.log('ERROR: WEBHOOK_URL has not been updated.');
    return 'not_sent';
  }
  const payload = JSON.stringify({
    row_index: rowIndex,
    secret:    WEBHOOK_SECRET
  });
  const options = {
    method:             'post',
    contentType:        'application/json',
    payload:            payload,
    muteHttpExceptions: true,
    followRedirects:    true,
    headers: { 'ngrok-skip-browser-warning': 'true' }
  };
  try {
    const response = UrlFetchApp.fetch(WEBHOOK_URL, options);
    const code = response.getResponseCode();
    if (code === 200) return 'ok';
    Logger.log('Webhook error row ' + rowIndex + ' — HTTP ' + code + ': ' +
      response.getContentText());
    return 'error_' + code;
  } catch (error) {
    Logger.log('Webhook request failed for row ' + rowIndex + ': ' + error.toString());
    return 'exception';
  }
}

function testWebhook() {
  const TEST_ROW = 2;
  Logger.log('Test result: ' + sendWebhook(TEST_ROW));
}

function testHealth() {
  const healthUrl = WEBHOOK_URL.replace('/webhook', '/health');
  try {
    const response = UrlFetchApp.fetch(healthUrl, {
      muteHttpExceptions: true,
      headers: { 'ngrok-skip-browser-warning': 'true' }
    });
    Logger.log('Health: HTTP ' + response.getResponseCode() + ' — ' + response.getContentText());
  } catch (e) {
    Logger.log('Health check failed: ' + e.toString());
  }
}

function refreshAllValidations() {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(SHEET_NAME);
  if (!sheet) return;
  const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
  const lastRow = sheet.getLastRow();
  let count = 0;
  for (let row = HEADER_ROW + 1; row <= lastRow; row++) {
    const fabric      = sheet.getRange(row, FABRIC_COLUMN).getValue();
    const productType = sheet.getRange(row, PRODUCT_TYPE_COLUMN).getValue();
    if (!fabric) continue;

    const ptCell = sheet.getRange(row, PRODUCT_TYPE_COLUMN);
    const ptRange = spreadsheet.getRangeByName('Types_' + fabric);
    if (ptRange) {
      ptCell.setDataValidation(
        SpreadsheetApp.newDataValidation()
          .requireValueInRange(ptRange, true)
          .setAllowInvalid(false)
          .build()
      );
    }
    if (productType) {
      const vCell = sheet.getRange(row, VARIANT_COLUMN);
      const vRange = spreadsheet.getRangeByName(
        'Variants_' + fabric + '_' + String(productType).replace(/ /g, ''));
      if (vRange) {
        vCell.setDataValidation(
          SpreadsheetApp.newDataValidation()
            .requireValueInRange(vRange, true)
            .setAllowInvalid(false)
            .build()
        );
      }
    }
    count++;
  }
  Logger.log('Refreshed validations on ' + count + ' row(s).');
}
