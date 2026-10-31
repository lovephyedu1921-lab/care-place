// index.html을 프레임 단위로 캡처해 frames/ 폴더에 저장한다.
// 사용: node render.cjs <출력폴더> [fps] [시작초] [끝초] [간격(프레임)]
const { chromium } = require('playwright');
const { mkdirSync } = require('node:fs');
const { resolve } = require('node:path');

const here = __dirname;
const [out = 'frames', fpsArg = '30', fromArg = '0', toArg, stepArg = '1'] = process.argv.slice(2);
const fps = +fpsArg, step = +stepArg;
mkdirSync(out, { recursive: true });

(async () => {
const proxy = process.env.HTTPS_PROXY ? { server: process.env.HTTPS_PROXY } : undefined;
const browser = await chromium.launch({ proxy });
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
await page.goto('file://' + resolve(here, 'index.html') + '?render');
await page.evaluate(async () => {
  const all = [...document.querySelectorAll('svg text')].map(t => t.textContent).join('') + document.body.textContent;
  const loads = [];
  for (const w of [500, 700, 900]) loads.push(document.fonts.load(`${w} 40px "Noto Serif KR"`, all));
  for (const w of [400, 500, 700]) loads.push(document.fonts.load(`${w} 40px "Noto Sans KR"`, all));
  await Promise.all(loads);
  await document.fonts.ready;
});
const ok = await page.evaluate(() => document.fonts.check('900 40px "Noto Serif KR"', '소담한방병원'));
console.log('font loaded:', ok);

const duration = await page.evaluate(() => window.DURATION);
const from = Math.round(+fromArg * fps), to = Math.round((toArg ? +toArg : duration) * fps);
for (let f = from; f < to; f += step) {
  await page.evaluate(t => window.renderAt(t), f / fps);
  await page.screenshot({ path: `${out}/f${String(f).padStart(5, '0')}.jpg`, type: 'jpeg', quality: 93 });
  if (f % 150 === 0) console.log('frame', f, '/', to);
}
await browser.close();
})();
