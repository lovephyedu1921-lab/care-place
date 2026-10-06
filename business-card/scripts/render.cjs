// Render the share image, app icon, print PNGs and print PDF with Playwright.
// Run build.py first, then:  NODE_PATH="$(npm root -g)" node business-card/scripts/render.cjs
const path = require("path");
const { chromium } = require("playwright");

const ROOT = path.resolve(__dirname, "..");
const file = (p) => "file://" + path.join(ROOT, p);
const DPI_SCALE = 300 / 96; // 300 dpi print output

async function shot(browser, url, out, { width, height, scale = 1, selector, quality } = {}) {
  const page = await browser.newPage({ viewport: { width, height }, deviceScaleFactor: scale });
  await page.goto(url, { waitUntil: "load" });
  await page.evaluate(() => document.fonts.ready);
  const target = selector ? page.locator(selector) : page;
  await target.screenshot({ path: path.join(ROOT, out), ...(quality ? { type: "jpeg", quality } : {}) });
  await page.close();
}

(async () => {
  const browser = await chromium.launch();

  await shot(browser, file(".build/og.html"), "site/og.jpg", { width: 1200, height: 630, quality: 82 });
  await shot(browser, file(".build/icon.html"), "site/apple-touch-icon.png", { width: 180, height: 180 });

  // 90 x 50 mm trim size at 300 dpi -> 1063 x 591 px
  const W = (90 * 96) / 25.4, H = (50 * 96) / 25.4;
  for (const face of ["front", "back"]) {
    const page = await browser.newPage({ viewport: { width: Math.ceil(W) + 8, height: Math.ceil(H) + 8 }, deviceScaleFactor: DPI_SCALE });
    await page.goto(file("print/card.html"), { waitUntil: "load" });
    await page.addStyleTag({ content: `.face:not(#${face}) { display: none !important; }` });
    await page.evaluate(() => document.fonts.ready);
    await page.screenshot({ path: path.join(ROOT, `print/card-${face}.png`), clip: { x: 0, y: 0, width: W, height: H } });
    await page.close();
  }

  // Print-shop PDF: 92 x 52 mm (1 mm bleed on each side), front + back pages
  const page = await browser.newPage();
  await page.goto(file(".build/card-bleed.html"), { waitUntil: "load" });
  await page.evaluate(() => document.fonts.ready);
  await page.pdf({
    path: path.join(ROOT, "print/card-print-92x52mm.pdf"),
    width: "92mm", height: "52mm", printBackground: true, preferCSSPageSize: true,
  });
  await page.close();

  await browser.close();
  console.log("rendered og.jpg, apple-touch-icon.png, card-front/back.png, card-print-92x52mm.pdf");
})();
