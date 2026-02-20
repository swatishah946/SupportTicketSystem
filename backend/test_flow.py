import urllib.request
import urllib.error
import json
import random

email = f"test{random.randint(1000,9999)}@test.com"
password = "TestPassword123!"

# 1. Register
print("Registering...")
req_reg = urllib.request.Request(
    'http://localhost:8000/api/auth/registration/',
    data=json.dumps({
        'email': email,
        'password1': password,
        'password2': password,
        'username': email.split('@')[0]
    }).encode('utf-8'),
    headers={'Content-Type': 'application/json'}
)

try:
    res_reg = urllib.request.urlopen(req_reg)
    print("REGISTRATION SUCCESS", res_reg.read())
except urllib.error.HTTPError as e:
    print("REGISTRATION ERROR", e.read())
    exit(1)

# 2. Login
print("Logging in...")
req_login = urllib.request.Request(
    'http://localhost:8000/api/auth/login/',
    data=json.dumps({
        'email': email,
        'password': password
    }).encode('utf-8'),
    headers={'Content-Type': 'application/json'}
)

try:
    res_login = urllib.request.urlopen(req_login)
    print("LOGIN SUCCESS", res_login.read())
except urllib.error.HTTPError as e:
    print("LOGIN ERROR", e.read())
