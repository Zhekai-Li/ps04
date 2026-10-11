const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const htmlRoot = path.resolve(__dirname, '../../runs/live-20261010T142614Z-b7aaa14e/package/technical_demo/_html');
const files = fs.readdirSync(htmlRoot).filter((name) => name.endsWith('.html')).sort().map((name) => path.join(htmlRoot, name));

(async () => {
  const browser = await chromium.launch({ headless: true, channel: 'chrome' });
  const page = await browser.newPage({ viewport: { width: 960, height: 540 } });
  const results = [];
  for (const file of files) {
    await page.goto(`file://${file}`);
    const findings = await page.evaluate(() => {
      const tolerance = 2;
      const rect = (el) => { const r = el.getBoundingClientRect(); return { left:r.left, top:r.top, right:r.right, bottom:r.bottom }; };
      const outside = (a,b) => a.left < b.left-tolerance || a.right > b.right+tolerance || a.top < b.top-tolerance || a.bottom > b.bottom+tolerance;
      const intersects = (a,b) => Math.min(a.right,b.right)-Math.max(a.left,b.left)>tolerance && Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top)>tolerance;
      const label = (el) => `${el.tagName.toLowerCase()}.${el.className||''}:${(el.textContent||'').trim().slice(0,80)}`;
      const issues=[];
      document.querySelectorAll('p,h1,h2').forEach((text)=>{const container=text.closest('.card,.dark,.warm,.tint,.surface');if(container&&outside(rect(text),rect(container)))issues.push({type:'text_outside_container',text:label(text),container:label(container)});});
      document.querySelectorAll('.card,.dark,.warm,.tint,.surface').forEach((container)=>{if(container.scrollWidth>container.clientWidth+tolerance||container.scrollHeight>container.clientHeight+tolerance)issues.push({type:'container_scroll_overflow',container:label(container)});});
      const section=document.querySelector('.section');if(section){const a=rect(section);[...document.body.children].forEach((el)=>{if(el===section||el.matches('.brand,.topic,.topline,.note'))return;if(getComputedStyle(el).position==='absolute'&&intersects(a,rect(el)))issues.push({type:'title_content_overlap',content:label(el)});});}
      return issues;
    });
    results.push({file:path.basename(file),findings});
  }
  await browser.close();
  const failed=results.filter((x)=>x.findings.length);
  process.stdout.write(`${JSON.stringify({checked:results.length,failed},null,2)}\n`);
  if(failed.length)process.exitCode=1;
})().catch((error)=>{console.error(error);process.exit(1)});
