#!/usr/bin/env python3
import json
import urllib.error
import urllib.request

req = urllib.request.Request(
    "http://127.0.0.1:8800/api/source-directories/3/discover",
    data=b"{}",
    headers={"Content-Type": "application/json"},
    method="POST",
)
try:
    urllib.request.urlopen(req, timeout=30)
    print("unexpected success")
except urllib.error.HTTPError as e:
    print(e.code, json.loads(e.read()))
