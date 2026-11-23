// SVG → PNG / PDF 변환 (Chromium + Playwright)
// 실행: node render.js
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const OUT = path.join(__dirname, 'output');
const jobs = [
  // [svg, 폭 mm, 높이 mm, 출력 이름, pdf 여부]
  ['drawing_A3.svg', 420, 297, 'drawing_A3', true],
  ['preview.svg', 424, 324, 'preview', false],
  ['answer_key.svg', 424, 324, 'answer_key', true],
  ['maze_L2_board_PRINT.svg', 400, 300, 'maze_L2_board_PRINT', true],
];

(async () => {
  const browser = await chromium.launch();
  for (const [svg, wmm, hmm, name, pdf] of jobs) {
    const svgText = fs.readFileSync(path.join(OUT, svg), 'utf8');
    const html = `<!doctype html><html><head><meta charset="utf-8"><style>
      @page { size: ${wmm}mm ${hmm}mm; margin: 0 }
      html,body{margin:0;padding:0} svg{display:block;width:${wmm}mm;height:${hmm}mm}
    </style></head><body>${svgText.replace(/^<\?xml[^>]*>/, '')}</body></html>`;
    const pxPerMm = 96 / 25.4;
    const page = await browser.newPage({
      viewport: { width: Math.ceil(wmm * pxPerMm), height: Math.ceil(hmm * pxPerMm) },
      deviceScaleFactor: 2.5,
    });
    await page.setContent(html, { waitUntil: 'load' });
    await page.screenshot({ path: path.join(OUT, `${name}.png`), fullPage: true });
    if (pdf) {
      await page.pdf({ path: path.join(OUT, `${name}.pdf`), width: `${wmm}mm`, height: `${hmm}mm`, printBackground: true });
    }
    await page.close();
    console.log('rendered', name);
  }
  await browser.close();
})();
