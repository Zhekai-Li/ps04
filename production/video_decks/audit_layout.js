const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const htmlRoot = path.resolve(__dirname, '../../runs/live-20261010T142614Z-b7aaa14e/package/video_decks/_html');
const files = fs.readdirSync(htmlRoot)
  .flatMap((deck) => fs.readdirSync(path.join(htmlRoot, deck)).map((name) => path.join(htmlRoot, deck, name)))
  .filter((name) => name.endsWith('.html'))
  .sort();

(async () => {
  const browser = await chromium.launch({ headless: true, channel: 'chrome' });
  const page = await browser.newPage({ viewport: { width: 960, height: 540 } });
  const results = [];

  for (const file of files) {
    await page.goto(`file://${file}`);
    const findings = await page.evaluate(() => {
      const tolerance = 2;
      const box = (element) => {
        const r = element.getBoundingClientRect();
        return { left: r.left, top: r.top, right: r.right, bottom: r.bottom, width: r.width, height: r.height };
      };
      const outside = (inner, outer) => (
        inner.left < outer.left - tolerance || inner.right > outer.right + tolerance ||
        inner.top < outer.top - tolerance || inner.bottom > outer.bottom + tolerance
      );
      const intersects = (a, b) => (
        Math.min(a.right, b.right) - Math.max(a.left, b.left) > tolerance &&
        Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) > tolerance
      );
      const label = (element) => `${element.tagName.toLowerCase()}.${element.className || ''}:${(element.textContent || '').trim().slice(0, 80)}`;
      const issues = [];

      document.querySelectorAll('p,h1,h2').forEach((text) => {
        const container = text.closest('.card,.dark,.warm,.tint,.surface,.tag');
        if (container && outside(box(text), box(container))) {
          issues.push({ type: 'text_outside_container', text: label(text), container: label(container) });
        }
      });

      document.querySelectorAll('.card,.dark,.warm,.tint,.surface,.tag').forEach((container) => {
        if (container.scrollWidth > container.clientWidth + tolerance || container.scrollHeight > container.clientHeight + tolerance) {
          issues.push({
            type: 'container_scroll_overflow',
            container: label(container),
            client: [container.clientWidth, container.clientHeight],
            scroll: [container.scrollWidth, container.scrollHeight],
          });
        }
      });

      const section = document.querySelector('.section');
      if (section) {
        const sectionBox = box(section);
        [...document.body.children].forEach((element) => {
          if (element === section || element.matches('.brand,.topic,.topline,.note')) return;
          if (getComputedStyle(element).position === 'absolute' && intersects(sectionBox, box(element))) {
            issues.push({ type: 'title_content_overlap', content: label(element) });
          }
        });
      }

      return issues;
    });
    results.push({ file: path.relative(htmlRoot, file), findings });
  }

  await browser.close();
  const failed = results.filter((result) => result.findings.length > 0);
  process.stdout.write(`${JSON.stringify({ checked: results.length, failed }, null, 2)}\n`);
  if (failed.length) process.exitCode = 1;
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
