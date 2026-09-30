"""Capture README screenshots from a running stack with Playwright.

    pip install playwright && python -m playwright install --with-deps chromium
    python scripts/screenshots.py --base http://localhost --out screenshots

Expects demo data (`manage.py seed_demo --force`). Used by
.github/workflows/screenshots.yml, which commits the results.
"""

import argparse
import os
from pathlib import Path

from playwright.sync_api import sync_playwright

PASSWORD = os.environ.get("DEMO_PASSWORD", "NexusDemo!2026")
VIEWPORT = {"width": 1440, "height": 900}


def login(page, base, email):
    page.goto(f"{base}/login")
    page.fill("input[type=email]", email)
    page.fill("input[type=password]", PASSWORD)
    page.click("button[type=submit]")
    page.wait_for_url(lambda url: "/login" not in url, timeout=15000)
    page.wait_for_load_state("networkidle")


def shot(page, out, name, full_page=True):
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(400)
    path = out / f"{name}.png"
    page.screenshot(path=str(path), full_page=full_page)
    print("saved", path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://localhost")
    parser.add_argument("--out", default="screenshots")
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    base = args.base.rstrip("/")

    with sync_playwright() as p:
        browser = p.chromium.launch()

        # Admin: analytics dashboard
        page = browser.new_context(viewport=VIEWPORT).new_page()
        login(page, base, "admin@nexusdesk.dev")
        page.goto(f"{base}/admin")
        page.wait_for_selector(".stat")
        shot(page, out, "admin-analytics")

        # Agent: SLA-sorted queue, then a ticket with an AI draft
        page = browser.new_context(viewport=VIEWPORT).new_page()
        login(page, base, "agent2@nexusdesk.dev")
        page.goto(f"{base}/agent")
        page.wait_for_selector(".ticket-card")
        shot(page, out, "agent-queue", full_page=False)
        page.click(".ticket-card >> nth=0")
        page.wait_for_selector(".timeline")
        page.click("text=Ask AI copilot")
        page.wait_for_selector(".callout-ai", timeout=30000)
        shot(page, out, "agent-ticket-copilot")

        # Customer: new ticket with duplicate warning and AI triage
        page = browser.new_context(viewport=VIEWPORT).new_page()
        login(page, base, "customer1@nexusdesk.dev")
        page.goto(f"{base}/new")
        page.fill("input[maxlength='200']", "Charged twice this month")
        page.fill("textarea", "My card statement shows two identical charges for the Pro plan. Please refund one.")
        page.click("h2")  # blur -> classify
        page.wait_for_selector(".callout-ai", timeout=30000)
        page.wait_for_timeout(1500)  # debounced duplicate check
        shot(page, out, "customer-new-ticket", full_page=False)

        page.goto(f"{base}/dashboard")
        page.wait_for_selector(".ticket-card, .empty")
        shot(page, out, "customer-dashboard", full_page=False)

        browser.close()


if __name__ == "__main__":
    main()
