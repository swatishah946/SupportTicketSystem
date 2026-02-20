import urllib.request
import urllib.error
import json
import random

email = f"test{random.randint(1000,9999)}@test.com"
password = "TestPassword123!"

print("Registering...")
req_reg = urllib.request.Request(
    'http://localhost:8000/api/auth/registration/',
    data=json.dumps({
        'username': email.split('@')[0],
        'email': email,
        'password1': password,
        'password2': password
    }).encode('utf-8'),
    headers={'Content-Type': 'application/json'}
)
urllib.request.urlopen(req_reg)

print("Logging in...")
req_login = urllib.request.Request(
    'http://localhost:8000/api/auth/login/',
    data=json.dumps({'email': email, 'password': password}).encode('utf-8'),
    headers={'Content-Type': 'application/json'}
)
res_login = urllib.request.urlopen(req_login)
data = json.loads(res_login.read().decode('utf-8'))
print("LOGIN KEYS:", data.keys())
print("DATA:", json.dumps(data, indent=2))
