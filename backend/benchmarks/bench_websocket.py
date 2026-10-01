"""WebSocket benchmark against a running server (Uvicorn + Redis).

    python benchmarks/bench_websocket.py --base http://127.0.0.1:8001 --replies 200 --sockets 500

Needs demo data (`manage.py seed_demo --force`). Measures two things:

1. Reply delivery latency: an agent posts a reply over HTTP; we time from
   sending that request until the customer's open WebSocket receives the
   "comment" event. This covers the whole server path: request, database
   commit, publish to Redis, and delivery over the socket (not browser rendering).
2. Fan-out: N agent sockets are open at once; one ticket change is made and we
   time until the *last* of the N sockets has received it.

Client and server run on the same machine, so absolute numbers depend on that
machine; the script prints its CPU count with the results.
"""

import argparse
import asyncio
import json
import os
import time
from pathlib import Path

import requests
from websockets.asyncio.client import connect

PASSWORD = os.environ.get("DEMO_PASSWORD", "NexusDemo!2026")


def login(base, email):
    session = requests.Session()
    session.post(f"{base}/api/auth/login/", json={"email": email, "password": PASSWORD}, timeout=10).raise_for_status()
    return session


def cookie_header(session):
    return "; ".join(f"{k}={v}" for k, v in session.cookies.items())


def pct(values, q):
    values = sorted(values)
    return round(values[min(len(values) - 1, int(q * (len(values) - 1)))], 1)


async def open_socket(ws_url, origin, cookie):
    socket = await connect(ws_url, origin=origin, additional_headers={"Cookie": cookie}, max_queue=None)
    hello = json.loads(await socket.recv())
    assert hello["event"] == "connected", hello
    return socket


async def reply_latency(base, ws_url, replies):
    customer = login(base, "customer1@nexusdesk.dev")
    ticket = customer.post(f"{base}/api/tickets/", json={"title": "Latency test", "description": "export error"},
                           timeout=10).json()
    agent = login(base, ticket["assigned_to"]["email"])
    socket = await open_socket(ws_url, base, cookie_header(customer))
    loop = asyncio.get_running_loop()
    latencies = []
    for i in range(replies):
        start = time.perf_counter()
        url = f"{base}/api/tickets/{ticket['id']}/comments/"
        await loop.run_in_executor(
            None, lambda i=i, url=url: agent.post(url, json={"body": f"update {i}"}, timeout=10).raise_for_status())
        while True:
            event = json.loads(await asyncio.wait_for(socket.recv(), 10))
            if event.get("change") == "comment" and event.get("ticket") == ticket["id"]:
                break
        latencies.append((time.perf_counter() - start) * 1000)
    await socket.close()
    return {"replies": replies, "p50_ms": pct(latencies, 0.5), "p95_ms": pct(latencies, 0.95),
            "max_ms": round(max(latencies), 1)}


async def fan_out(base, ws_url, sockets, rounds):
    """Time until every one of `sockets` agent connections receives one customer reply."""
    agent = login(base, "agent1@nexusdesk.dev")
    cookie = cookie_header(agent)
    connections = []
    for start in range(0, sockets, 50):  # open in batches to avoid a connection storm
        connections += await asyncio.gather(*(open_socket(ws_url, base, cookie)
                                              for _ in range(start, min(sockets, start + 50))))
    customer = login(base, "customer2@nexusdesk.dev")
    actor = customer.get(f"{base}/api/auth/user/", timeout=10).json()["username"]
    ticket = customer.post(f"{base}/api/tickets/", json={"title": "Fan-out test", "description": "slow page"},
                           timeout=10).json()
    loop = asyncio.get_running_loop()

    async def arrival(socket):
        while True:
            event = json.loads(await socket.recv())
            if event.get("change") == "comment" and event.get("ticket") == ticket["id"] and event["actor"] == actor:
                return time.perf_counter()

    durations = []
    for i in range(rounds):
        # Drain anything queued (e.g. the "created" event) before timing.
        for socket in connections:
            while True:
                try:
                    await asyncio.wait_for(socket.recv(), 0.001)
                except TimeoutError:
                    break
        url = f"{base}/api/tickets/{ticket['id']}/comments/"
        start = time.perf_counter()
        await loop.run_in_executor(
            None, lambda i=i, url=url: customer.post(url, json={"body": f"ping {i}"}, timeout=10).raise_for_status())
        arrivals = await asyncio.wait_for(asyncio.gather(*(arrival(s) for s in connections)), 30)
        durations.append((max(arrivals) - start) * 1000)
    await asyncio.gather(*(s.close() for s in connections))
    return {"sockets": sockets, "rounds": rounds, "all_received_p50_ms": pct(durations, 0.5),
            "all_received_p95_ms": pct(durations, 0.95)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8001")
    parser.add_argument("--replies", type=int, default=200)
    parser.add_argument("--sockets", type=int, default=500)
    parser.add_argument("--rounds", type=int, default=20)
    args = parser.parse_args()
    ws_url = args.base.replace("http", "ws", 1) + "/ws/"

    results = {
        "cpus": os.cpu_count(),
        "reply_delivery": asyncio.run(reply_latency(args.base, ws_url, args.replies)),
        "fan_out": asyncio.run(fan_out(args.base, ws_url, args.sockets, args.rounds)),
    }
    out = Path(__file__).resolve().parent / "results-websocket.json"
    out.write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
