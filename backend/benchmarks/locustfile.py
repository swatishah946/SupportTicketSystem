"""Load test against a running stack (e.g. `docker compose -f docker-compose.prod.yml up`).

    pip install locust
    locust -f benchmarks/locustfile.py --host http://localhost --headless -u 50 -r 10 -t 2m

Logs in as the seeded demo agent (run `manage.py seed_demo --force` first) and
mixes the read-heavy traffic an agent dashboard generates.
"""

import os
import random

from locust import HttpUser, between, task

PASSWORD = os.environ.get("DEMO_PASSWORD", "NexusDemo!2026")


class Agent(HttpUser):
    wait_time = between(0.5, 2)

    def on_start(self):
        email = f"agent{random.randint(1, 3)}@nexusdesk.dev"
        self.client.post("/api/auth/login/", json={"email": email, "password": PASSWORD})
        page = self.client.get("/api/tickets/?page_size=50").json()
        self.ids = [t["id"] for t in page.get("results", [])] or [1]

    @task(5)
    def queue(self):
        self.client.get("/api/tickets/?assigned_to=me&active=true", name="/api/tickets/?assigned_to=me")

    @task(3)
    def detail(self):
        self.client.get(f"/api/tickets/{random.choice(self.ids)}/", name="/api/tickets/:id/")

    @task(1)
    def breached(self):
        self.client.get("/api/tickets/?sla_breached=true", name="/api/tickets/?sla_breached")

    @task(1)
    def similar(self):
        self.client.post("/api/tickets/similar/", json={"description": "cannot export csv report error"})
