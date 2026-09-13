#!/usr/bin/env python3
import json
import os
import urllib.error
import urllib.parse
import urllib.request

CONTROL_URL = "https://hnszvqlgqatsgbuchewt.supabase.co/functions/v1/generation-nvidia-asset-worker"
AUDIENCE = "iss-asset-provider-smoke"
CANONICAL_UID = "820a13c4831c41959ce75e6c2014e882"
NEGATIVE_UID = "00000000000000000000000000000000"


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


def call_raw(mode, **payload):
    body = json.dumps({"mode": mode, **payload}).encode()
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
            return resp.status, json.load(resp)
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", "replace")
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            payload = {"raw": text[:4000]}
        return exc.code, payload


def call(mode, **payload):
    code, result = call_raw(mode, **payload)
    if code < 200 or code >= 300:
        raise RuntimeError(f"CONTROL_HTTP_{code}: {json.dumps(result, sort_keys=True)[:4000]}")
    return result


status = call("status")
print(json.dumps({"marker": "ASSET_PROVIDER_CONTROL_STATUS", "result": status}, sort_keys=True))
if status.get("success") is not True:
    raise SystemExit("CONTROL_STATUS_FAILED")
if status.get("version") != "1.1.1":
    raise SystemExit(f"CONTROL_VERSION_MISMATCH:{status.get('version')}")
if status.get("exactSourceDownloadEnabled") is not True:
    raise SystemExit("EXACT_SOURCE_DOWNLOAD_NOT_ENABLED")
if status.get("sketchfabCredentialPresent") is not True:
    raise SystemExit("SKETCHFAB_CREDENTIAL_MISSING")
print("ASSET_EXACT_SOURCE_CONTROL_STATUS=PASS")

canonical = call("signed_source_download", uid=CANONICAL_UID)
source = canonical.get("source") or {}
if canonical.get("success") is not True or canonical.get("status") != "SIGNED_SOURCE_READY":
    raise SystemExit("CANONICAL_SOURCE_NOT_SIGNED_READY")
if source.get("provider") != "sketchfab" or source.get("uid") != CANONICAL_UID:
    raise SystemExit("CANONICAL_SOURCE_IDENTITY_MISMATCH")
if source.get("artifactKind") != "glb":
    raise SystemExit(f"CANONICAL_SOURCE_NOT_GLB:{source.get('artifactKind')}")
if not isinstance(source.get("signedUrl"), str) or not source.get("signedUrl", "").startswith("https://"):
    raise SystemExit("CANONICAL_SOURCE_SIGNED_URL_INVALID")
print(json.dumps({
    "marker": "ASSET_EXACT_SOURCE_CANONICAL_READY",
    "uid": source.get("uid"),
    "provider": source.get("provider"),
    "artifactKind": source.get("artifactKind"),
    "declaredBytes": source.get("declaredBytes"),
    "signedUrlPresent": True,
}, sort_keys=True))
print("ASSET_EXACT_SOURCE_CANONICAL_READY=PASS")

negative_code, negative = call_raw("signed_source_download", uid=NEGATIVE_UID)
if negative_code != 403:
    raise SystemExit(f"NEGATIVE_UID_HTTP_EXPECTED_403_GOT_{negative_code}")
if negative.get("status") != "SOURCE_DOWNLOAD_REJECTED" or negative.get("error") != "SOURCE_UID_NOT_ALLOWLISTED":
    raise SystemExit(f"NEGATIVE_UID_FAIL_CLOSED_MISMATCH:{json.dumps(negative, sort_keys=True)}")
print("ASSET_EXACT_SOURCE_UNKNOWN_UID_REJECTED=PASS")
print("ASSET_EXACT_SOURCE_FAIL_CLOSED_PREFLIGHT=PASS")

result = call("run_smoke")
if result.get("success") is not True or result.get("marker") != "ASSET_EXTERNAL_PROVIDER_HANDOFF=PASS":
    raise SystemExit("ASSET_EXTERNAL_PROVIDER_HANDOFF_FAILED")
print(json.dumps({
    "marker": result.get("marker"),
    "candidateCount": result.get("candidateCount"),
    "assetServiceResult": result.get("assetServiceResult"),
}, indent=2, sort_keys=True))
print("ASSET_EXTERNAL_PROVIDER_HANDOFF=PASS")
