import urllib.request
import urllib.error
import json

req = urllib.request.Request(
    'http://localhost:8000/api/auth/login/',
    data=json.dumps({'email': 'test@test.com', 'password': 'password'}).encode('utf-8'),
    headers={'Content-Type': 'application/json'}
)

try:
    res = urllib.request.urlopen(req)
    print("SUCCESS", res.read())
except urllib.error.HTTPError as e:
    print("ERROR", e.read())
