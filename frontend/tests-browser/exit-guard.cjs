/* Offline Chromium warning check. No authentication, provider, or owner data. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  try {
    const page = await browser.newPage();
    await page.route('**/*', route => route.fulfill({ contentType: 'text/html', body:
      '<button id="draft">Prepare synthetic draft</button><button id="clear">Clear draft</button><a href="/next">Leave</a>' }));
    await page.goto('http://li-exit.test/');
    await page.addScriptTag({ content: fs.readFileSync(path.join(__dirname, '../static/assets/exit-guard.js'), 'utf8') });
    await page.evaluate(() => {
      let pending = false;
      const guard = window.LiExitGuard.create({ window, hasPendingWork: () => pending });
      document.querySelector('#draft').onclick = () => { pending = true; guard.refresh(); };
      document.querySelector('#clear').onclick = () => { pending = false; guard.refresh(); };
    });
    let warnings = 0;
    page.on('dialog', async dialog => {
      assert.equal(dialog.type(), 'beforeunload'); warnings++; await dialog.dismiss();
    });
    await page.click('#draft'); await page.click('a');
    assert.equal(warnings, 1); assert.equal(page.url(), 'http://li-exit.test/');
    await page.click('#clear');
    await Promise.all([page.waitForURL('http://li-exit.test/next'), page.click('a')]);
    assert.equal(warnings, 1);
    console.log('PASS: dirty draft requests a browser warning; dismiss preserves page; clean page leaves without warning.');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
