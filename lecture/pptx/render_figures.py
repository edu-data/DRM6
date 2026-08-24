# -*- coding: utf-8 -*-
"""강의자료 HTML 안의 인라인 SVG 도해를 PNG 로 굽는다.

빌드할 때마다 브라우저가 필요하지 않도록, 결과 PNG 를 figures/ 에 넣어
저장소에 함께 둔다. 도해를 고쳤을 때만 다시 실행하면 된다.

    python render_figures.py            # ../index.html → figures/fig-00.png …

필요 조건: playwright (pip install playwright && playwright install chromium)
빌드 자체에는 필요 없다.
"""

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HTML = os.path.join(HERE, "..", "index.html")
OUT = os.path.join(HERE, "figures")

JS = r"""
const { chromium } = require('playwright');
(async () => {
  const [html, out, exe] = process.argv.slice(2);
  const b = await chromium.launch(exe ? { executablePath: exe } : {});
  const pg = await (await b.newContext({
    viewport: { width: 1600, height: 1200 }, deviceScaleFactor: 3,
    colorScheme: 'light',
  })).newPage();
  await pg.goto('file://' + html, { waitUntil: 'load' });
  // 모든 슬라이드를 펼쳐 한 번에 촬영한다
  await pg.addStyleTag({ content: `
    body{overflow:auto!important}
    #deck{position:static!important;display:block!important}
    .slide{display:flex!important;position:static!important;height:auto!important;
           min-height:0!important;animation:none!important}
    #chrome,#toc,#rose{display:none!important}
    .fig svg{width:1400px!important;max-width:none!important;height:auto!important}
  ` });
  await pg.waitForTimeout(400);
  const figs = await pg.locator('.fig svg');
  const n = await figs.count();
  for (let i = 0; i < n; i++) {
    const el = figs.nth(i);
    await el.scrollIntoViewIfNeeded();
    const name = out + '/fig-' + String(i).padStart(2, '0') + '.png';
    await el.screenshot({ path: name, omitBackground: true });
    console.log(name);
  }
  await b.close();
})();
"""


def main():
    os.makedirs(OUT, exist_ok=True)
    script = os.path.join(OUT, "_shoot.js")
    with open(script, "w", encoding="utf-8") as f:
        f.write(JS)
    exe = os.environ.get("CHROMIUM_PATH", "")
    if not exe and os.path.exists("/opt/pw-browsers/chromium"):
        exe = "/opt/pw-browsers/chromium"
    try:
        subprocess.run(["node", script, os.path.abspath(HTML), OUT, exe], check=True)
    finally:
        os.remove(script)
    print("done →", OUT)


if __name__ == "__main__":
    sys.exit(main())
