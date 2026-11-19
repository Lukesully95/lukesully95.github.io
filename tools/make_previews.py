"""Retake the link-preview images (og:image) for the portfolio, 2x AI and AI Tracker sites.

Run from the repo root. Serves the repo on localhost, screenshots each page at 1200x630,
and only replaces an image (and bumps its ?v= stamp so iMessage/Slack fetch the new one)
when the page actually looks different from the last preview.
"""
import http.server, os, re, socketserver, sys, threading, time
from functools import partial
from PIL import Image, ImageChops, ImageStat
from playwright.sync_api import sync_playwright

ROOT = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
OUT = os.environ.get("PREVIEW_OUT", ROOT)  # set to a temp dir to test without touching the repo
PORT = 8799

SITES = [
    # (page to shoot, html file holding the og tags, image path, extra css, wait ms)
    ("portfolio/", "portfolio/index.html", "portfolio/og.jpg", "", 4000),
    ("2x-ai/index.html", "2x-ai/index.html", "2x-ai/og2.jpg",
     ".sidenav{display:none!important}.hero{padding-top:44px!important}.proof{display:none!important}", 2500),
    ("ai-popularity-tracker/index.html", "ai-popularity-tracker/index.html", "ai-popularity-tracker/og2.jpg",
     "*{animation:none!important;transition:none!important}", 5000),
]


def serve():
    handler = partial(http.server.SimpleHTTPRequestHandler, directory=ROOT)
    handler.log_message = lambda *a: None
    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.TCPServer(("127.0.0.1", PORT), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def changed(new_path, old_path):
    if not os.path.exists(old_path):
        return True
    a = Image.open(new_path).convert("RGB")
    b = Image.open(old_path).convert("RGB")
    if a.size != b.size:
        return True
    diff = ImageStat.Stat(ImageChops.difference(a, b)).mean
    return sum(diff) / 3 > 1.5  # ignore tiny noise (e.g. a scrolling ticker)


def main():
    httpd = serve()
    stamp = time.strftime("%Y%m%d%H%M", time.gmtime())
    updated = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        for page_path, html_path, img_path, css, wait in SITES:
            pg = b.new_page(viewport={"width": 1200, "height": 630})
            pg.goto(f"http://127.0.0.1:{PORT}/{page_path}", wait_until="networkidle")
            if css:
                pg.add_style_tag(content=css)
            pg.wait_for_timeout(wait)
            tmp = f"/tmp/preview-{os.path.basename(os.path.dirname(img_path))}.png"
            pg.screenshot(path=tmp)
            pg.close()
            dest = os.path.join(OUT, img_path)
            if not changed(tmp, os.path.join(ROOT, img_path)):
                continue
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            Image.open(tmp).convert("RGB").save(dest, quality=88)
            html_dest = os.path.join(OUT, html_path)
            src = open(os.path.join(ROOT, html_path)).read()
            name = re.escape(os.path.basename(img_path))
            new = re.sub(rf"({name})(\?v=[^\"']*)?", rf"\g<1>?v={stamp}", src)
            os.makedirs(os.path.dirname(html_dest), exist_ok=True)
            open(html_dest, "w").write(new)
            updated.append(img_path)
        b.close()
    httpd.shutdown()
    print("updated:", ", ".join(updated) if updated else "none")


if __name__ == "__main__":
    sys.exit(main())
