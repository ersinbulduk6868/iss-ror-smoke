#!/usr/bin/env python3
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

CONTROL_URL = "https://hnszvqlgqatsgbuchewt.supabase.co/functions/v1/generation-nvidia-asset-worker"
AUDIENCE = "iss-asset-provider-smoke"


def oidc_token():
    base = os.environ.get("ACTIONS_ID_TOKEN_REQUEST_URL", "")
    bearer = os.environ.get("ACTIONS_ID_TOKEN_REQUEST_TOKEN", "")
    if not base or not bearer:
        raise RuntimeError("GITHUB_OIDC_ENV_MISSING")
    sep = "&" if "?" in base else "?"
    req = urllib.request.Request(
        f"{base}{sep}audience={urllib.parse.quote(AUDIENCE)}",
        headers={"Authorization": f"bearer {bearer}", "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.load(resp)
    token = payload.get("value")
    if not token:
        raise RuntimeError("GITHUB_OIDC_TOKEN_MISSING")
    return token


def call(mode):
    body = json.dumps({"mode": mode}).encode()
    req = urllib.request.Request(
        CONTROL_URL,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {oidc_token()}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", "replace")
        raise RuntimeError(f"CONTROL_HTTP_{exc.code}: {text[:4000]}") from exc


status = call("status")
print(json.dumps({"marker": "ASSET_PROVIDER_CONTROL_STATUS", "result": status}, sort_keys=True))
if status.get("success") is not True:
    raise SystemExit("CONTROL_STATUS_FAILED")
print(f"SKETCHFAB_CREDENTIAL_PRESENT={str(bool(status.get('sketchfabCredentialPresent'))).lower()}")
result = call("run_smoke")
print(json.dumps(result, indent=2, sort_keys=True))
if result.get("success") is not True or result.get("marker") != "ASSET_EXTERNAL_PROVIDER_HANDOFF=PASS":
    raise SystemExit("ASSET_EXTERNAL_PROVIDER_HANDOFF_FAILED")
print("ASSET_EXTERNAL_PROVIDER_HANDOFF=PASS")
