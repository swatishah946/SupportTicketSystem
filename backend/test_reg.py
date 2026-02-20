import urllib.request
import urllib.error
import json
import random

email = f"test{random.randint(1000,9999)}@test.com"
password = "TestPassword123!"

# 1. Register without username
print("Registering...")
req_reg = urllib.request.Request(
    'http://localhost:8000/api/auth/registration/',
    data=json.dumps({
        'email': email,
        'password1': password,
        'password2': password
    }).encode('utf-8'),
    headers={'Content-Type': 'application/json'}
)

try:
    res_reg = urllib.request.urlopen(req_reg)
    print("REGISTRATION SUCCESS", res_reg.read())
except urllib.error.HTTPError as e:
    err_body = e.read().decode('utf-8')
    print("REGISTRATION ERROR:", e.code)
    try:
        err_json = json.loads(err_body)
        print("JSON Error:", json.dumps(err_json, indent=2))
    except:
        print("Raw Error:", err_body)
