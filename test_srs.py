"""SRS live test driver: 200/304/404 + handshake dance. Crib candidate."""
import json, urllib.request

BASE = "http://127.0.0.1:18080"
WK = BASE + "/.well-known/ccrfc-report"
results = []

def check(name, cond, detail=""):
    results.append((name, "PASS" if cond else "FAIL", detail))
    print(("PASS" if cond else "FAIL"), "-", name, detail)

# 1. GET well-known -> 200 + ETag
with urllib.request.urlopen(WK) as r:
    body1 = r.read()
    etag = r.headers.get("ETag")
    check("GET well-known 200", r.status == 200, f"status={r.status}")
    check("ETag present", bool(etag), f"etag={etag}")
    report = json.loads(body1.decode())
    check("report has checksum", "report_checksum" in report)

# 2. GET with If-None-Match -> 304
req = urllib.request.Request(WK, headers={"If-None-Match": etag})
try:
    with urllib.request.urlopen(req) as r:
        check("GET If-None-Match 304", False, f"got {r.status}, wanted 304")
except urllib.error.HTTPError as e:
    check("GET If-None-Match 304", e.code == 304, f"code={e.code}")

# 3. GET wrong path -> 404
try:
    with urllib.request.urlopen(BASE + "/nope") as r:
        check("GET wrong-path 404", False, f"got {r.status}")
except urllib.error.HTTPError as e:
    check("GET wrong-path 404", e.code == 404, f"code={e.code}")

# 4. POST /handshake {} -> full report (first contact)
data = json.dumps({}).encode()
req = urllib.request.Request(BASE + "/handshake", data=data,
    headers={"Content-Type": "application/json"})
with urllib.request.urlopen(req) as r:
    b = json.loads(r.read().decode())
    check("POST handshake first-contact full report", "report_checksum" in b)

# 5. POST /handshake matching checksum -> status 304
cs = etag.strip('"')
data = json.dumps({"report_checksum": cs}).encode()
req = urllib.request.Request(BASE + "/handshake", data=data,
    headers={"Content-Type": "application/json"})
with urllib.request.urlopen(req) as r:
    b = json.loads(r.read().decode())
    check("POST handshake match 304", b.get("status") == 304, str(b)[:80])

# 6. POST /handshake wrong checksum -> full report (mismatch refetch)
data = json.dumps({"report_checksum": "0"*64}).encode()
req = urllib.request.Request(BASE + "/handshake", data=data,
    headers={"Content-Type": "application/json"})
with urllib.request.urlopen(req) as r:
    b = json.loads(r.read().decode())
    check("POST handshake mismatch refetch", "report_checksum" in b and b.get("status") != 304)

# 7. POST wrong path -> 404
try:
    req = urllib.request.Request(BASE + "/wrong", data=b"{}",
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        check("POST wrong-path 404", False, f"got {r.status}")
except urllib.error.HTTPError as e:
    check("POST wrong-path 404", e.code == 404, f"code={e.code}")

fails = [n for n, s, _ in results if s == "FAIL"]
print(f"\n{len(results)-len(fails)}/{len(results)} passing")
raise SystemExit(1 if fails else 0)
