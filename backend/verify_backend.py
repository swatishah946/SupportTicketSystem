
import urllib.request
import json
import os
import time

BASE_URL = "http://localhost:8000/api"

def run_test(name, method, endpoint, data=None):
    print(f"Testing {name}...")
    url = f"{BASE_URL}{endpoint}"
    req = urllib.request.Request(url, method=method)
    req.add_header('Content-Type', 'application/json')
    
    if data:
        json_data = json.dumps(data).encode('utf-8')
        req.data = json_data

    try:
        with urllib.request.urlopen(req) as response:
            status = response.code
            body = response.read().decode('utf-8')
            print(f"  Status: {status}")
            print(f"  Response: {body[:200]}...")
            return json.loads(body)
    except urllib.error.HTTPError as e:
        print(f"  Failed: {e.code} {e.reason}")
        print(f"  Response: {e.read().decode('utf-8')}")
        return None
    except Exception as e:
        print(f"  Error: {e}")
        return None

def verify_backend():
    print("=== Starting Backend Verification ===")
    
    # 1. Test LLM Classification
    print("\n[1] Testing Classification (Requires GEMINI_API_KEY)")
    desc = "My internet is down and the modem light is red."
    classification = run_test("Classify Endpoint", "POST", "/tickets/classify/", {"description": desc})
    
    # 2. Create Ticket
    print("\n[2] Testing Ticket Creation")
    
    if classification:
        category = classification.get("suggested_category") or classification.get("category") or "technical"
        priority = classification.get("suggested_priority") or classification.get("priority") or "high"
    else:
        print("  Skipping classification result usage due to previous error.")
        category = "technical"
        priority = "high"

    ticket_data = {
        "title": "Internet Outage",
        "description": desc,
        "category": category,
        "priority": priority
    }

    created_ticket = run_test("Create Ticket", "POST", "/tickets/", ticket_data)
    
    # 3. List Tickets
    print("\n[3] Testing List Tickets")
    run_test("List Tickets", "GET", "/tickets/")
    
    # 4. Stats
    print("\n[4] Testing Stats Endpoint")
    run_test("Stats", "GET", "/tickets/stats/")

if __name__ == "__main__":
    verify_backend()
