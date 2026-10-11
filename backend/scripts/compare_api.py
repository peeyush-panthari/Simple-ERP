"""Fetch every GET endpoint from the original (Flask :5001) and the new (FastAPI :8000) API with the same login
and compare the JSON. Both point at the same database, so any difference is a behavioural difference."""
import json, re, sys, urllib.request, urllib.error

NEW, OLD = "http://127.0.0.1:8000", "http://127.0.0.1:5001"
EMAIL, PW = "dev-admin@example.test", "DevAdmin#Pass2026"

def call(base, path, token=None, method="GET", body=None):
    req = urllib.request.Request(base + path, method=method, data=json.dumps(body).encode() if body is not None else None)
    req.add_header("Content-Type", "application/json")
    if token: req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
            ct = r.headers.get("content-type", "")
            return r.status, (json.loads(raw) if "json" in ct and raw else raw), ct
    except urllib.error.HTTPError as e:
        raw = e.read()
        try: return e.code, json.loads(raw), e.headers.get("content-type","")
        except Exception: return e.code, raw, e.headers.get("content-type","")

tok = {}
for name, base in (("new", NEW), ("old", OLD)):
    s, b, _ = call(base, "/api/v1/auth/login", method="POST", body={"email": EMAIL, "password": PW})
    assert s == 200, (name, s, b)
    tok[name] = b["accessToken"]

_, spec, _ = call(NEW, "/openapi.json")
gets = sorted(p for p, ops in spec["paths"].items() if "get" in ops)
static = [p for p in gets if "{" not in p]

def first_ids(path, n=4):
    s, b, _ = call(NEW, path + ("&" if "?" in path else "?") + f"limit={n}", tok["new"])
    if s != 200: return []
    rows = b.get("data") if isinstance(b, dict) else b
    if isinstance(rows, list): return [r.get("id") or r.get("code") for r in rows[:n] if isinstance(r, dict) and (r.get("id") or r.get("code"))]
    return []

targets = list(static)
for p in gets:
    if "{" in p and p.count("{") == 1 and p.endswith("}"):
        parent = p[: p.rindex("/")]
        if parent in static:
            for i in first_ids(parent):
                targets.append(p.replace(re.search(r"\{[^}]+\}", p).group(0), str(i)))

VOLATILE = re.compile(r"(At|Date|_at|timestamp|expires|Time)$|^(iat|exp)$", re.I)
def norm(x, key=None):
    if isinstance(x, dict): return {k: norm(v, k) for k, v in sorted(x.items())}
    if isinstance(x, list): return [norm(v) for v in x]
    return x

for p in static:
    for q in ("?limit=3&page=2", "?limit=5&q=a", "?status=active", "?status=posted", "?type=vendor", "?limit=2"):
        targets.append(p + q)
diffs, same, skipped = [], 0, 0
def find_diff(a, b, path=""):
    if type(a) != type(b):
        if isinstance(a,(int,float)) and isinstance(b,(int,float)) and a == b: return None
        return f"{path}: {a!r} != {b!r}"
    if isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a: return f"{path}.{k}: missing in NEW (old={str(b[k])[:60]!r})"
            if k not in b: return f"{path}.{k}: only in NEW ({str(a[k])[:60]!r})"
            d = find_diff(a[k], b[k], f"{path}.{k}")
            if d: return d
        return None
    if isinstance(a, list):
        if len(a) != len(b): return f"{path}: len {len(a)} != {len(b)}"
        for i, (x, y) in enumerate(zip(a, b)):
            d = find_diff(x, y, f"{path}[{i}]")
            if d: return d
        return None
    return None if a == b else f"{path}: {str(a)[:70]!r} != {str(b)[:70]!r}"

for p in targets:
    sn, bn, cn = call(NEW, p, tok["new"]); so, bo, co = call(OLD, p, tok["old"])
    if sn == 404 and so == 404: skipped += 1; continue
    if sn != so:
        diffs.append((p, f"status new={sn} old={so}", str(bn)[:120], str(bo)[:120])); continue
    if isinstance(bn, (bytes, bytearray)) or isinstance(bo, (bytes, bytearray)):
        if (len(bn) > 0) != (len(bo) > 0): diffs.append((p, "binary body presence differs"))
        else: same += 1
        continue
    d = find_diff(norm(bn), norm(bo))
    if d: diffs.append((p, d))
    else: same += 1

print(f"compared {len(targets)} GET endpoints: identical={same} skipped(404 both)={skipped} different={len(diffs)}")
for d in diffs: print(" -", *d)
