"""
Visual QA harness.

Drives the running Streamlit app with Playwright and captures every tab for each
persona, so layout defects are found by looking rather than by hoping.

Run (from the pw-venv, with the app already running on :8501):
    ../.tools/pw-venv/Scripts/python.exe scripts/visual_qa.py
"""
from __future__ import annotations

import os
import sys

from playwright.sync_api import sync_playwright

URL = "http://localhost:8501"
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "qa-shots")

PERSONAS = ["Regional Sales Director, West", "Chief Financial Officer",
            "Junior Analyst"]
TABS = ["Explanation", "Attribution", "Causal gates", "Evidence",
        "Actions", "Method and cost", "Contract", "Audit"]


def settle(page, ms: int = 1200) -> None:
    """Streamlit reruns on every interaction; wait for the spinner to clear."""
    page.wait_for_timeout(ms)
    try:
        page.wait_for_selector('[data-testid="stStatusWidget"]', state="detached",
                               timeout=6000)
    except Exception:
        pass
    page.wait_for_timeout(350)


def pick_persona(page, index: int, label: str) -> bool:
    """Streamlit renders options as [role="option"] in a portal, not as <li>."""
    page.locator('[data-testid="stSelectbox"]').first.click()
    page.wait_for_timeout(800)
    opt = page.locator('[role="option"]').nth(index)
    if opt.count() == 0:
        page.keyboard.press("Escape")
        return False
    opt.click()
    settle(page, 1800)
    # an input's value is not part of inner_text, so read the value attribute
    val = page.locator('[data-testid="stSelectbox"] input').first.input_value()
    return label.split(",")[0] in (val or "")


def overflow_report(page) -> list[str]:
    """Elements whose content spills past their own box, plus page-level scroll."""
    return page.evaluate("""() => {
        const out = [];
        if (document.documentElement.scrollWidth > window.innerWidth + 2)
            out.push(`PAGE scrolls horizontally: ${document.documentElement.scrollWidth}px > ${window.innerWidth}px`);
        for (const el of document.querySelectorAll('div,p,span,h1,h2,h3,td,th,li')) {
            const r = el.getBoundingClientRect();
            if (r.width < 40 || r.height < 8) continue;
            if (el.scrollWidth > el.clientWidth + 6 && el.clientWidth > 60) {
                const style = getComputedStyle(el);
                if (style.overflowX === 'visible' && !el.closest('[data-testid="stTabs"] [role="tablist"]')) {
                    const t = (el.innerText || '').trim().slice(0, 60);
                    if (t) out.push(`OVERFLOW-X ${el.tagName}.${el.className.toString().slice(0,28)} "${t}"`);
                }
            }
        }
        return [...new Set(out)].slice(0, 12);
    }""")


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    for f in os.listdir(OUT):
        if f.endswith(".png"):
            os.remove(os.path.join(OUT, f))

    findings: list[str] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1600, "height": 1000},
                                device_scale_factor=1)
        page.goto(URL, wait_until="networkidle")
        settle(page, 3500)

        console: list[str] = []
        page.on("console", lambda m: console.append(f"{m.type}: {m.text[:160]}")
                if m.type in ("error", "warning") else None)

        for pi, persona in enumerate(PERSONAS):
            if pi > 0 and not pick_persona(page, pi, persona):
                findings.append(f"could not select persona '{persona}'")
                continue

            slug = persona.split(",")[0].replace(" ", "-").lower()

            for ti, tab in enumerate(TABS):
                btn = page.locator(f'[role="tab"]:has-text("{tab}")').first
                if btn.count() == 0:
                    findings.append(f"[{slug}] tab '{tab}' not found")
                    continue
                btn.click()
                settle(page, 900)

                name = f"{pi}{ti}-{slug}-{tab.replace(' ', '-').lower()}.png"
                page.screenshot(path=os.path.join(OUT, name), full_page=True)

                for issue in overflow_report(page):
                    findings.append(f"[{slug} / {tab}] {issue}")

        # mobile-ish narrow check on the busiest tab
        page.set_viewport_size({"width": 1100, "height": 900})
        settle(page, 900)
        nb = page.locator('[role="tab"]:has-text("Attribution")').first
        if nb.count():
            nb.click()
            settle(page, 900)
        page.screenshot(path=os.path.join(OUT, "z-narrow-1100-attribution.png"),
                        full_page=True)
        for issue in overflow_report(page):
            findings.append(f"[narrow 1100px / Attribution] {issue}")

        browser.close()

    shots = sorted(f for f in os.listdir(OUT) if f.endswith(".png"))
    print(f"captured {len(shots)} screenshots -> {OUT}")
    print()
    if findings:
        print(f"{len(findings)} layout finding(s):")
        for f in findings:
            print("  -", f.encode("ascii", "replace").decode())
    else:
        print("no automated layout findings (still look at the images)")
    if console:
        print("\nconsole errors/warnings:")
        for c in dict.fromkeys(console):
            print("  -", c.encode("ascii", "replace").decode())
    return 0


if __name__ == "__main__":
    sys.exit(main())
