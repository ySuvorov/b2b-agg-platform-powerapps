"""Helpers for Fabric REST API (LRO-aware) + getting tokens via az CLI."""
import subprocess, json, urllib.request, urllib.error, time, base64

WS = "<workspace-id>"
MODEL_ID = "0e72f1a8-79cf-48ae-8bbe-1ad6bdf9af37"


def token(resource="https://api.fabric.microsoft.com"):
    return subprocess.run(
        ["az", "account", "get-access-token", "--resource", resource,
         "--query", "accessToken", "-o", "tsv"],
        capture_output=True, text=True).stdout.strip()


def _req(method, url, tok, body=None, ctype="application/json"):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, method=method,
                               headers={"Authorization": f"Bearer {tok}",
                                        "Content-Type": ctype})
    return r


def call(method, url, tok, body=None, poll=True):
    """Call Fabric API; transparently poll LRO 202 until result."""
    try:
        resp = urllib.request.urlopen(_req(method, url, tok, body))
        status = resp.status
        raw = resp.read()
        if status == 200 and raw:
            return json.loads(raw)
        if status == 201 and raw:
            return json.loads(raw)
        if status == 202 and poll:
            loc = resp.headers.get("Location")
            return _poll(loc, tok)
        return {"status": status}
    except urllib.error.HTTPError as e:
        if e.code == 202 and poll:
            loc = e.headers.get("Location")
            return _poll(loc, tok)
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode()[:600]}")


def _poll(loc, tok, timeout=180):
    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(3)
        try:
            resp = urllib.request.urlopen(_req("GET", loc, tok))
            raw = resp.read()
            j = json.loads(raw) if raw else {}
            st = j.get("status")
            if st in ("Succeeded", "Completed"):
                # fetch result
                rloc = resp.headers.get("Location") or loc + "/result"
                try:
                    rr = urllib.request.urlopen(_req("GET", loc + "/result", tok))
                    rraw = rr.read()
                    return json.loads(rraw) if rraw else j
                except urllib.error.HTTPError:
                    return j
            if st == "Failed":
                raise RuntimeError(f"LRO failed: {json.dumps(j)[:600]}")
        except urllib.error.HTTPError as e:
            if e.code in (200, 202):
                continue
            raise RuntimeError(f"poll HTTP {e.code}: {e.read().decode()[:400]}")
    raise RuntimeError("LRO timeout")


def b64(s: str) -> str:
    return base64.b64encode(s.encode("utf-8")).decode("ascii")


def unb64(s: str) -> str:
    return base64.b64decode(s).decode("utf-8")
