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


def check_live_update(browser, base, out):
    """Real-browser test of WebSockets through nginx: an agent replies in one
    browser and the customer's open ticket page updates without a reload."""
    customer = browser.new_context(viewport=VIEWPORT).new_page()
    login(customer, base, "customer2@nexusdesk.dev")
    ticket = customer.request.post(f"{base}/api/tickets/", data={
        "title": "CSV export fails",
        "description": "Exporting last year's report to CSV shows error 500.",
    }).json()
    customer.goto(f"{base}/tickets/{ticket['id']}")
    customer.wait_for_selector(".live-live", timeout=15000)  # WebSocket connected

    agent = browser.new_context(viewport=VIEWPORT).new_page()
    login(agent, base, ticket["assigned_to"]["email"])
    reply = "Found it: exports over 12 months time out. Please pick a shorter date range for now."
    agent.request.post(f"{base}/api/tickets/{ticket['id']}/comments/", data={"body": reply})

    customer.wait_for_selector(f"text={reply}", timeout=15000)  # appeared without reloading
    customer.wait_for_selector(".toast", timeout=5000)
    shot(customer, out, "live-update", full_page=False)
    print("Live update OK: reply appeared on the customer's open page without a reload")


def check_google_button(browser, base, out):
    """Open the login page and confirm Google accepts our Client ID for this origin.

    Google's script logs "[GSI_LOGGER]" errors such as "The given origin is not
    allowed for the given client ID" when the Cloud Console setup is wrong.
    """
    page = browser.new_context(viewport=VIEWPORT).new_page()
    console = []
    page.on("console", lambda msg: console.append(msg.text))
    page.goto(f"{base}/login")
    page.wait_for_load_state("networkidle")
    if not page.query_selector("[data-testid=google-signin]"):
        print("Google sign-in not configured (no GOOGLE_CLIENT_ID); skipping check")
        return True
    page.wait_for_selector("iframe[src*='accounts.google.com']", timeout=20000)
    page.wait_for_timeout(4000)
    shot(page, out, "login-google", full_page=False)
    problems = [m for m in console if "GSI_LOGGER" in m]
    for message in problems:
        print("Google sign-in problem:", message)
    if not problems:
        print("Google sign-in button loaded without errors for", base)
    return not problems


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
        # An existing open ticket the new one duplicates, so the warning is real.
        page.request.post(f"{base}/api/tickets/", data={
            "title": "Charged twice for my subscription",
            "description": "I was charged two times for the Pro plan this month, please refund the extra payment.",
        })
        page.goto(f"{base}/new")
        page.fill("input[maxlength='200']", "Charged twice this month")
        page.fill("textarea", "My card statement shows two identical charges for the Pro plan. Please refund one.")
        page.click("h2")  # blur -> classify
        page.wait_for_selector(".callout-ai", timeout=30000)
        page.wait_for_selector("text=Is this the same as one of your open tickets?", timeout=15000)
        shot(page, out, "customer-new-ticket", full_page=False)

        page.goto(f"{base}/dashboard")
        page.wait_for_selector(".ticket-card, .empty")
        shot(page, out, "customer-dashboard", full_page=False)

        check_live_update(browser, base, out)

        google_ok = check_google_button(browser, base, out)
        browser.close()
    if not google_ok:
        raise SystemExit("Google sign-in is misconfigured: see messages above")


if __name__ == "__main__":
    main()
