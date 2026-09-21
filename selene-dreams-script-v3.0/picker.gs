/**
 * Selene Dreams — Weekly Picks web app ("Selene Dreams Research Picks")
 * File: picker.gs — lives in the SAME Apps Script project as trigger.gs
 * (it reuses that file's WEBHOOK_URL / WEBHOOK_SECRET globals) and owns the
 * project's single doGet router (?view=status, ?view=review).
 *
 * VERSION 4.1 — 2026-09-14          (page footer shows PICKER_BUILD)
 *
 * VERSION vs PICKER_BUILD: VERSION is the feature line, maintained here with
 * its changelog; PICKER_BUILD (below) is stamped on every paste, however
 * small, and printed in the page footer so a stale deployment is instantly
 * visible. If the footer's build doesn't match this file's, the deployment
 * is serving old code.
 *
 * What it does:
 *   • Serves the weekly shortlist (real IG images) pulled from the
 *     selene-ig-memory GitHub repo (shortlists/shortlist-YYYY-MM-DD.json),
 *     ranked by brand fit, plus the shelf of images saved in earlier weeks.
 *   • Teammates type their name and tap individual IMAGES. Tap order is the
 *     order: the first WEEKLY_IMAGE_CAP become this week's prompts, anything
 *     after is auto-saved to the shelf for next week. At most MAX_SLIDES from
 *     any one post (a post becomes one queue row with five prompt columns).
 *   • FIRST VALID SUBMISSION WINS the week (Weekly Picks tab); everyone after
 *     sees who picked what.
 *   • The winning pick POSTs /select to the Mac; prompt_runner writes the
 *     Generation Queue rows.
 *   • On the same 15-min tick it relays /research (Monday) and /screen to
 *     the Mac and emails the invite to TEAMMATE_EMAILS.
 *
 * ── CHANGELOG ────────────────────────────────────────────────────────────
 * v4.1  2026-09-14  Invite email rewritten to the Weekly Action format:
 *   subject '[SELENE DREAMS] Weekly Action - Content Picker', and a body
 *   carrying Date, Flow Hub, and a Weekly Brief that names where this
 *   week's posts were sourced from. Flow Hub comes from Script Property
 *   FLOW_HUB_URL (pkFlowHub_), falling back to the pinned artifact, so the
 *   link is changed without a redeploy. Nothing else about the picker moves.
 * v4.0  2026-09-09  (builds .a, .b, .c) REDESIGN — Claude Design round 2, desktop +
 *   mobile in ONE responsive page, rendered client-side from PK_STATE.
 *   • Header: title, week / count / "ranked by brand fit", a 15-slot prompt
 *     meter with gold overflow ticks; the four rules as chips (desktop) or a
 *     "?" sheet (mobile). No more paragraph of rules.
 *   • Sticky bar: "picking as" name field at the TOP, live count, clear all
 *     (5-second undo), Submit. Submit disabled until a name is typed.
 *   • Filters: all · fit ≥ 9 · one chip per FABRIC found in this week's
 *     data (never hard-coded) · carousels only. Selections survive filtering.
 *   • Tiles: 4:5 grid on desktop, 3-across squares on mobile. Order badge,
 *     "→ prompt NN" label, gold "next wk" for overflow, a zoom glyph on
 *     every tile that opens a lightbox (← → within the post, Esc/✕, and a
 *     Select/Selected button so you can pick while zoomed).
 *   • Per-post cap: once a post has MAX_SLIDES taken, its other tiles lock
 *     (dimmed, tooltip) instead of a page-level error. The greedy fill
 *     honours the cap, so un-picking never pushes a post over it.
 *   • Expired CDN images: "recovering from archive" → archivedImage(), or
 *     "image expired" (dimmed, not selectable).
 *   • Shelf rows (dashed cream, "saved <date> · by <name>") and held-over
 *     rows ("held over from <week>" gold tag) drawn as distinct things.
 *   • Terminal views: week-locked (who / how many / when + a compact grid of
 *     what was picked) and post-submit ("You got it" + overflow line).
 *     Lost-the-race is an inline red line under Submit, then a reload.
 *   • Explicit per-tile "save" button REMOVED — overflow auto-shelves.
 *     saveToShelf() is still used for the overflow on submit.
 *   • TEAMMATE_EMAILS filled (Marcus + Charles) — the invite now sends.
 *   • ?preview=1 renders the full shortlist even when the week is locked,
 *     with submitting disabled — for looking at the page, never for picking.
 *   • (.b) FIX weekWinner_: a Week cell auto-converted to a Date by Sheets
 *     never matched the shortlist week, so a picked week still showed the
 *     shortlist (seen 2026-09-09 for week 2026-09-07). Now compared as
 *     yyyy-MM-dd via pkWeekStr_(). Also: hidden likes (-1) read "likes
 *     hidden" instead of "-1 likes".
 *   • (.c) FIX locked view: tile grid used 1fr columns, so real photos of
 *     mixed sizes forced uneven columns (minmax(0,1fr) + min-width:0 on
 *     every grid, shortlist tiles included); "Submitted at" Date printed
 *     raw — now yyyy-MM-dd HH:mm; the mobile "· wk 09-07" title suffix
 *     no longer shows on desktop.
 *   • weekWinner_ now also returns the Details JSON so the locked view can
 *     draw what was picked.
 *   • Backend (GitHub, shelf, submitPicks, relays, invite) unchanged from
 *     v3.5 apart from weekWinner_.
 *
 * v3.5  2026-09-08  Relay logging tells the truth; pingMac() diagnostic.
 * v3.4  2026-08-21  Router: ?view=review → review.gs.
 * v3.3  2026-08-17→19  15-images-a-week model, click order decides, overflow
 *       auto-saves; rank badges; held-over entries (OWEEK map); ?view=status.
 * v3.1  2026-08-17  FIX archived-image recovery used the display number —
 *       recovery MUST use origN (ORIG map). Research window Mon 10:00.
 * v3.0  2026-08-13  One post per row, per-image selection, the shelf.
 * v2.0  2026-08-12  Pipeline relays on the 15-min tick.
 * v1.0  2026-07-23  First release.
 *
 * ── SETUP (one time) ─────────────────────────────────────────────────────
 *   1. Paste this file into the sheet's Apps Script project (file: picker).
 *   2. Script Properties: GITHUB_TOKEN = the selene-ig-memory token.
 *   3. Deploy → New deployment → Web app → Execute as: Me · Access: Anyone.
 *      Copy the /exec URL — that is the permanent picker link.
 *   4. Script Properties: PICKER_URL = that /exec URL.
 *   5. Run installEmailTrigger() once (15-min tick: relays + invite email).
 *
 * ── UPDATING ─────────────────────────────────────────────────────────────
 *   Editing the code does NOT change what the live URL serves. After pasting:
 *   Deploy → Manage deployments → pencil → Version: New version → Deploy.
 *   EDIT the existing deployment; a new one gets a new URL and orphans every
 *   link already emailed. Confirm the page footer shows the PICKER_BUILD set
 *   below.
 */

var TEAMMATE_EMAILS = [
  'lee.marcusmz@gmail.com',
  'holongcharles.lee@gmail.com',
];

// Bumped whenever the picker page changes. Shown in the page footer so the
// live deployment can always be identified without guessing which paste
// made it in — Apps Script's own version numbers are just a counter.
var PICKER_BUILD = '2026-09-14.a';

var PICKER_REPO = 'leemarcusmz/selene-ig-memory';
var PICKER_BRANCH = 'main';
var SHORTLIST_DIR = 'shortlists';
var PICKS_SHEET = 'Weekly Picks';
// Selection limits, reworked 2026-08-17.
//   WEEKLY_IMAGE_CAP — total images that become prompts this week. Credits are
//     billed per generated image, so this is the only real cost lever.
//   MAX_SLIDES — per post. 5 because a Generation Queue row has exactly five
//     Prompt columns and one picked post becomes one row; more would need a
//     second row, which QA/captions/outcomes all assume does not happen.
//   There is deliberately NO cap on the number of posts — 15 images spread
//     across 15 posts is as valid as 3 posts of 5.
// Anything chosen beyond WEEKLY_IMAGE_CAP is not rejected: it is saved to the
// shelf and reappears at the top of next week's picker.
var WEEKLY_IMAGE_CAP = 15;
var MAX_SLIDES = 5;

// ── GitHub helpers ─────────────────────────────────────────────

function ghToken_() {
  var t = PropertiesService.getScriptProperties().getProperty('GITHUB_TOKEN');
  if (!t) throw new Error('Script Property GITHUB_TOKEN is not set.');
  return t;
}

function ghFetch_(url) {
  var resp = UrlFetchApp.fetch(url, {
    muteHttpExceptions: true,
    headers: { Authorization: 'token ' + ghToken_(),
               Accept: 'application/vnd.github+json' }
  });
  if (resp.getResponseCode() !== 200) {
    throw new Error('GitHub fetch failed ' + resp.getResponseCode());
  }
  return resp.getContentText();
}


// ── The shelf: images saved for a later week ───────────────────
// A week's cap is 5 posts x 3 images, but a strong week often surfaces more
// than that. Saving costs nothing and has no cap; saved images appear in their
// own section at the top of every later picker until used or expired.
//
// The catch this solves: Instagram CDN URLs die within days (three of the
// 2026-08-10 candidates died within five hours). A shelf holding CDN links
// would show broken images a week later. So the bytes are copied into the
// repo AT SAVE TIME, while the link is still alive.

var SHELF_PATH = 'saved/shelf.json';
var SHELF_IMG_DIR = 'saved/images';
var SHELF_EXPIRY_DAYS = 21;      // ~3 weeks, then it drops off with a log line
var SHELF_RENDER_MAX = 12;       // bound the page size

function ghApi_(path) {
  return 'https://api.github.com/repos/' + PICKER_REPO + '/contents/' + path;
}

/** Returns {json, sha} or {json:null, sha:null} when the file is absent. */
function ghReadJson_(path) {
  var resp = UrlFetchApp.fetch(ghApi_(path) + '?ref=' + PICKER_BRANCH, {
    muteHttpExceptions: true,
    headers: { Authorization: 'token ' + ghToken_(),
               Accept: 'application/vnd.github+json' }
  });
  if (resp.getResponseCode() === 404) return { json: null, sha: null };
  if (resp.getResponseCode() !== 200) {
    throw new Error('GitHub read failed ' + resp.getResponseCode() + ' for ' + path);
  }
  var meta = JSON.parse(resp.getContentText());
  var text = Utilities.newBlob(Utilities.base64Decode(meta.content)).getDataAsString();
  return { json: JSON.parse(text), sha: meta.sha };
}

/** Raw bytes of a repo file as a data: URL — lets the private repo's archived
 *  images render in an <img> tag without exposing the token. */
function ghDataUrl_(path) {
  try {
    var resp = UrlFetchApp.fetch(ghApi_(path) + '?ref=' + PICKER_BRANCH, {
      muteHttpExceptions: true,
      headers: { Authorization: 'token ' + ghToken_(),
                 Accept: 'application/vnd.github+json' }
    });
    if (resp.getResponseCode() !== 200) return '';
    var meta = JSON.parse(resp.getContentText());
    return 'data:image/jpeg;base64,' + String(meta.content).replace(/\n/g, '');
  } catch (e) { return ''; }
}

function ghPutBase64_(path, b64, message, sha) {
  var body = { message: message, content: b64, branch: PICKER_BRANCH };
  if (sha) body.sha = sha;
  var resp = UrlFetchApp.fetch(ghApi_(path), {
    method: 'put', contentType: 'application/json',
    payload: JSON.stringify(body), muteHttpExceptions: true,
    headers: { Authorization: 'token ' + ghToken_(),
               Accept: 'application/vnd.github+json' }
  });
  var code = resp.getResponseCode();
  if (code !== 200 && code !== 201) {
    throw new Error('GitHub write failed ' + code + ' for ' + path + ': ' +
                    resp.getContentText().slice(0, 200));
  }
}

function daysSince_(iso) {
  var t = Date.parse(iso);
  if (isNaN(t)) return 0;
  return Math.floor((Date.now() - t) / 86400000);
}

/** Live shelf items, expired ones dropped. */
function shelfLoad_() {
  var got;
  try { got = ghReadJson_(SHELF_PATH); } catch (e) { return { items: [], sha: null, expired: [] }; }
  var items = (got.json && got.json.items) || [];
  var live = [], expired = [];
  items.forEach(function (it) {
    (daysSince_(it.savedAt) > SHELF_EXPIRY_DAYS ? expired : live).push(it);
  });
  return { items: live, sha: got.sha, expired: expired };
}

/**
 * Save chosen images for a later week. Called from the picker page.
 * items: [{n, slides:[i,...]}] referring to the CURRENT shortlist.
 */

/**
 * An archived copy of a shortlist image, as a data: URL.
 *
 * The page renders Instagram CDN URLs because they are fast and weigh nothing.
 * Those links die within days, though — on 2026-08-13 a whole post rendered as
 * empty boxes — so when the browser fails to load one it asks for this
 * instead. Only broken images pay the cost of being inlined.
 */
function archivedImage(week, n, i) {
  var name = (Number(i) === 1) ? 'cand_' + n + '.jpg'
                               : 'cand_' + n + '_s' + i + '.jpg';
  return ghDataUrl_('candidate-images/' + week + '/' + name);
}

function saveToShelf(name, week, items) {
  name = String(name || '').trim() || 'someone';
  if (!items || !items.length) return { ok: false, error: 'Nothing marked to save.' };

  var data = loadLatestShortlist_();
  if (!data || String(data.week) !== String(week)) {
    return { ok: false, error: 'A newer shortlist is live — refresh the page.' };
  }
  var byN = {};
  data.entries.forEach(function (e) { byN[e.n] = e; });

  var shelf = shelfLoad_();
  var existing = {};
  shelf.items.forEach(function (it) { existing[it.id] = true; });

  var added = 0, failed = 0;
  items.forEach(function (p) {
    var e = byN[p.n];
    if (!e) return;
    var imgs = e.images || [];
    var slides = [];
    (p.slides || []).forEach(function (i) {
      var url = imgs[i - 1];
      if (!url) return;
      var path = SHELF_IMG_DIR + '/' + week + '-' + p.n + '-' + i + '.jpg';
      try {
        // Copy the bytes now, while the CDN link still resolves.
        var blob = UrlFetchApp.fetch(url, { muteHttpExceptions: true }).getBlob();
        ghPutBase64_(path, Utilities.base64Encode(blob.getBytes()),
                     'Shelf image ' + week + ' #' + p.n + ' slide ' + i, null);
        slides.push({ i: i, archive: path });
      } catch (err) { failed++; }
    });
    if (!slides.length) return;
    var id = week + '-' + p.n;
    if (existing[id]) return;                    // already on the shelf
    shelf.items.push({
      id: id, week: week, n: p.n, savedAt: new Date().toISOString().slice(0, 10),
      savedBy: name, source: e.source || '', postUrl: e.postUrl || '',
      concept: e.concept || '', caption: e.caption || '', product: e.product || null,
      brandScore: e.brandScore || '', slides: slides
    });
    added++;
  });

  if (!added) return { ok: false, error: 'Could not save those images (links may have expired).' };

  ghPutBase64_(SHELF_PATH,
    Utilities.base64Encode(Utilities.newBlob(
      JSON.stringify({ items: shelf.items }, null, 1)).getBytes()),
    'Shelf: +' + added + ' from ' + week +
      (shelf.expired.length ? ' (expired ' + shelf.expired.length + ')' : ''),
    shelf.sha);

  return { ok: true, added: added, failed: failed, total: shelf.items.length };
}

/** Latest shortlist file, or null. Returns {week, entries[]}. */
function loadLatestShortlist_() {
  var listing;
  try {
    listing = JSON.parse(ghFetch_('https://api.github.com/repos/' + PICKER_REPO +
      '/contents/' + SHORTLIST_DIR + '?ref=' + PICKER_BRANCH));
  } catch (e) {
    return null;   // shortlists/ doesn't exist yet
  }
  var files = listing.filter(function (f) {
    return f.type === 'file' && /^shortlist-\d{4}-\d{2}-\d{2}\.json$/.test(f.name);
  }).sort(function (a, b) { return a.name < b.name ? 1 : -1; });
  if (!files.length) return null;
  var data = JSON.parse(ghFetch_(files[0].download_url));
  data.week = data.week || files[0].name.replace(/^shortlist-|\.json$/g, '');
  return data;
}

// ── Weekly Picks tab (the lock + record) ───────────────────────

function picksSheet_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sh = ss.getSheetByName(PICKS_SHEET);
  if (!sh) {
    sh = ss.insertSheet(PICKS_SHEET);
    sh.getRange(1, 1, 1, 7).setValues([[
      'Week', 'Picker', 'Posts', 'Slide choices', 'Submitted at',
      'Prompt status', 'Details'
    ]]).setFontWeight('bold');
  }
  return sh;
}

/** A Weekly Picks "Week" cell (string or Date) as 'yyyy-MM-dd'. */
function pkWeekStr_(v) {
  if (Object.prototype.toString.call(v) === '[object Date]') {
    return Utilities.formatDate(v, SpreadsheetApp.getActiveSpreadsheet().getSpreadsheetTimeZone(), 'yyyy-MM-dd');
  }
  return String(v == null ? '' : v).trim();
}

function weekWinner_(week) {
  var sh = picksSheet_();
  var last = sh.getLastRow();
  if (last < 2) return null;
  var vals = sh.getRange(2, 1, last - 1, 7).getValues();
  var want = String(week).trim();
  for (var i = 0; i < vals.length; i++) {
    // v4.0.b: Sheets may have auto-converted the Week cell to a Date, in
    // which case String(cell) is "Mon Sep 07 2026 ..." and never matched —
    // the page then showed the shortlist for a week that was already picked.
    if (pkWeekStr_(vals[i][0]) === want) {
      var details = [];
      try { details = JSON.parse(vals[i][6] || '[]'); } catch (e) { details = []; }
      return { picker: vals[i][1], posts: vals[i][2], slides: vals[i][3],
               at: vals[i][4], status: vals[i][5],
               details: Array.isArray(details) ? details : [] };
    }
  }
  return null;
}

// ── Web app ────────────────────────────────────────────────────

function doGet(e) {
  // Apps Script allows exactly ONE doGet per project, so every page in this
  // project is routed from here.
  //   ?view=status → the pipeline dashboard   (status.gs)
  //   ?view=review → the approval screen      (review.gs)
  // No parameter → Selene Picks, the teammate shortlist.
  if (e && e.parameter && e.parameter.view === 'status') {
    return doGetStatus_();
  }
  if (e && e.parameter && e.parameter.view === 'review') {
    return doGetReview_();
  }
  var data;
  try { data = loadLatestShortlist_(); }
  catch (e) { return htmlMsg_('Selene Picks', 'Could not load the shortlist: ' + e.message); }
  if (!data) {
    return htmlMsg_('Selene Picks',
      'No shortlist is published yet — check back after the Monday research run.');
  }
  var winner = weekWinner_(data.week);
  // ?preview=1 — look at the full page even after the week is locked.
  // Renders the shortlist with submitting disabled; nothing is written.
  var preview = !!(e && e.parameter && e.parameter.preview === '1');
  var state = pkState_(data, preview ? null : winner);
  if (preview) state.preview = winner ? ('this week is already picked by ' + winner.picker + ' — submitting is off') : 'preview mode — submitting is off';
  return HtmlService.createHtmlOutput(pkPageHtml_(state))
    .setTitle('Selene Dreams Research Picks — week of ' + data.week)
    .addMetaTag('viewport', 'width=device-width, initial-scale=1, viewport-fit=cover');
}

/** Called from the page. picks = [{n, slides:[1-based indexes]}] */
function submitPicks(name, week, picks) {
  name = String(name || '').trim();
  if (!name) return { ok: false, error: 'Please enter your name.' };
  if (!picks || !picks.length) return { ok: false, error: 'Choose at least one image.' };
  var totalImgs = 0;
  picks.forEach(function (p) { totalImgs += (p.slides || []).length; });
  if (totalImgs > WEEKLY_IMAGE_CAP) {
    return { ok: false, error: 'That is ' + totalImgs + ' images — the weekly cap is ' +
             WEEKLY_IMAGE_CAP + '. Anything over it should be saved for next week.' };
  }

  var data = loadLatestShortlist_();
  if (!data || String(data.week) !== String(week)) {
    return { ok: false, error: 'A newer shortlist is live — refresh the page.' };
  }

  // Two sources feed one list of rows: this week's shortlist, and the shelf of
  // images saved in earlier weeks (ids prefixed "S"). Both resolve to the same
  // pick payload, so nothing downstream needs to tell them apart.
  var byId = {};
  data.entries.forEach(function (e) { byId[String(e.n)] = { kind: 'week', e: e }; });
  var shelf = shelfLoad_();
  var carried = shelf.items.slice(-SHELF_RENDER_MAX).reverse();
  carried.forEach(function (it, k) { byId['S' + k] = { kind: 'shelf', e: it }; });

  // Selection is per image now, so every pick must name its slides.
  for (var i = 0; i < picks.length; i++) {
    var p = picks[i], row = byId[String(p.n)];
    if (!row) return { ok: false, error: 'Unknown selection "' + p.n + '" — refresh the page.' };
    if (!p.slides || !p.slides.length) {
      return { ok: false, error: 'Choose at least one image per post.' };
    }
    if (p.slides.length > MAX_SLIDES) {
      return { ok: false, error: 'At most ' + MAX_SLIDES + ' images per post.' };
    }
  }

  var lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    var winner = weekWinner_(week);
    if (winner) {
      return { ok: false, locked: true,
               error: 'Too slow — ' + winner.picker + ' already picked this week.' };
    }

    var labels = [], slidesStr = [], usedShelfIds = [];
    var payloadPicks = picks.map(function (p) {
      var row = byId[String(p.n)], e = row.e;
      if (row.kind === 'shelf') {
        // Archived bytes in the repo; prompt_runner fetches "repo:" paths with
        // its own token, because the CDN links these came from are long dead.
        var urls = p.slides.map(function (i) {
          var sl = e.slides[i - 1];
          return sl ? 'repo:' + sl.archive : null;
        }).filter(Boolean);
        labels.push('saved ' + e.week + '#' + e.n);
        slidesStr.push('saved ' + e.week + '#' + e.n + ': ' + p.slides.join(','));
        usedShelfIds.push(e.id);
        return { n: e.n, postUrl: e.postUrl,
                 concept: (e.concept || '') + ' [carried over from ' + e.week + ']',
                 product: e.product, slideUrls: urls };
      }
      var imgs = e.images || [];
      labels.push(String(e.n));
      slidesStr.push('#' + e.n + ': ' + p.slides.join(','));
      return { n: e.n, postUrl: e.postUrl, concept: e.concept || '',
               product: e.product,
               slideUrls: p.slides.map(function (i) { return imgs[i - 1]; })
                 .filter(Boolean) };
    });

    var payload = { secret: WEBHOOK_SECRET, week: week, picker: name,
                    picks: payloadPicks };

    var status = 'PENDING — Mac offline; ask Claude to run the pending pick';
    try {
      var resp = UrlFetchApp.fetch(WEBHOOK_URL.replace('/webhook', '/select'), {
        method: 'post', contentType: 'application/json',
        payload: JSON.stringify(payload), muteHttpExceptions: true,
        followRedirects: true,
        headers: { 'ngrok-skip-browser-warning': 'true' }
      });
      if (resp.getResponseCode() === 200) status = 'Prompts generating…';
      else Logger.log(relayResult_('Pick submission', week, resp));
    } catch (e) {
      Logger.log('Pick submission relay THREW for week ' + week + ': ' + e);
    }

    picksSheet_().appendRow([
      week, name, labels.join(', '), slidesStr.join(' · ') || '—',
      Utilities.formatDate(new Date(),
        SpreadsheetApp.getActiveSpreadsheet().getSpreadsheetTimeZone(),
        'yyyy-MM-dd HH:mm'),
      status, JSON.stringify(payload.picks)
    ]);

    // A shelf item that has now been used comes off the shelf.
    if (usedShelfIds.length) {
      try {
        var keep = shelf.items.filter(function (it) {
          return usedShelfIds.indexOf(it.id) === -1;
        });
        ghPutBase64_(SHELF_PATH,
          Utilities.base64Encode(Utilities.newBlob(
            JSON.stringify({ items: keep }, null, 1)).getBytes()),
          'Shelf: used ' + usedShelfIds.length + ' in week ' + week, shelf.sha);
      } catch (e) { /* the pick already landed; the shelf can be tidied later */ }
    }
    return { ok: true, status: status };
  } finally {
    lock.releaseLock();
  }
}

// ── Monday invite email ────────────────────────────────────────

function installEmailTrigger() {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === 'sendPickInvite') ScriptApp.deleteTrigger(t);
  });
  // Every 15 min; sendPickInvite exits instantly unless a NEW shortlist has
  // just been published — so the invite lands within ~15 min of the Monday
  // research run finishing, automatically.
  ScriptApp.newTrigger('sendPickInvite').timeBased().everyMinutes(15).create();
  Logger.log('Invite trigger installed — checks every 15 min, emails once per new shortlist.');
}

/**
 * Vision-screening relay (2026-08-12): the Monday research agent publishes
 * candidates/candidates-DATE.json; the Mac must view+score the images before
 * a shortlist exists. This runs on the same 15-min tick as the invite email:
 * if candidates exist for a week with no shortlist yet, poke the Mac's
 * /screen endpoint. Safe to call repeatedly — the Mac dedupes and skips if
 * the shortlist is already pushed.
 */
/**
 * Weekly research relay (2026-08-12): the cloud environment is blocked from
 * Apify, so Monday research now runs ON THE MAC. On every 15-min tick from
 * Monday 09:00 through Tuesday, if this week's candidates file doesn't exist
 * yet, poke the Mac's /research endpoint. The Mac dedupes (skips if already
 * running or already published) — so this self-heals if the Mac was off.
 */
/**
 * Relay calls use muteHttpExceptions, so an unreachable Mac does NOT throw:
 * ngrok's edge answers 404 for a domain with no live tunnel, and a bad host
 * under *.ngrok-free.dev still resolves because that zone is a wildcard. A
 * relay that reached nobody therefore looks identical to one that worked
 * unless the status code is logged. Log it.
 */
/**
 * DIAGNOSTIC — run from the editor to prove the relay path end to end.
 * Reports the REAL HTTP status of a call to the Mac instead of assuming one.
 * 200 = tunnel up and Flask answering. 404 from ngrok = WEBHOOK_URL points at
 * a domain with no live tunnel (or is still a placeholder — see trigger.gs
 * v3.2). A throw = the host does not resolve at all.
 */
function pingMac() {
  var url = WEBHOOK_URL.replace('/webhook', '/health');
  try {
    var resp = UrlFetchApp.fetch(url, {
      method: 'get', muteHttpExceptions: true, followRedirects: true,
      headers: { 'ngrok-skip-browser-warning': 'true' }
    });
    Logger.log('pingMac ' + url + ' -> HTTP ' + resp.getResponseCode() +
               ' | ' + String(resp.getContentText() || '').slice(0, 200));
  } catch (e) {
    Logger.log('pingMac ' + url + ' -> THREW (host unreachable): ' + e);
  }
}

function relayResult_(what, week, resp) {
  var code = resp.getResponseCode();
  if (code === 200) return what + ' relay OK (200) for week ' + week;
  return what + ' relay FAILED for week ' + week + ' — HTTP ' + code +
         ' from ' + WEBHOOK_URL + ' — body: ' +
         String(resp.getContentText() || '').slice(0, 200);
}

function requestResearchIfNeeded_() {
  var tz = SpreadsheetApp.getActiveSpreadsheet().getSpreadsheetTimeZone();
  var now = new Date();
  var dow = parseInt(Utilities.formatDate(now, tz, 'u'), 10);  // 1=Mon
  var hour = parseInt(Utilities.formatDate(now, tz, 'H'), 10);
  if (!(dow === 1 && hour >= 10) && dow !== 2) return;  // Mon 10:00 → Tue only
  // This week's Monday date
  var monday = new Date(now.getTime() - ((dow - 1) * 24 * 3600 * 1000));
  var week = Utilities.formatDate(monday, tz, 'yyyy-MM-dd');
  try {
    ghFetch_('https://api.github.com/repos/' + PICKER_REPO +
      '/contents/candidates/candidates-' + week + '.json?ref=' + PICKER_BRANCH);
    return;   // already published
  } catch (e) { /* not yet — poke the Mac */ }
  try {
    var rResp = UrlFetchApp.fetch(WEBHOOK_URL.replace('/webhook', '/research'), {
      method: 'post', contentType: 'application/json',
      payload: JSON.stringify({ secret: WEBHOOK_SECRET }),
      muteHttpExceptions: true, followRedirects: true,
      headers: { 'ngrok-skip-browser-warning': 'true' }
    });
    Logger.log(relayResult_('Research', week, rResp));
  } catch (e) {
    Logger.log('Research relay THREW (no response at all) for week ' +
               week + ': ' + e);
  }
}

function requestScreeningIfNeeded_() {
  var listing;
  try {
    listing = JSON.parse(ghFetch_('https://api.github.com/repos/' + PICKER_REPO +
      '/contents/candidates?ref=' + PICKER_BRANCH));
  } catch (e) { return; }   // no candidates dir yet
  var files = listing.filter(function (f) {
    return f.type === 'file' && /^candidates-\d{4}-\d{2}-\d{2}\.json$/.test(f.name);
  }).sort(function (a, b) { return a.name < b.name ? 1 : -1; });
  if (!files.length) return;
  var week = files[0].name.replace(/^candidates-|\.json$/g, '');
  // Shortlist already produced for that week?
  try {
    ghFetch_('https://api.github.com/repos/' + PICKER_REPO +
      '/contents/' + SHORTLIST_DIR + '/shortlist-' + week + '.json?ref=' + PICKER_BRANCH);
    return;   // exists — screening done
  } catch (e) { /* not yet — fall through */ }
  try {
    var sResp = UrlFetchApp.fetch(WEBHOOK_URL.replace('/webhook', '/screen'), {
      method: 'post', contentType: 'application/json',
      payload: JSON.stringify({ week: week, secret: WEBHOOK_SECRET }),
      muteHttpExceptions: true, followRedirects: true,
      headers: { 'ngrok-skip-browser-warning': 'true' }
    });
    Logger.log(relayResult_('Screening', week, sResp));
  } catch (e) {
    Logger.log('Screening relay THREW (no response at all) for week ' +
               week + ': ' + e);
  }
}


// ── Web app URL ────────────────────────────────────────────────
// ScriptApp.getService().getUrl() returns the /dev URL in several execution
// contexts (editor runs, some trigger contexts). The /dev URL requires EDIT
// access on the script, so a teammate clicking it lands on a Google Drive
// error page instead of the picker — which is exactly what happened on
// 2026-08-13. The two URLs are not interchangeable: /dev keys off the script
// ID, /exec off the deployment ID, so one cannot be derived from the other.
//
// SETUP (once): Deploy > Manage deployments > copy the Web app /exec URL,
// then Project Settings > Script Properties > add PICKER_URL = that URL.
/**
 * The Flow Hub link printed at the top of every Weekly Action email.
 * Script Property FLOW_HUB_URL wins, so the destination can change without
 * a redeploy; the fallback is the pinned Flow Hub artifact.
 */
function pkFlowHub_() {
  return PropertiesService.getScriptProperties().getProperty('FLOW_HUB_URL') ||
         'https://claude.ai/code/artifact/0c53a3c8-42fb-456f-92ab-595922714512';
}

/** 'MM/DD/YYYY' in the spreadsheet's timezone. */
function pkToday_() {
  var tz = SpreadsheetApp.getActiveSpreadsheet().getSpreadsheetTimeZone();
  return Utilities.formatDate(new Date(), tz, 'MM/dd/yyyy');
}

/** Distinct sources on the shortlist, for the 'where they are from' line. */
function pkSources_(entries) {
  var seen = {}, out = [];
  (entries || []).forEach(function (e) {
    var src = String(e && e.source || '').trim();
    if (!src || seen[src]) return;
    seen[src] = 1; out.push(src);
  });
  return out;
}

function pickerUrl_() {
  var stored = PropertiesService.getScriptProperties().getProperty('PICKER_URL');
  if (stored) return stored;
  var url = ScriptApp.getService().getUrl() || '';
  if (url.indexOf('/exec') > -1) return url;
  return null;   // a /dev URL is worse than no email — never send one out
}

// Clear the "already invited" flag so an invite can be re-sent for a week.
function resetInvite(week) {
  week = week || (loadLatestShortlist_() || {}).week;
  PropertiesService.getScriptProperties().deleteProperty('INVITED_' + week);
  Logger.log('Invite flag cleared for ' + week + ' — sendPickInvite will resend.');
}

function sendPickInvite() {
  requestResearchIfNeeded_();
  requestScreeningIfNeeded_();
  if (!TEAMMATE_EMAILS.length) { Logger.log('No TEAMMATE_EMAILS set.'); return; }
  var data;
  try { data = loadLatestShortlist_(); } catch (e) { return; }
  if (!data) return;                                   // no shortlist yet
  var props = PropertiesService.getScriptProperties();
  if (props.getProperty('INVITED_' + data.week)) return;   // already invited
  if (weekWinner_(data.week)) return;                  // already picked
  var url = pickerUrl_();
  if (!url) {
    Logger.log('NOT SENDING: no /exec URL available. Set Script Property ' +
               'PICKER_URL to the web app URL from Manage deployments. ' +
               'The invite will send itself once that exists.');
    return;                       // no INVITED_ flag set, so this retries
  }
  var srcs = pkSources_(data.entries);
  var from = srcs.length
    ? 'Sourced from ' + srcs.slice(0, 6).join(', ') +
      (srcs.length > 6 ? ' and ' + (srcs.length - 6) + ' more.' : '.')
    : '';
  var brief = 'This week\'s shortlist is up (<b>' + data.entries.length +
              ' posts</b>), ranked by brand fit.' + (from ? ' ' + from : '');
  MailApp.sendEmail({
    to: TEAMMATE_EMAILS.join(','),
    subject: '[SELENE DREAMS] Weekly Action - Content Picker',
    htmlBody:
      'Date: ' + pkToday_() + '<br>' +
      'Flow Hub: <a href="' + pkFlowHub_() + '">' + pkFlowHub_() + '</a><br><br>' +
      '<b>Weekly Brief:</b><br>' + brief + '<br><br>' +
      '<a href="' + url + '"><b>Open the picker</b></a> — up to ' +
      WEEKLY_IMAGE_CAP + ' images, first submission wins.'
  });
  props.setProperty('INVITED_' + data.week, '1');
  Logger.log('Invite sent for week ' + data.week + '.');
}

// ── HTML rendering ─────────────────────────────────────────────


// ── Page state ─────────────────────────────────────────────────
// Everything the page needs, as one JSON object. Rendering is client-side
// (pkJs_) so desktop and mobile share one template.

function htmlMsg_(title, msg) {
  return HtmlService.createHtmlOutput(
    '<body style="font-family:Archivo,-apple-system,sans-serif;background:#F5F3EF;display:flex;' +
    'justify-content:center;padding:80px 16px 0;color:#273F22"><div style="max-width:420px;' +
    'background:#fff;border:2px solid #273F22;border-radius:12px;' +
    'padding:24px;text-align:center"><h2 style="font-size:18px;margin:0 0 10px">' + title +
    '</h2><p style="font-size:13.5px;line-height:1.6;margin:0">' + msg +
    '</p></div></body>').setTitle(title);
}

function prodStr_(p) {
  if (!p) return '';
  if (typeof p === 'string') return p;
  return [p.fabric, p.productType, p.variant].filter(Boolean).join(' · ');
}
function fabricOf_(p) {
  if (!p) return '';
  if (typeof p === 'string') return String(p.split('·')[0] || '').trim();
  return String(p.fabric || '').trim();
}

function pkState_(data, winner) {
  var entries = (data.entries || []).slice().sort(function (a, b) {
    return (Number(b.brandScore) || 0) - (Number(a.brandScore) || 0);
  });
  var srcByN = {};
  var fabrics = [];
  var rows = entries.map(function (e, k) {
    srcByN[String(e.n)] = e.source || '';
    var fab = fabricOf_(e.product);
    if (fab && fabrics.indexOf(fab) === -1) fabrics.push(fab);
    return {
      id: String(e.n), kind: 'week', rank: k + 1,
      origN: (e.origN != null ? String(e.origN) : ''),
      archiveWeek: e.archiveWeek || '',
      source: e.source || '', heldFrom: e.carriedFrom || '',
      images: e.images || [],
      caption: e.caption || e.concept || '', rationale: e.brandRationale || '',
      postUrl: e.postUrl || '', product: prodStr_(e.product), fabric: fab,
      score: e.brandScore || '', likes: e.likes, comments: e.comments,
      engagement: e.engagement || '', type: e.type || ''
    };
  });

  var shelfRows = [];
  if (!winner) {
    var shelf = shelfLoad_();
    var carried = shelf.items.slice(-SHELF_RENDER_MAX).reverse();
    carried.forEach(function (it, k) {
      var imgs = it.slides.map(function (sl) { return ghDataUrl_(sl.archive); })
        .filter(function (u) { return u; });
      if (!imgs.length) return;
      var fab = fabricOf_(it.product);
      if (fab && fabrics.indexOf(fab) === -1) fabrics.push(fab);
      shelfRows.push({
        id: 'S' + k, kind: 'shelf', rank: 0, origN: '', archiveWeek: '',
        source: it.source || '', heldFrom: '',
        savedTag: 'saved ' + (it.savedAt || it.week) + ' · by ' + (it.savedBy || '—'),
        images: imgs, caption: it.caption || it.concept || '', rationale: '',
        postUrl: it.postUrl || '', product: prodStr_(it.product), fabric: fab,
        score: it.brandScore || '', likes: '', comments: '', engagement: '', type: ''
      });
    });
  }

  var win = null;
  if (winner) {
    var tiles = [];
    (winner.details || []).forEach(function (p) {
      (p.slideUrls || []).forEach(function (u) {
        tiles.push({ url: String(u || ''), handle: srcByN[String(p.n)] || prodStr_(p.product) || ('#' + p.n) });
      });
    });
    var at = winner.at;
    if (Object.prototype.toString.call(at) === '[object Date]') {
      at = Utilities.formatDate(at, SpreadsheetApp.getActiveSpreadsheet().getSpreadsheetTimeZone(), 'yyyy-MM-dd HH:mm');
    }
    win = { picker: String(winner.picker || ''), posts: String(winner.posts || ''),
            slides: String(winner.slides || ''), at: String(at || ''),
            status: String(winner.status || ''), tiles: tiles };
  }

  return {
    build: PICKER_BUILD, week: String(data.week), cap: WEEKLY_IMAGE_CAP, maxSlides: MAX_SLIDES,
    count: entries.length, fabrics: fabrics, entries: rows, shelf: shelfRows, winner: win
  };
}

function pkPageHtml_(state) {
  var json = JSON.stringify(state).replace(/<\//g, '<\\/');
  return '<!DOCTYPE html><html><head><meta charset="utf-8">' +
    '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">' +
    '<link rel="preconnect" href="https://fonts.googleapis.com">' +
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>' +
    '<link href="https://fonts.googleapis.com/css2?family=Archivo:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">' +
    '<style>' + pkCss_() + '</style></head><body>' +
    '<div id="app"></div>' +
    '<div id="sheetwrap" class="sheetwrap" hidden><div class="scrim" data-close="1"></div><div id="sheet" class="sheet"></div></div>' +
    '<div id="lb" class="lb" hidden></div>' +
    '<div id="toast" class="toast"></div>' +
    '<script>var PK_STATE=' + json + ';</script>' +
    '<script>' + pkJs_() + '</script>' +
    '</body></html>';
}

function esc_(s) {
  return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

// ── CSS ─────────────────────────────────────────────────────────
function pkCss_() { return `
*{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#F5F3EF;--ink:#273F22;--soft:#6f7768;--line:#ded9cc;--ecru:#E8E4D8;--sage:#7C896F;
--wedge:#335875;--apr:#b8552f;--gold:#8a6d3b;--goldbg:#faf6ec;--goldline:#d8c9a8;--danger:#c2492f;--dim:#9a9384;--mut:#f1efe8;
--sans:Archivo,-apple-system,"Segoe UI",system-ui,sans-serif;--mono:"IBM Plex Mono",ui-monospace,Menlo,monospace}
html,body{background:#e9e6df;color:var(--ink);font-family:var(--sans);-webkit-text-size-adjust:100%}
button{font:inherit;cursor:pointer;color:inherit;background:none;border:0}
a{color:var(--wedge)}
.lab{font:600 9.5px/1 var(--mono);color:var(--soft);text-transform:uppercase;letter-spacing:.11em}
.stripe{background:repeating-linear-gradient(45deg,#E8E4D8 0 7px,#efece3 7px 14px)}
@keyframes spin{to{transform:rotate(360deg)}}
.spin{width:18px;height:18px;border-radius:50%;border:2px solid var(--line);border-top-color:var(--sage);animation:spin .9s linear infinite;flex:none}
.btn{display:inline-flex;align-items:center;justify-content:center;gap:7px;height:42px;padding:0 18px;border-radius:8px;font:600 13px/1 var(--sans);white-space:nowrap;border:1.5px solid var(--ink);background:var(--ink);color:var(--bg)}
.btn.soft{background:transparent;border-color:var(--line);color:var(--soft)}
.btn.link{border:0;background:none;color:var(--soft);text-decoration:underline;text-underline-offset:3px;font-weight:500;padding:0 6px}
.btn:disabled{background:#c9c6bd;border-color:#c9c6bd;color:#f2f0ea;cursor:not-allowed}
.page{max-width:1240px;margin:0 auto;background:var(--bg);min-height:100vh;box-shadow:0 0 0 1px #d8d3c6}
/* header */
.hd{padding:26px 30px 0}
.hdrow{display:flex;align-items:flex-end;justify-content:space-between;gap:24px;border-bottom:2px solid var(--ink);padding-bottom:14px}
.ttl{font:600 24px/1.1 var(--sans);letter-spacing:-.01em}
.hd .sub{font:500 11px/1 var(--mono);color:var(--soft);margin-top:7px;text-transform:uppercase;letter-spacing:.09em}
.meter{display:flex;align-items:center;gap:14px;flex:none}
.meter .lab{white-space:nowrap}
.slots{display:flex;gap:3px;align-items:center}
.slots i{width:13px;height:22px;border-radius:2px;border:1px solid var(--line);background:#fff;display:block}
.slots i.on{background:var(--ink);border-color:var(--ink)}
.slots i.gap{width:9px;border:0;background:none}
.slots i.over{background:var(--gold);border-color:var(--gold);opacity:.85}
.mcount{font:600 15px/1 var(--sans);white-space:nowrap}
.mcount b{font:600 15px/1 var(--mono)}.mcount span{color:var(--soft)}.mcount em{font:500 13px/1 var(--mono);color:var(--gold);font-style:normal}
.rules{display:flex;gap:10px;padding:14px 30px 0;flex-wrap:wrap}
.rule{display:flex;align-items:center;gap:8px;background:#fff;border:1px solid var(--line);border-radius:20px;padding:6px 13px 6px 7px;font:400 12px/1.2 var(--sans)}
.rule i{width:18px;height:18px;border-radius:50%;background:var(--ink);color:var(--bg);font:600 9.5px/18px var(--mono);text-align:center;font-style:normal;flex:none}
.help{display:none}
.preview{margin:14px 30px 0;background:#faf6ec;border:1px dashed var(--goldline);color:var(--gold);border-radius:8px;padding:9px 13px;font:600 11px/1.4 var(--mono);letter-spacing:.05em}
/* sticky bar */
.bar{position:sticky;top:0;z-index:6;margin-top:16px;padding:12px 30px;background:var(--bg);border-top:1px solid var(--line);border-bottom:2px solid var(--ink);display:flex;align-items:center;gap:16px;flex-wrap:wrap}
.name{display:flex;align-items:center;gap:9px}
.name input{background:#fff;border:2px solid var(--line);border-radius:7px;padding:8px 12px;font:500 13px/1 var(--sans);min-width:150px;color:var(--ink);height:38px}
.name input.ok{border-color:var(--sage)}.name input.bad{border-color:#dda99a}
.vsep{width:1px;height:26px;background:var(--line)}
.cnt{font:400 12.5px/1.4 var(--sans);flex:none;white-space:nowrap}.cnt b{font-weight:600}.cnt span{color:var(--gold)}
.bar .sp{flex:1}
.bar .acts{display:flex;gap:10px;align-items:center;flex:none}
.err{font:500 12px/1.5 var(--sans);color:var(--danger);width:100%}
.hint{font:500 11.5px/1.5 var(--mono);color:var(--soft);width:100%}
.err:empty,.hint:empty{display:none}
/* filters */
.filters{padding:10px 30px 6px;display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.chip{border:1px solid var(--line);background:#fff;color:var(--ink);border-radius:5px;padding:6px 10px;font:500 11.5px/1 var(--sans);cursor:pointer;white-space:nowrap}
.chip.on{background:var(--ink);border-color:var(--ink);color:var(--bg)}
/* sections */
.sect{padding:16px 30px 0;display:flex;align-items:center;gap:10px}
.sect .lab{letter-spacing:.13em}.sect.gold .lab{color:var(--gold)}
.sect span:last-child{flex:1;height:1px;background:#e2ddd0}
.list{padding:10px 30px 0;display:flex;flex-direction:column;gap:18px}
.post{background:#fff;border:2px solid var(--line);border-radius:16px;padding:22px 24px}
.post.hidden{display:none}
.post.shelf{background:var(--goldbg);border:2px dashed var(--goldline)}
.ph{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap}
.rank{background:var(--ecru);color:var(--ink);border-radius:5px;padding:4px 9px;font:600 10.5px/1 var(--mono);text-transform:uppercase;letter-spacing:.06em}
.rank.top{background:var(--ink);color:var(--bg)}
.ptitle{font:600 16px/1 var(--sans)}
.src{font:500 13px/1 var(--mono);color:var(--wedge)}.src.tag{color:var(--apr)}
.held{background:var(--goldbg);border:1px solid var(--goldline);color:var(--gold);border-radius:4px;padding:3px 8px;font:600 10px/1.3 var(--mono)}
.saved{background:var(--gold);color:var(--bg);border-radius:4px;padding:4px 9px;font:600 10px/1 var(--mono)}
.savednote{font:500 11px/1 var(--mono);color:var(--gold)}
.ph .sp{flex:1}
.capdots{display:flex;align-items:center;gap:12px}
.capdots .d{display:flex;gap:3px}.capdots .d i{width:7px;height:7px;border-radius:50%;background:#dcd8ce;display:block}.capdots .d i.on{background:var(--ink)}
.capdots .t{font:500 11px/1 var(--mono);color:var(--soft)}.capdots .t.full{color:var(--gold)}
.stats{display:flex;gap:7px;flex-wrap:wrap;margin-top:13px}
.stat{background:#faf9f5;color:var(--soft);border:1px solid var(--line);border-radius:4px;padding:4px 8px;font:500 11px/1 var(--mono)}
.stat.blue{background:#e7edf3;color:var(--wedge);border-color:#c8d6e2}.stat.green{background:#e9efe6;color:#3d6b34;border-color:#cbd9c4}
.two{display:flex;gap:20px;margin-top:16px;align-items:flex-start}
.two>div{flex:1;min-width:0}
.capq{background:var(--bg);border-left:3px solid var(--sage);padding:11px 14px;border-radius:0 6px 6px 0}
.capq .lab,.why .lab{display:block;margin-bottom:6px}
.capq p{font:400 12.5px/1.55 var(--sans);white-space:pre-wrap}
.why p{font:400 12.5px/1.55 var(--sans);color:var(--soft)}
.why a{display:inline-block;margin-top:8px;font:500 12px/1 var(--sans)}
.twotg{display:none}
.strip{display:flex;align-items:center;gap:9px;margin:18px 0 9px}
.strip span:nth-child(2){flex:1;height:1px;background:var(--line)}
.strip .capnote{font:500 10px/1 var(--mono);color:var(--gold)}
.tiles{display:grid;grid-template-columns:repeat(auto-fill,minmax(155px,1fr));gap:12px}
.tiles>.tile{min-width:0}
.tile{position:relative;aspect-ratio:4/5;border:3px solid var(--line);border-radius:12px;overflow:hidden;background:var(--mut);cursor:pointer;transition:border-color .12s,transform .12s}
.tile:hover{border-color:var(--sage);transform:translateY(-2px)}
.tile img{width:100%;height:100%;object-fit:cover;display:block}
.tile.sel{border-color:var(--ink)}.tile.over{border:3px dashed var(--gold);opacity:.92}
.tile.lock{border-color:#e4e0d6;cursor:not-allowed}.tile.lock:hover{transform:none;border-color:#e4e0d6}
.tile.gone{opacity:.45;cursor:not-allowed;border-color:#e4e0d6}.tile.gone:hover{transform:none}
.tile.rec{cursor:default}
.veil{position:absolute;inset:0;background:rgba(39,63,34,.4);display:none}
.tile.sel .veil{display:block}.tile.over .veil{display:block;background:rgba(138,109,59,.26)}
.tile .n{position:absolute;top:7px;left:7px;background:rgba(255,255,255,.92);border-radius:4px;padding:2px 6px;font:600 9.5px/1.5 var(--mono);color:var(--soft)}
.tile .ob{position:absolute;top:7px;right:7px;background:var(--ink);color:var(--bg);border-radius:5px;padding:3px 8px;font:600 10.5px/1.3 var(--mono);display:none}
.tile.sel .ob,.tile.over .ob{display:block}.tile.over .ob{background:var(--gold)}
.tile .lbl{position:absolute;bottom:8px;left:8px;background:var(--bg);color:var(--ink);border-radius:4px;padding:3px 7px;font:500 9px/1.3 var(--mono);display:none}
.tile.sel .lbl,.tile.over .lbl{display:block}.tile.over .lbl{background:var(--gold);color:var(--bg)}
.tile .zm{position:absolute;bottom:8px;right:8px;width:26px;height:26px;border-radius:6px;background:rgba(255,255,255,.9);border:1px solid var(--line);color:var(--ink);font:500 12px/24px var(--mono);text-align:center;opacity:0;transition:opacity .12s}
.tile:hover .zm{opacity:1}
.tile .st{position:absolute;inset:0;display:none;flex-direction:column;align-items:center;justify-content:center;gap:9px;text-align:center;padding:8px}
.tile .st .t{font:500 9.5px/1.3 var(--mono);color:var(--soft)}
.tile.rec .st.rec{display:flex;background:var(--mut)}
.tile.gone .st.gone{display:flex;background:#f4f2ec}.tile.gone .st.gone .t{font-weight:600;color:var(--danger)}
.tile.lock .st.lock{display:flex;background:rgba(244,242,236,.72)}
.tile.lock .st.lock .t{background:var(--ink);color:var(--bg);border-radius:6px;padding:7px 9px;font:500 9.5px/1.4 var(--mono);margin:0 8px}
.foot{text-align:center;font:400 10.5px/1.6 var(--mono);color:var(--dim);padding:26px 16px}
/* terminal views */
.term{max-width:600px;margin:0 auto;padding:44px 40px}
.term .h{font:600 22px/1.2 var(--sans);text-align:center}
.term .l1{font:400 13.5px/1.6 var(--sans);text-align:center;margin-top:12px}
.term .l2{font:400 13.5px/1.6 var(--sans);text-align:center;margin-top:4px;color:var(--gold)}
.term .l2.soft{color:var(--soft);font:500 11.5px/1.6 var(--mono)}
.tgrid{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:8px;margin-top:26px}
.tgrid>div{min-width:0}
.tgrid .c{aspect-ratio:4/5;border:1px solid var(--line);border-radius:7px;overflow:hidden;width:100%}
.tgrid .c img{width:100%;height:100%;object-fit:cover;display:block}
.tgrid .hn{font:500 8px/1.5 var(--mono);color:var(--dim);margin-top:4px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.term .ft{text-align:center;font:400 12px/1.5 var(--sans);color:var(--soft);margin-top:24px;border-top:1px solid #e2ddd0;padding-top:18px}
/* lightbox */
.lb{position:fixed;inset:0;background:#141a12;z-index:60;display:flex;align-items:center;justify-content:center}
.lb[hidden]{display:none}
.lb img{max-width:92vw;max-height:88vh;border-radius:6px;display:block}
.lb .x{position:absolute;top:22px;right:24px;border:1.5px solid rgba(245,243,239,.5);color:#F5F3EF;border-radius:7px;padding:9px 16px;font:600 12px/1 var(--sans)}
.lb .info{position:absolute;top:24px;left:26px;font:500 11px/1.6 var(--mono);color:rgba(245,243,239,.66)}
.lb .nav{position:absolute;top:50%;transform:translateY(-50%);width:46px;height:46px;border-radius:50%;background:rgba(245,243,239,.12);border:1px solid rgba(245,243,239,.28);color:#F5F3EF;font:400 17px/1 var(--sans)}
.lb .nav.l{left:26px}.lb .nav.r{right:26px}
.lb .bot{position:absolute;bottom:22px;left:0;right:0;text-align:center;padding:0 16px}
.lb .cnt2{font:500 12px/1 var(--mono);color:rgba(245,243,239,.7);margin-bottom:14px}
.lb .selbtn{height:50px;padding:0 22px;background:#F5F3EF;color:var(--ink);border-radius:9px;font:600 14.5px/50px var(--sans)}
.lb .selbtn.on{background:var(--ink);color:#F5F3EF;border:1.5px solid rgba(245,243,239,.5)}
.lb .selbtn:disabled{opacity:.4}
.lb .esc{font:400 10.5px/1.5 var(--mono);color:rgba(245,243,239,.45);margin-top:10px}
/* sheet + toast */
.sheetwrap{position:fixed;inset:0;z-index:50}.sheetwrap[hidden]{display:none}
.scrim{position:absolute;inset:0;background:rgba(20,26,18,.42)}
.sheet{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);width:min(420px,calc(100vw - 32px));max-height:88vh;overflow:auto;background:var(--bg);border:2px solid var(--ink);border-radius:12px;padding:22px}
.sheet .grab{display:none}
.sheet .h{font:600 17px/1.2 var(--sans)}
.sheet .rl{display:flex;flex-direction:column;gap:14px;margin-top:16px}
.sheet .rl div{display:flex;gap:11px;align-items:flex-start;font:400 13.5px/1.5 var(--sans)}
.sheet .rl i{width:22px;height:22px;flex:none;border-radius:50%;background:var(--ink);color:var(--bg);font:600 11px/22px var(--mono);text-align:center;font-style:normal}
.sheet .p{font:400 12px/1.5 var(--sans);color:var(--soft);margin-top:16px;border-top:1px solid #e2ddd0;padding-top:14px}
.sheet .full{width:100%;margin-top:18px;height:48px}
.toast{position:fixed;left:50%;bottom:22px;transform:translate(-50%,300%);opacity:0;background:var(--ink);color:#fff;font:500 12.5px/1.4 var(--sans);padding:13px 18px;border-radius:12px;transition:transform .22s ease;max-width:88vw;z-index:99;display:flex;align-items:center;gap:14px}
.toast.show{transform:translate(-50%,0);opacity:1}.toast.bad{background:var(--danger)}
.toast button{color:#fff;font:600 13px/1 var(--sans);text-decoration:underline;text-underline-offset:3px}
@media(prefers-reduced-motion:reduce){.toast,.tile{transition:none}}
/* ── MOBILE ── */
@media(max-width:899px){
  html,body{background:var(--bg)}
  .page{box-shadow:none;padding-bottom:calc(90px + env(safe-area-inset-bottom))}
  .hd{position:sticky;top:0;z-index:7;background:var(--bg);padding:0 14px;border-bottom:2px solid var(--ink)}
  .hdrow{border:0;padding:0;height:56px;align-items:center;gap:10px}
  .ttl{font-size:15px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .ttl small{color:var(--soft);font-weight:500;font-size:15px}
  .hd .sub{margin-top:2px;font-size:9.5px;text-transform:uppercase;letter-spacing:.07em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .meter{gap:7px}.meter .lab{display:none}
  .slots{width:52px;height:6px;border-radius:3px;background:#e2ddd0;overflow:hidden;gap:0}
  .slots i{height:6px;width:auto;flex:1;border:0;border-radius:0;background:transparent}
  .slots i.gap{display:none}
  .mcount{font:600 11.5px/1 var(--mono)}.mcount span,.mcount em{display:none}
  .help{display:flex;width:44px;height:44px;align-items:center;justify-content:center;flex:none;margin-right:-8px}
  .help span{width:30px;height:30px;border-radius:50%;border:1.5px solid var(--line);background:#fff;font:600 13px/28px var(--sans);text-align:center;color:var(--soft)}
  .rules{display:none}
  .preview{margin:12px 14px 0}
  .bar{position:static;margin:0;padding:12px 14px 0;border:0;flex-wrap:wrap;gap:6px 8px}
  .bar .name{width:100%}.name input{flex:1;height:44px;font-size:14px}
  .vsep,.bar .cnt,.bar .sp,.bar .acts{display:none}
  .bar .hint{width:100%}
  .filters{padding:12px 14px 0;flex-wrap:nowrap;overflow-x:auto;gap:7px;-webkit-overflow-scrolling:touch}
  .filters .lab{display:none}.chip{height:34px;border-radius:17px;padding:0 13px;font:500 12.5px/32px var(--sans);flex:none}
  .filters .note{display:none}
  .sect{padding:18px 14px 0}.list{padding:9px 14px 0;gap:14px}
  .post{padding:13px 12px;border-radius:14px}
  .ph{gap:7px;align-items:center}.ptitle{display:none}
  .rank{padding:4px 8px;font-size:10px}.src{font-size:11.5px}
  .ph .score{display:inline-block}
  .capdots{gap:5px}.capdots .d i{width:6px;height:6px}.capdots .t{font-size:10.5px}
  .mtitle{display:block;font:600 14.5px/1.25 var(--sans);margin-top:9px}
  .stats{gap:5px;margin-top:9px}.stat{padding:3px 7px;font-size:10px}
  .two{display:none;flex-direction:column;gap:10px;margin-top:6px}
  .post.open .two{display:flex}
  .twotg{display:flex;align-items:center;margin-top:11px;height:44px;border-top:1px solid #ede9df;font:500 12px/1 var(--mono);color:var(--soft)}
  .post.open .twotg{color:var(--ink)}
  .strip{margin:11px 0 6px}.strip .lab{display:none}.strip span:nth-child(2){display:none}
  .tiles{grid-template-columns:repeat(3,minmax(0,1fr));gap:4px}
  .tile{aspect-ratio:1/1;border-width:2px;border-radius:9px}
  .tile:hover{transform:none}
  .tile .n{top:5px;left:5px;padding:1px 5px;font-size:9px}
  .tile .ob{top:5px;right:5px;padding:2px 6px;font-size:9.5px}
  .tile .lbl{bottom:6px;left:5px;padding:2px 5px;font-size:8px}
  .tile .zm{opacity:1;width:26px;height:26px}
  .tile .zmhit{position:absolute;bottom:0;right:0;width:44px;height:44px}
  .tile.lock .st.lock .t{background:none;color:var(--gold);font-size:15px;padding:0}
  .mbar{position:fixed;left:0;right:0;bottom:0;z-index:6;background:var(--bg);border-top:2px solid var(--ink);padding:10px 14px calc(10px + env(safe-area-inset-bottom))}
  .mbar .err{margin-bottom:8px}
  .mbar .row{display:flex;align-items:center;gap:10px}
  .mbar .c1{font:600 12.5px/1.3 var(--sans);white-space:nowrap}
  .mbar .c2{font:500 10.5px/1.35 var(--mono);color:var(--gold);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .mbar .btn.link{padding:0 4px;font-size:11.5px}
  .toast{bottom:calc(104px + env(safe-area-inset-bottom))}
  .mbar .btn.link{flex:none;height:44px}
  .mbar .btn{height:44px;padding:0 16px}
  .term{padding:28px 16px}.term .h{font-size:21px}
  .tgrid{grid-template-columns:repeat(3,minmax(0,1fr));gap:6px;margin-top:24px}.tgrid .c{aspect-ratio:1/1}.tgrid .hn{font-size:8.5px}
  .lb img{max-width:100vw;max-height:70vh;border-radius:4px}
  .lb .x{top:6px;right:6px;border:0;font-size:19px;width:44px;height:44px;padding:0}
  .lb .info{top:20px;left:16px;font-size:10.5px}
  .lb .nav{display:none}
  .lb .selbtn{width:100%}
  .sheet{left:0;right:0;top:auto;bottom:0;transform:none;width:auto;border:0;border-radius:20px 20px 0 0;padding:10px 16px calc(26px + env(safe-area-inset-bottom))}
  .sheet .grab{display:block;width:38px;height:4px;border-radius:2px;background:var(--line);margin:0 auto 16px}
}
@media(min-width:900px){ .mbar{display:none} .mtitle{display:none} .mwk{display:none} }
`; }

// ── Client JS ───────────────────────────────────────────────────
// Rendered client-side from PK_STATE. No backticks or ${ inside this string.
function pkJs_() { return `
var S=PK_STATE, CAP=S.cap, MAXS=S.maxSlides, WEEK=S.week;
var MOBILE=window.matchMedia('(max-width:899px)');
var ROWS=S.shelf.concat(S.entries), BY={}; ROWS.forEach(function(r){BY[r.id]=r;});
var ORDER=[], NAME='', FILTER='all', OPEN={}, IMG={}, LB=null, BUSY=false, DONE=false;
function esc(s){return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}
function pad(n){return (n<10?'0':'')+n;}
function key(id,i){return id+'|'+i;}
function parts(k){var j=k.lastIndexOf('|');return [k.slice(0,j),Number(k.slice(j+1))];}
function toast(msg,bad,undo){var t=document.getElementById('toast');t.innerHTML='<span>'+esc(msg)+'</span>'+(undo?'<button data-act="undo">Undo</button>':'');t.className='toast show'+(bad?' bad':'');clearTimeout(t._h);t._h=setTimeout(function(){t.className='toast';},undo?5000:3400);}
function rowTitle(r){ return r.kind==='shelf'?(r.product||'Saved post'):('Selene Pick '+r.id); }

/* ── selection model: greedy fill honouring the per-post cap ── */
function compute(){ var taken=[],over=[],per={},pos={};
  ORDER.forEach(function(k){ var id=parts(k)[0]; if(taken.length<CAP&&(per[id]||0)<MAXS){ per[id]=(per[id]||0)+1; pos[k]={kind:'taken',idx:taken.length+1}; taken.push(k);} else { pos[k]={kind:'over'}; over.push(k);} });
  return {taken:taken,over:over,per:per,pos:pos}; }
function group(ks){ var m={},out=[]; ks.forEach(function(k){var a=parts(k);(m[a[0]]=m[a[0]]||[]).push(a[1]);}); Object.keys(m).forEach(function(id){out.push({n:id,slides:m[id].sort(function(a,b){return a-b;})});}); return out; }
function imgState(id,i){ return IMG[key(id,i)]||'ok'; }
function isLocked(id,i,c){ return ORDER.indexOf(key(id,i))===-1&&(c.per[id]||0)>=MAXS; }
function pick(id,i){ var st=imgState(id,i); if(st==='gone'||st==='rec') return; var k=key(id,i); var at=ORDER.indexOf(k);
  if(at>-1){ ORDER.splice(at,1); } else { var c=compute(); if(isLocked(id,i,c)){ toast(MAXS+' is the max for one post',true); return; } ORDER.push(k); }
  upd(); }

/* ── render ── */
function render(){ var app=document.getElementById('app');
  if(S.winner){ app.innerHTML=termHtml('This week is picked', esc(S.winner.picker)+' chose posts '+esc(S.winner.posts), S.winner.slides+(S.winner.at?' · '+S.winner.at:''), true, S.winner.tiles, 'Next shortlist lands Monday.'); return; }
  var h='<div class="page"><div class="hd"><div class="hdrow"><div style="min-width:0;flex:1"><div class="ttl">Selene Dreams Research Picks<small class="mwk"> · wk '+esc(WEEK.slice(5))+'</small></div><div class="sub">week of '+esc(WEEK)+' · '+S.count+' posts shortlisted · ranked by brand fit</div></div>';
  h+='<div class="meter"><span class="lab">prompt slots</span><div class="slots" id="slots"></div><div class="mcount" id="mcount"></div></div><button class="help" data-act="rules"><span>?</span></button></div></div>';
  if(S.preview) h+='<div class="preview">PREVIEW · '+esc(S.preview)+'</div>';
  h+='<div class="rules">'+rules().map(function(r,i){return '<div class="rule"><i>'+(i+1)+'</i>'+esc(r)+'</div>';}).join('')+'</div>';
  h+='<div class="bar"><div class="name"><span class="lab">picking as</span><input type="text" id="name" placeholder="your name" maxlength="40" autocomplete="off"></div><div class="vsep"></div><div class="cnt" id="cnt"></div><div class="sp"></div><div class="acts"><button class="btn link" data-act="clear">clear all</button><button class="btn" id="go" data-act="submit" disabled>Submit picks →</button></div><div class="hint" id="hint"></div><div class="err" id="err"></div></div>';
  h+='<div class="filters"><span class="lab">filter</span>'+chips()+'<span class="note lab" style="text-transform:none;letter-spacing:0;font-weight:400">fabric chips come from this week\\'s data</span></div>';
  if(S.shelf.length){ h+='<div class="sect gold"><span class="lab">saved from earlier weeks</span><span></span></div><div class="list">'+S.shelf.map(rowHtml).join('')+'</div>'; }
  h+='<div class="sect"><span class="lab">this week\\'s shortlist</span><span></span></div><div class="list">'+S.entries.map(rowHtml).join('')+'</div>';
  h+='<div class="foot">picker build '+esc(S.build)+'</div>';
  h+='<div class="mbar"><div class="err" id="merr"></div><div class="row"><div style="min-width:0;flex:1"><div class="c1" id="mc1"></div><div class="c2" id="mc2"></div></div><button class="btn link" data-act="clear">Clear all</button><button class="btn" id="mgo" data-act="submit" disabled>Submit picks →</button></div></div>';
  h+='</div>';
  app.innerHTML=h; upd(); applyFilter(); }
function rules(){ return ['Click individual images, never whole posts','Click order is the order — first '+CAP+' become prompts','Max '+MAXS+' images from any one post','Extras auto-save to next week']; }
function chips(){ var c=[{k:'all',t:'all '+S.count},{k:'fit9',t:'fit ≥ 9'}]; S.fabrics.forEach(function(f){c.push({k:'fab:'+f,t:f.toLowerCase()});}); c.push({k:'car',t:'carousels only'});
  return c.map(function(x){return '<button class="chip'+(FILTER===x.k?' on':'')+'" data-act="filter" data-k="'+esc(x.k)+'">'+esc(x.t)+'</button>';}).join(''); }
function rowHtml(r){ var isTag=String(r.source).charAt(0)==='#'; var h='<div class="post'+(r.kind==='shelf'?' shelf':'')+(OPEN[r.id]?' open':'')+'" id="post'+r.id+'" data-id="'+r.id+'"><div class="ph">';
  if(r.kind==='week') h+='<span class="rank'+(r.rank===1?' top':'')+'">'+(r.rank===1?'Best fit':'#'+r.rank)+'</span><span class="ptitle">'+esc(rowTitle(r))+'</span>';
  h+='<span class="src'+(isTag?' tag':'')+'">'+esc(r.source)+'</span>';
  if(r.kind==='shelf') h+='<span class="saved">'+esc(r.savedTag)+'</span>';
  if(r.heldFrom) h+='<span class="held">held over from '+esc(r.heldFrom)+'</span>';
  if(r.score) h+='<span class="stat blue score" style="display:none">'+esc(String(r.score))+'/12</span>';
  h+='<span class="sp"></span>';
  if(r.kind==='shelf') h+='<span class="savednote">already saved · no save needed</span>';
  h+='<div class="capdots"><div class="d" id="dots'+r.id+'"></div><span class="t" id="chosen'+r.id+'"></span></div></div>';
  h+='<div class="mtitle">'+esc(r.product||rowTitle(r))+'</div>';
  var st=[]; st.push('<span class="stat">'+r.images.length+' image'+(r.images.length===1?'':'s')+'</span>');
  if(Number(r.likes)<0) st.push('<span class="stat">likes hidden</span>'); else if(r.likes||r.likes===0) st.push('<span class="stat">'+esc(String(r.likes))+' likes</span>');
  if(r.comments||r.comments===0) st.push('<span class="stat">'+esc(String(r.comments))+' comments</span>');
  if((!r.likes&&r.likes!==0)&&r.engagement) st.push('<span class="stat">'+esc(r.engagement)+'</span>');
  if(r.type) st.push('<span class="stat">'+esc(r.type)+'</span>');
  if(r.score) st.push('<span class="stat blue">brand fit '+esc(String(r.score))+'/12</span>');
  if(r.product) st.push('<span class="stat green">'+esc(r.product)+'</span>');
  h+='<div class="stats">'+st.join('')+'</div>';
  if(r.caption||r.rationale||r.postUrl){ h+='<div class="twotg" data-act="open" data-id="'+r.id+'">caption · why it scored '+(OPEN[r.id]?'▴':'▾')+'</div><div class="two">'+(r.caption?'<div class="capq"><span class="lab">their caption</span><p>'+esc(r.caption)+'</p></div>':'')+'<div class="why"><span class="lab">why it scored</span><p>'+esc(r.rationale||'—')+'</p>'+(r.postUrl?'<a href="'+esc(r.postUrl)+'" target="_blank" rel="noopener">open original post ↗</a>':'')+'</div></div>'; }
  h+='<div class="strip"><span class="lab">'+(r.images.length>1?'carousel':'single')+' · '+r.images.length+' slide'+(r.images.length===1?'':'s')+'</span><span></span><span class="capnote" id="capnote'+r.id+'"></span></div><div class="tiles">';
  r.images.forEach(function(u,ix){ var i=ix+1; h+='<div class="tile" id="t'+r.id+'_'+i+'" data-act="pick" data-id="'+r.id+'" data-i="'+i+'"><img src="'+esc(u)+'" loading="lazy" alt=""'+(r.kind==='week'?' onerror="recover(\\''+r.id+'\\','+i+')"':'')+'><div class="veil"></div><span class="n">'+pad(i)+'</span><span class="ob"></span><span class="lbl"></span><span class="zm" data-act="zoom" data-id="'+r.id+'" data-i="'+i+'">⌖</span><span class="zmhit" data-act="zoom" data-id="'+r.id+'" data-i="'+i+'"></span><div class="st rec"><span class="spin"></span><span class="t">recovering<br>from archive</span></div><div class="st gone"><span class="t">image expired</span></div><div class="st lock"><span class="t">'+(MOBILE.matches?'▢':MAXS+' is the max for one post')+'</span></div></div>'; });
  return h+'</div></div>'; }

/* patch selection state without re-rendering (keeps images + name input) */
function upd(){ if(S.winner||DONE) return; var c=compute();
  ROWS.forEach(function(r){ var cnt=c.per[r.id]||0; r.images.forEach(function(_,ix){ var i=ix+1; var el=document.getElementById('t'+r.id+'_'+i); if(!el) return; var p=c.pos[key(r.id,i)]; var st=imgState(r.id,i);
    el.className='tile'+(p?(p.kind==='taken'?' sel':' over'):'')+(st==='rec'?' rec':'')+(st==='gone'?' gone':'')+(!p&&st==='ok'&&isLocked(r.id,i,c)?' lock':'');
    el.querySelector('.ob').textContent=p?(p.kind==='taken'?pad(p.idx):'next wk'):''; el.querySelector('.lbl').textContent=p?(p.kind==='taken'?'→ prompt '+pad(p.idx):(MOBILE.matches?'→ next week':'→ saved for next week')):''; });
    var d=''; for(var k=1;k<=MAXS;k++) d+='<i class="'+(k<=cnt?'on':'')+'"></i>'; var de=document.getElementById('dots'+r.id); if(de) de.innerHTML=d;
    var ch=document.getElementById('chosen'+r.id); if(ch){ ch.textContent=cnt+' of '+MAXS+(MOBILE.matches?'':' chosen'); ch.className='t'+(cnt>=MAXS?' full':''); }
    var cn=document.getElementById('capnote'+r.id); if(cn) cn.textContent=cnt>=MAXS?'this post is at its '+MAXS+'-image cap':'';
    var pe=document.getElementById('post'+r.id); if(pe) pe.style.borderColor=cnt&&r.kind!=='shelf'?'#273F22':''; });
  var posts=Object.keys(c.per).length; var sl=''; for(var s=1;s<=CAP;s++) sl+='<i class="'+(s<=c.taken.length?'on':'')+'"></i>'; if(c.over.length){ sl+='<i class="gap"></i>'; for(var o=0;o<Math.min(c.over.length,6);o++) sl+='<i class="over"></i>'; }
  document.getElementById('slots').innerHTML=sl;
  document.getElementById('mcount').innerHTML='<b>'+c.taken.length+'</b><span>/'+CAP+'</span>'+(c.over.length?' <em>· +'+c.over.length+' next week</em>':'');
  document.getElementById('cnt').innerHTML='<b>'+c.taken.length+' image'+(c.taken.length===1?'':'s')+'</b> across '+posts+' post'+(posts===1?'':'s')+(c.over.length?' <span>· '+c.over.length+' saved for next week</span>':'');
  document.getElementById('mc1').textContent=c.taken.length+' of '+CAP+' · '+posts+' post'+(posts===1?'':'s'); document.getElementById('mc2').textContent=c.over.length?c.over.length+' saved for next week':'';
  var ok=!!NAME.trim()&&c.taken.length>0&&!BUSY&&!S.preview; document.getElementById('go').disabled=!ok; document.getElementById('mgo').disabled=!ok;
  var ni=document.getElementById('name'); ni.className=NAME.trim()?'ok':(c.taken.length?'bad':''); document.getElementById('hint').textContent=(!NAME.trim()&&c.taken.length)?'Type your name to submit':'';
  if(LB) lbDraw(); }
function applyFilter(){ ROWS.forEach(function(r){ var show=true; if(FILTER==='fit9') show=(Number(r.score)||0)>=9; else if(FILTER==='car') show=r.images.length>1||/carousel/i.test(r.type||''); else if(FILTER.indexOf('fab:')===0) show=(r.fabric||'')===FILTER.slice(4); var el=document.getElementById('post'+r.id); if(el) el.classList.toggle('hidden',!show); });
  var cs=document.querySelectorAll('.chip'); for(var i=0;i<cs.length;i++) cs[i].classList.toggle('on',cs[i].getAttribute('data-k')===FILTER); }

/* ── expired-image recovery ── */
function recover(id,i){ var r=BY[id]; var el=document.getElementById('t'+id+'_'+i); if(!el||IMG[key(id,i)]) return;
  if(!r||!r.origN){ IMG[key(id,i)]='gone'; upd(); return; }
  IMG[key(id,i)]='rec'; upd();
  google.script.run.withSuccessHandler(function(d){ if(d){ el.querySelector('img').src=d; r.images[i-1]=d; IMG[key(id,i)]='ok'; } else IMG[key(id,i)]='gone'; upd(); })
    .withFailureHandler(function(){ IMG[key(id,i)]='gone'; upd(); }).archivedImage(r.archiveWeek||WEEK, r.origN, i); }

/* ── lightbox ── */
function lbOpen(id,i){ LB={id:id,i:i}; document.getElementById('lb').hidden=false; lbDraw(); }
function lbClose(){ LB=null; document.getElementById('lb').hidden=true; }
function lbDraw(){ if(!LB) return; var r=BY[LB.id]; var c=compute(); var k=key(LB.id,LB.i); var p=c.pos[k]; var st=imgState(LB.id,LB.i); var locked=!p&&isLocked(LB.id,LB.i,c);
  var lbl=p?(p.kind==='taken'?'Selected ✓ · prompt '+pad(p.idx):'Selected ✓ · next week'):'Select';
  document.getElementById('lb').innerHTML='<img src="'+esc(r.images[LB.i-1])+'" alt=""><button class="x" data-act="lbclose">✕</button><div class="info">'+esc(rowTitle(r))+' · '+esc(r.source)+'<br>slide '+pad(LB.i)+' of '+pad(r.images.length)+(p?' · chosen':'')+'</div><button class="nav l" data-act="lbnav" data-d="-1">←</button><button class="nav r" data-act="lbnav" data-d="1">→</button><div class="bot"><div class="cnt2">'+LB.i+' / '+r.images.length+'</div><button class="selbtn'+(p?' on':'')+'" data-act="lbsel"'+((st!=='ok'||locked)?' disabled':'')+'>'+(st==='gone'?'image expired':(locked?MAXS+' max for this post':lbl))+'</button><div class="esc">'+(MOBILE.matches?'tap again to deselect · swipe for the next slide':'← → move · esc to close')+'</div></div>'; }
function lbNav(d){ if(!LB) return; var r=BY[LB.id]; var n=LB.i+d; if(n<1||n>r.images.length) return; LB.i=n; lbDraw(); }

/* ── sheets ── */
function openSheet(html){ document.getElementById('sheet').innerHTML='<div class="grab"></div>'+html; document.getElementById('sheetwrap').hidden=false; }
function closeSheet(){ document.getElementById('sheetwrap').hidden=true; }
function rulesSheet(){ openSheet('<div class="h">How picking works</div><div class="rl">'+rules().map(function(r,i){return '<div><i>'+(i+1)+'</i><span>'+esc(r)+'</span></div>';}).join('')+'</div><div class="p">First valid submission wins the week. Everyone after sees a locked screen.</div><button class="btn full" data-close="1">Got it</button>'); }

/* ── terminal views ── */
function termHtml(title,l1,l2,l2soft,tiles,foot){ var g=(tiles||[]).map(function(t){return '<div><div class="c stripe">'+(t.url?'<img src="'+esc(t.url)+'" alt="" onerror="this.style.display=\\'none\\'">':'')+'</div><div class="hn">'+esc(t.handle)+'</div></div>';}).join('');
  return '<div class="page"><div class="hd"><div class="hdrow"><div><div class="ttl">Selene Dreams Research Picks<small class="mwk"> · wk '+esc(WEEK.slice(5))+'</small></div><div class="sub">week of '+esc(WEEK)+'</div></div></div></div><div class="term"><div class="h">'+esc(title)+'</div><div class="l1">'+l1+'</div>'+(l2?'<div class="l2'+(l2soft?' soft':'')+'">'+esc(l2)+'</div>':'')+(g?'<div class="tgrid">'+g+'</div>':'')+'<div class="ft">'+esc(foot)+'</div></div><div class="foot">picker build '+esc(S.build)+'</div></div>'; }
function pickedTiles(keys){ return keys.map(function(k){var a=parts(k);var r=BY[a[0]];return {url:r.images[a[1]-1],handle:r.source||rowTitle(r)};}); }

/* ── submit ── */
function setErr(m){ document.getElementById('err').textContent=m; document.getElementById('merr').textContent=m; }
function submit(){ if(S.preview){ toast('Preview only — nothing is submitted',true); return; } var c=compute(); if(!c.taken.length||!NAME.trim()||BUSY) return; BUSY=true; upd(); setErr('');
  var go=document.getElementById('go'), mgo=document.getElementById('mgo'); go.textContent=mgo.textContent='Submitting…';
  var overNonShelf=c.over.filter(function(k){return parts(k)[0].charAt(0)!=='S';});
  var takenKeys=c.taken.slice();
  google.script.run.withSuccessHandler(function(r){
    if(!r.ok){ BUSY=false; go.textContent=mgo.textContent='Submit picks →'; setErr(r.error||'Could not submit.'); upd(); if(r.locked){ setErr('Someone submitted before you — this week is locked. Reloading…'); setTimeout(function(){location.reload();},1800);} return; }
    var posts=group(takenKeys).length; var finish=function(note){ DONE=true; document.getElementById('app').innerHTML=termHtml('You got it', takenKeys.length+' image'+(takenKeys.length===1?'':'s')+' across '+posts+' post'+(posts===1?'':'s')+' are being written into the queue.', note, false, pickedTiles(takenKeys), 'Prompts are written within the hour. The images show up on the review page.'); };
    if(!overNonShelf.length){ finish(''); return; }
    go.textContent=mgo.textContent='Saving the rest…';
    google.script.run.withSuccessHandler(function(sv){ finish(sv&&sv.ok?sv.added+' image set'+(sv.added===1?'':'s')+' saved for next week.':'Your picks are in, but the overflow could not be saved — tell Marcus.'); })
      .withFailureHandler(function(){ finish('Your picks are in, but the overflow could not be saved.'); })
      .saveToShelf(NAME.trim(),WEEK,group(overNonShelf));
  }).withFailureHandler(function(e){ BUSY=false; go.textContent=mgo.textContent='Submit picks →'; setErr('Error: '+String(e&&e.message||e)); upd(); })
  .submitPicks(NAME.trim(),WEEK,group(takenKeys)); }

/* ── events ── */
var UNDO=null;
document.addEventListener('click',function(e){
  if(e.target.closest('[data-close]')){ closeSheet(); return; }
  var el=e.target.closest('[data-act]'); if(!el) return; var act=el.getAttribute('data-act'); var id=el.getAttribute('data-id'); var i=Number(el.getAttribute('data-i')||0);
  if(act==='zoom'){ e.stopPropagation(); if(imgState(id,i)==='gone') return; lbOpen(id,i); return; }
  if(act==='pick'){ pick(id,i); return; }
  if(act==='open'){ OPEN[id]=!OPEN[id]; var pe=document.getElementById('post'+id); pe.classList.toggle('open',!!OPEN[id]); el.textContent='caption · why it scored '+(OPEN[id]?'▴':'▾'); return; }
  if(act==='filter'){ FILTER=el.getAttribute('data-k'); applyFilter(); return; }
  if(act==='rules'){ rulesSheet(); return; }
  if(act==='clear'){ if(!ORDER.length) return; UNDO=ORDER.slice(); var n=ORDER.length; ORDER=[]; upd(); toast('Cleared '+n+' pick'+(n===1?'':'s'),false,true); return; }
  if(act==='undo'){ if(UNDO){ ORDER=UNDO; UNDO=null; upd(); } document.getElementById('toast').className='toast'; return; }
  if(act==='submit'){ submit(); return; }
  if(act==='lbclose'){ lbClose(); return; }
  if(act==='lbnav'){ lbNav(Number(el.getAttribute('data-d'))); return; }
  if(act==='lbsel'){ if(LB) pick(LB.id,LB.i); return; }
});
document.addEventListener('input',function(e){ if(e.target&&e.target.id==='name'){ NAME=e.target.value; upd(); } });
document.addEventListener('keydown',function(e){ if(e.key==='Escape'){ lbClose(); closeSheet(); } if(LB&&e.key==='ArrowLeft') lbNav(-1); if(LB&&e.key==='ArrowRight') lbNav(1); });
(function(){ var x0=null; var lb=document.getElementById('lb'); lb.addEventListener('touchstart',function(e){x0=e.touches[0].clientX;},{passive:true}); lb.addEventListener('touchend',function(e){ if(x0==null) return; var dx=e.changedTouches[0].clientX-x0; x0=null; if(Math.abs(dx)>40) lbNav(dx<0?1:-1); },{passive:true}); })();
render();
`; }
