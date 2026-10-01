"""API micro-benchmark: SQL queries per request and server-side latency.

    python benchmarks/bench_api.py --tickets 2000

Runs in-process against a fresh SQLite database through Django's test client,
so latency excludes network and reverse-proxy time. Its main purpose is to
show the number of SQL queries per request stays constant as data grows;
the timings are only indicative (they depend on the machine).
"""

import argparse
import json
import os
import statistics
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
# BENCH_DATABASE_URL points at an *empty* database (e.g. Postgres); default is a temp SQLite file.
_db = Path(tempfile.mkdtemp()) / "bench.sqlite3"
os.environ["DATABASE_URL"] = os.environ.get("BENCH_DATABASE_URL", f"sqlite:///{_db}")
os.environ["DEBUG"] = "True"
os.environ["ALLOWED_HOSTS"] = "testserver"
os.environ["GEMINI_API_KEY"] = ""
os.environ["THROTTLE_USER"] = "1000000/min"
os.environ["THROTTLE_AI"] = "1000000/min"
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ticket_system.settings")

import django  # noqa: E402

django.setup()

from django.core.management import call_command  # noqa: E402
from django.db import connection, reset_queries  # noqa: E402
from django.test.utils import CaptureQueriesContext  # noqa: E402
from rest_framework.test import APIClient  # noqa: E402

from tickets.models import Ticket, User  # noqa: E402


def measure(client, method, url, runs, **kwargs):
    timings, queries = [], set()
    for _ in range(runs):
        reset_queries()  # DEBUG query log is capped at 9000 entries; seeding fills it
        with CaptureQueriesContext(connection) as ctx:
            start = time.perf_counter()
            resp = getattr(client, method)(url, format="json", **kwargs)
            timings.append((time.perf_counter() - start) * 1000)
        assert resp.status_code in (200, 201), (url, resp.status_code, resp.content[:200])
        queries.add(len(ctx.captured_queries))
    timings.sort()
    return {
        "p50_ms": round(statistics.median(timings), 1),
        "p95_ms": round(timings[int(0.95 * (len(timings) - 1))], 1),
        "queries": sorted(queries),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tickets", type=int, default=2000)
    parser.add_argument("--runs", type=int, default=50)
    args = parser.parse_args()

    call_command("migrate", verbosity=0)
    call_command("seed_demo", tickets=args.tickets, verbosity=0)
    agent = User.objects.get(email="agent1@nexusdesk.dev")
    admin = User.objects.get(email="admin@nexusdesk.dev")
    customer = User.objects.get(email="customer1@nexusdesk.dev")
    ticket = Ticket.objects.filter(comments__isnull=False).first()

    as_agent, as_admin, as_customer = APIClient(), APIClient(), APIClient()
    as_agent.force_authenticate(agent)
    as_admin.force_authenticate(admin)
    as_customer.force_authenticate(customer)

    results = {
        "database": connection.vendor,
        "tickets_in_db": Ticket.objects.count(),
        "list_page_20": measure(as_agent, "get", "/api/tickets/", args.runs),
        "list_page_100": measure(as_agent, "get", "/api/tickets/?page_size=100", args.runs),
        "list_filtered_breached": measure(as_agent, "get", "/api/tickets/?sla_breached=true", args.runs),
        "detail": measure(as_agent, "get", f"/api/tickets/{ticket.id}/", args.runs),
        "analytics": measure(as_admin, "get", "/api/analytics/", args.runs),
        "similar_1000_candidates": measure(as_agent, "post", "/api/tickets/similar/", args.runs,
                                           data={"description": "charged twice for my subscription"}),
        "create_ticket": measure(as_customer, "post", "/api/tickets/", args.runs,
                                 data={"title": "Export fails", "description": "CSV export error 500"}),
    }
    out = HERE / f"results-{connection.vendor}.json"
    out.write_text(json.dumps(results, indent=2) + "\n")
    print(f"{'endpoint':28} {'p50 ms':>8} {'p95 ms':>8}  queries")
    for name, r in results.items():
        if isinstance(r, dict):
            print(f"{name:28} {r['p50_ms']:>8} {r['p95_ms']:>8}  {r['queries']}")
    print(f"tickets in db: {results['tickets_in_db']}  -> wrote {out.relative_to(HERE.parent)}")


if __name__ == "__main__":
    main()
