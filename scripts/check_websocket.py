"""Smoke test for live updates through the real reverse proxy (used in CI).

    python scripts/check_websocket.py http://localhost

Logs in two seeded demo users, opens a WebSocket for the customer, has the
assigned agent reply, and checks the customer's socket receives the event.
"""

import asyncio
import json
import sys

import requests
from websockets.asyncio.client import connect

PASSWORD = "NexusDemo!2026"


def login(base, email):
    session = requests.Session()
    session.post(f"{base}/api/auth/login/", json={"email": email, "password": PASSWORD}, timeout=10).raise_for_status()
    return session


async def main(base):
    ws_url = base.replace("http", "ws", 1) + "/ws/"
    customer = login(base, "customer1@nexusdesk.dev")
    ticket = customer.post(f"{base}/api/tickets/", json={"title": "Live check", "description": "export error 500"},
                           timeout=10).json()
    cookie = "; ".join(f"{k}={v}" for k, v in customer.cookies.items())

    async with connect(ws_url, origin=base, additional_headers={"Cookie": cookie}) as socket:
        hello = json.loads(await asyncio.wait_for(socket.recv(), 10))
        assert hello["event"] == "connected", hello
        agent = login(base, ticket["assigned_to"]["email"])
        agent.post(f"{base}/api/tickets/{ticket['id']}/comments/", json={"body": "On it"}, timeout=10).raise_for_status()
        event = json.loads(await asyncio.wait_for(socket.recv(), 10))
        assert (event["ticket"], event["change"]) == (ticket["id"], "comment"), event
    print(f"WebSocket OK through {base}: customer received live reply on ticket #{ticket['id']}")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "http://localhost"))
