/* Offline layout regression. Requires Playwright and a local Chromium browser.
   Uses the real Workspace renderer and navigation sizing with all network traffic intercepted. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');
const root = path.resolve(__dirname, '../static');

(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  try {
    for (const width of [180, 360, 390, 760, 1440]) {
      for (const scale of [1, 2]) {
        const page = await browser.newPage({ viewport: { width, height: 844 } });
        await page.route('**/*', route => route.request().url() === 'http://li-layout.test/'
          ? route.fulfill({ contentType: 'text/html', body: '<html><body></body></html>' }) : route.abort());
        await page.goto('http://li-layout.test/');
        const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8')
          .replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, '')
          .replace(/<link\b[^>]*>/gi, '');
        await page.setContent(html);
        for (const asset of ['app.css', 'privacy.css', 'appearance.css', 'specialists.css', 'planning.css']) {
          await page.addStyleTag({ content: fs.readFileSync(path.join(root, 'assets', asset), 'utf8') });
        }
        await page.addScriptTag({ content: fs.readFileSync(path.join(root, 'assets/workspace.js'), 'utf8') });
        const navigationSizing = fs.readFileSync(path.join(root, 'assets/app.js'), 'utf8').split('// Keep the last page controls clear of navigation as text size changes.')[1];
        assert.ok(navigationSizing, 'Navigation sizing code must exist');
        await page.addScriptTag({ content: navigationSizing });
        await page.evaluate(scale => {
          document.querySelectorAll('.hidden').forEach(el => { if (el.querySelector('.view')) el.classList.remove('hidden'); });
          document.querySelector('#page-title').textContent = 'Welcome back';
          window.LiWorkspace.create({ document, fetch: () => { throw new Error('Network is forbidden'); }, avatar: () => document.createElement('span') });
          // Double each computed font size to model enlarged text independently of viewport zoom.
          const sizes = [...document.querySelectorAll('body *')].map(el => [el, parseFloat(getComputedStyle(el).fontSize)]);
          for (const [el, size] of sizes) el.style.fontSize = `${size * scale}px`;
        }, scale);
        for (const view of ['home', 'specialist']) {
          await page.evaluate(view => {
            document.querySelectorAll('.view').forEach(el => el.classList.toggle('active', el.dataset.viewPanel === view));
          }, view);
          await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
          const result = await page.evaluate(view => {
            const selectors = view === 'home'
              ? ['#composer textarea', '#composer button', '.panel-heading', '.bottom-nav .nav-item']
              : ['.workspace-composer-bar textarea', '.workspace-composer-bar button', '.bottom-nav .nav-item'];
            const controls = selectors.flatMap(s => [...document.querySelectorAll(s)])
              .filter(el => el.getClientRects().length)
              .map(el => ({ label: el.getAttribute('aria-label') || el.className, rect: el.getBoundingClientRect().toJSON() }));
            const outside = [...document.querySelectorAll('body *')].filter(el => el.getClientRects().length && el.getBoundingClientRect().right > innerWidth + 1).map(el => el.id || el.className || el.tagName);
            const navigation = document.querySelector('.bottom-nav');
            if (navigation.getClientRects().length && parseFloat(getComputedStyle(document.querySelector('main')).paddingBottom) < navigation.getBoundingClientRect().height) throw new Error('Navigation covers the final page controls');
            return { overflow: document.documentElement.scrollWidth > innerWidth + 1, controls, width: innerWidth, outside };
          }, view);
          assert.equal(result.overflow, false, `${view}: overflow at ${width}px/${scale}x: ${result.outside.join(', ')}`);
          assert.ok(result.controls.some(control => control.label.includes('Message Li')), `${view}: conversation input must be visible`);
          for (const { label, rect } of result.controls) {
            assert.ok(rect.left >= -1 && rect.right <= result.width + 1, `${label}: clipped at ${width}px/${scale}x`);
            if (!label.includes('panel-heading')) assert.ok(rect.height >= 44, `${label}: touch target below 44px`);
          }
        }
        await page.close();
        console.log(`PASS: ${width}px, ${scale * 100}% simulated text size, Home and Workspace`);
      }
    }
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
