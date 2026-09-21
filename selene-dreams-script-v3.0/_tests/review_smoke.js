// Headless smoke test for review.gs v2.5 — mocked google.script.run.
const fs = require('fs'), vm = require('vm'), { chromium } = require('playwright');
const src = fs.readFileSync('review.gs', 'utf8');
const ctx = {}; vm.createContext(ctx); vm.runInContext(src, ctx);

const PNG = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==';
const ids = (p, n) => Array.from({ length: n }, (_, i) => p + 'xxxxxxxxxxxxxxxxxxxx' + i);
const state = {
  build: ctx.REVIEW_BUILD, today: '2026-09-16', defaultDate: '2026-09-17', handle: 'x', cost: 0.24, maxRerolls: 2,
  pending: [
    { n: '40', lane: 'ai', num: '40', title: 'Linen · Duvet Set · Alabaster White', fabric: 'Linen', folder: '', slideIds: ids('A', 3), rerolls: {}, caption: 'ai caption', qaNotes: ['note one'], hasCaption: true },
    { n: 'ED-10', lane: 'edu', num: '10', title: 'Educational · Fabric Education · Fabric Face-Offs', fabric: '', folder: '', slideIds: ids('E', 6), rerolls: {}, caption: 'edu caption', qaNotes: [], hasCaption: true },
  ],
  regen: [{ n: '27', title: 'Linen · Duvet Set · Alabaster White', slide: 1, attempt: 1, max: 2, img: 'Ready', since: '2026-09-08 13:30' }],
  attention: [],
  scheduled: [
    { n: 'ED-16', lane: 'edu', num: '16', title: 'Educational · Sleep Rituals · Wind Down', when: '2026-09-17', status: 'Scheduled', slides: '', slideIds: ids('S', 5), caption: 'sched caption' },
    { n: '31', lane: 'ai', num: '31', title: 'Percale · Sheet Set · Cream', when: '2026-09-19', status: 'Scheduled', slides: '2,1', slideIds: ids('P', 2), caption: 'ai sched caption' },
  ],
  calendar: [
    { type: 'ED', lane: 'edu', n: '16', title: 'Edu · Sleep Rituals', date: '2026-09-17', time: '21:00 NY', status: 'sched', url: '', slides: '', slideIds: ids('S', 5) },
    { type: 'AI', lane: 'ai', n: '31', title: 'Percale · Sheet Set', date: '2026-09-19', time: '21:00 NY', status: 'sched', url: '', slides: '2,1', slideIds: ids('P', 2) },
  ],
};
let html = ctx.rvPageHtml_(state);
const calls = [];
const mock = `<script>
window.__calls=[];
var google={script:{run:null}};
function mk(){var ok=null,bad=null;var o={withSuccessHandler:function(f){ok=f;return o;},withFailureHandler:function(f){bad=f;return o;}};
 ['reviewThumb','reviewState','reviewApprove','reviewReject','reviewReroll','reviewCancel','reviewRetry','reviewReschedule','reviewUnreroll'].forEach(function(fn){
  o[fn]=function(){var a=[].slice.call(arguments);window.__calls.push([fn].concat(a));
   setTimeout(function(){
    if(fn==='reviewThumb') ok('${PNG}');
    else if(fn==='reviewState') ok(window.__state);
    else if(fn==='reviewApprove'){ window.__state.pending=window.__state.pending.filter(function(p){return p.n!==a[0];}); ok(String(a[0]).indexOf('ED-')===0?{ok:true,lane:'edu',status:'Approved',when:'',kind:'carousel',kept:a[1]}:{ok:true,status:'Scheduled',kept:a[1],when:a[3],kind:'carousel'}); }
    else if(fn==='reviewReroll') ok({ok:true,status:'Rerolling',attempt:1,max:2});
    else ok({ok:true});
   },5);};});
 return o;}
google.script.run={withSuccessHandler:function(f){return mk().withSuccessHandler(f);},withFailureHandler:function(f){return mk().withFailureHandler(f);}};
window.__state=${JSON.stringify(state)};
</script>`;
html = html.replace('<script>var RV_STATE=', mock + '<script>var RV_STATE=');
html = html.replace(/<link[^>]*fonts[^>]*>/g, '');
fs.writeFileSync('/tmp/review_smoke.html', html);

(async () => {
  const browser = await chromium.launch({executablePath:'/opt/pw-browsers/chromium-1194/chrome-linux/chrome', args:['--no-sandbox']});
  const errors = [];
  async function page(w, h) {
    const p = await browser.newPage({ viewport: { width: w, height: h } });
    p.on('pageerror', e => errors.push(w + ': ' + e.message));
    p.on('console', m => { if (m.type() === 'error') errors.push(w + ' console: ' + m.text()); });
    await p.goto('file:///tmp/review_smoke.html'); await p.waitForTimeout(300);
    return p;
  }
  // desktop
  let p = await page(1240, 900);
  const t = async (name, cond) => { const r = await cond(); console.log((r ? 'PASS ' : 'FAIL ') + name); if (!r) process.exitCode = 1; };
  await t('scheduled group rendered', () => p.locator('.grp.ok').count().then(c => c === 1));
  await t('2 scheduled rows', () => p.locator('.qrow.sched').count().then(c => c === 2));
  await t('regen row clickable', () => p.locator('.qrow.regen[data-act="sel"]').count().then(c => c === 1));
  await t('AI post: drop + move buttons', () => p.locator('#rail .sbar .mv').count().then(c => c === 6));
  await p.screenshot({ path: '/tmp/shot_ai.png' });
  // open edu post
  await p.click('.qrow[data-n="ED-10"]'); await p.waitForTimeout(300);
  await t('edu: 6 slides with drop buttons', () => p.locator('#rail .sbar .drop').count().then(c => c === 6));
  await t('edu: cover drop disabled', () => p.locator('#rail figure[data-i="1"] .drop:disabled').count().then(c => c === 1));
  await t('edu: order strip shown', () => p.locator('#order .oth').count().then(c => c === 6));
  await p.click('#rail figure[data-i="3"] .drop'); await p.waitForTimeout(100);
  await t('edu: slide 3 dropped', () => p.locator('#rail figure[data-i="3"].dropped').count().then(c => c === 1));
  await t('edu: approve label 5 slides', () => p.locator('.btn.approve').textContent().then(s => /Approve 5 slides/.test(s)));
  await p.click('#rail figure[data-i="4"] [data-act="moveL"]'); await p.waitForTimeout(100);
  await t('edu: slide 4 moved before 2', () => p.locator('#order .oth').allTextContents().then(a => a.join(',').replace(/cover/g, '') === '1,4,2,5,6'));
  await t('edu: move into cover blocked', () => p.locator('#rail figure[data-i="4"] [data-act="moveL"]:disabled').count().then(c => c === 1));
  await p.screenshot({ path: '/tmp/shot_edu.png' });
  // lightbox
  await p.click('#rail figure[data-i="2"] .shot'); await p.waitForTimeout(300);
  await t('lightbox open with img', () => p.locator('#lb:not([hidden]) .lbimg img').count().then(c => c === 1));
  await t('lightbox label slide 2', () => p.locator('#lb .lbm').textContent().then(s => /slide 2 · 3 of 5/.test(s)));
  await p.keyboard.press('ArrowRight'); await p.waitForTimeout(50);
  await t('lightbox next -> slide 5', () => p.locator('#lb .lbm').textContent().then(s => /slide 5/.test(s)));
  await p.screenshot({ path: '/tmp/shot_lb.png' });
  await p.keyboard.press('Escape'); await p.waitForTimeout(50);
  await t('lightbox closed', () => p.locator('#lb[hidden]').count().then(c => c === 1));
  // approve edu
  await p.click('.btn.approve'); await p.waitForTimeout(400);
  await t('edu approve sent kept order', () => p.evaluate(() => JSON.stringify(window.__calls.find(c => c[0] === 'reviewApprove').slice(1, 3))).then(s => s === '["ED-10",[1,4,2,5,6]]'));
  await t('edu left waiting list', () => p.locator('.qrow[data-n="ED-10"][data-kind="post"]').count().then(c => c === 0));
  await t('toast shows approved', () => p.locator('#toast').textContent().then(s => /Approved — 5 slides/.test(s)));
  // scheduled view
  await p.click('.qrow.sched[data-n="31"]'); await p.waitForTimeout(300);
  await t('sched view: order 2,1 + read-only', () => p.locator('#rail.ro figure').evaluateAll(f => f.map(x => x.getAttribute('data-i')).join(',')).then(s => s === '2,1'));
  await t('sched view: reschedule + cancel', () => p.locator('.pacts [data-act="resched"], .pacts [data-act="cancel"]').count().then(c => c === 2));
  await p.click('.qrow.sched[data-n="ED-16"]'); await p.waitForTimeout(200);
  await t('edu sched view: unapprove only', () => p.locator('.pacts [data-act="cancel"]').textContent().then(s => /Unapprove/.test(s)));
  await p.screenshot({ path: '/tmp/shot_sched.png' });
  // regen view
  await p.click('.qrow.regen'); await p.waitForTimeout(200);
  await t('regen view: withdraw button', () => p.locator('[data-act="unreroll"]').count().then(c => c === 1));
  // calendar day panel
  await p.click('.day[data-date="2026-09-17"]'); await p.waitForTimeout(400);
  await t('day panel strip thumbs', () => p.locator('#sheet .daystrip .dth img').count().then(c => c === 5));
  await p.screenshot({ path: '/tmp/shot_day.png' });
  await p.click('#sheet .dth[data-i="2"]'); await p.waitForTimeout(200);
  await t('day panel thumb opens lightbox', () => p.locator('#lb:not([hidden]) .lbm').textContent().then(s => /slide 2 · 2 of 5/.test(s)));
  await p.close();
  // mobile
  p = await page(390, 800);
  await t('mobile renders', () => p.locator('.tabs button').count().then(c => c === 2));
  await p.click('.qrow[data-n="40"]'); await p.waitForTimeout(300);
  await t('mobile: move buttons on slides', () => p.locator('#rail .sbar .mv').count().then(c => c === 6));
  await p.screenshot({ path: '/tmp/shot_mobile.png' });
  await p.close();
  await browser.close();
  console.log(errors.length ? 'ERRORS:\n' + errors.join('\n') : 'no page errors');
  if (errors.length) process.exitCode = 1;
})();
