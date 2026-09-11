#!/usr/bin/env python3
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

CONTROL_URL = os.environ.get("ISS_BLENDER_CONTROL_URL", "https://hnszvqlgqatsgbuchewt.supabase.co/functions/v1/bullet-physics-proof")
AUDIENCE = "iss-blender-worker"
WORKER_VERSION = "blender-production-worker-1.0.1"
BLENDER_VERSION = "4.5.13"
BLENDER_URL = f"https://download.blender.org/release/Blender4.5/blender-{BLENDER_VERSION}-linux-x64.tar.xz"
ROOT = pathlib.Path.cwd()
ARTIFACTS = ROOT / "artifacts" / "production-worker"
ASSETS = ARTIFACTS / "assets"
OUTPUT = ARTIFACTS / "output"
JOB_FILE = ARTIFACTS / "job.json"
ASSET_MAP_FILE = ARTIFACTS / "asset-map.json"
RESULT_FILE = ARTIFACTS / "runtime-result.json"
for p in (ARTIFACTS, ASSETS, OUTPUT):
    p.mkdir(parents=True, exist_ok=True)


def log(marker, **fields):
    print(json.dumps({"marker": marker, "time": time.time(), **fields}, sort_keys=True), flush=True)


def oidc_token():
    base = os.environ.get("ACTIONS_ID_TOKEN_REQUEST_URL", "")
    bearer = os.environ.get("ACTIONS_ID_TOKEN_REQUEST_TOKEN", "")
    if not base or not bearer:
        raise RuntimeError("GITHUB_OIDC_ENV_MISSING")
    sep = "&" if "?" in base else "?"
    req = urllib.request.Request(f"{base}{sep}audience={urllib.parse.quote(AUDIENCE)}", headers={"Authorization": f"bearer {bearer}", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.load(resp)
    token = payload.get("value")
    if not token:
        raise RuntimeError("GITHUB_OIDC_TOKEN_MISSING")
    return token


def control(mode, **payload):
    body = json.dumps({"mode": mode, **payload}).encode()
    req = urllib.request.Request(CONTROL_URL, data=body, method="POST", headers={"Authorization": f"Bearer {oidc_token()}", "Content-Type": "application/json", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.load(resp)
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", "replace")
        raise RuntimeError(f"CONTROL_HTTP_{exc.code}: {text[:1200]}") from exc
    if result.get("success") is not True:
        raise RuntimeError(f"CONTROL_{mode.upper()}_FAILED: {json.dumps(result, sort_keys=True)[:1600]}")
    return result


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def ensure_blender():
    existing = os.environ.get("BLENDER_BIN", "")
    if existing and pathlib.Path(existing).is_file():
        return existing
    root = ROOT / ".blender"
    binary = root / f"blender-{BLENDER_VERSION}-linux-x64" / "blender"
    if binary.is_file():
        return str(binary)
    root.mkdir(exist_ok=True)
    archive = root / "blender.tar.xz"
    log("BLENDER_DOWNLOAD_START", version=BLENDER_VERSION)
    subprocess.run(["curl", "--fail", "--location", "--retry", "3", "--retry-all-errors", BLENDER_URL, "-o", str(archive)], check=True)
    subprocess.run(["tar", "-xJf", str(archive), "-C", str(root)], check=True)
    if not binary.is_file():
        raise RuntimeError("BLENDER_BINARY_NOT_FOUND_AFTER_EXTRACT")
    version = subprocess.check_output([str(binary), "--version"], text=True, timeout=30)
    if f"Blender {BLENDER_VERSION}" not in version:
        raise RuntimeError("BLENDER_VERSION_MISMATCH")
    log("BLENDER_DOWNLOAD_PASS", version=BLENDER_VERSION)
    return str(binary)


def asset_http_url(uri):
    if uri.startswith("https://"):
        return uri
    if uri.startswith("gs://"):
        rest = uri[5:]
        bucket, slash, key = rest.partition("/")
        if not bucket or not slash or not key:
            raise RuntimeError(f"INVALID_GS_URI: {uri}")
        return f"https://storage.googleapis.com/{bucket}/{urllib.parse.quote(key, safe='/')}"
    raise RuntimeError(f"UNSUPPORTED_PRODUCTION_ASSET_URI: {uri}")


def suffix_for(uri):
    path = urllib.parse.urlparse(asset_http_url(uri)).path.lower()
    for ext in (".glb", ".gltf", ".usd", ".usda", ".usdc"):
        if path.endswith(ext):
            return ext
    raise RuntimeError(f"UNSUPPORTED_PRODUCTION_ASSET_FORMAT: {uri}")


def download_assets(job):
    bindings = job.get("request_json", {}).get("assetBindings", [])
    if len(bindings) < 2:
        raise RuntimeError("PRODUCTION_ASSET_BINDING_COUNT_LT_2")
    mapping = []
    for index, binding in enumerate(bindings, 1):
        entity = str(binding.get("entityId") or "").strip()
        uri = str(binding.get("assetUri") or "").strip()
        if not entity or not uri:
            raise RuntimeError("PRODUCTION_ASSET_BINDING_INVALID")
        ext = suffix_for(uri)
        dest = ASSETS / f"actor-{index:02d}{ext}"
        url = asset_http_url(uri)
        log("ASSET_DOWNLOAD_START", entityId=entity, extension=ext)
        req = urllib.request.Request(url, headers={"User-Agent": "ISS-Blender-Production-Worker/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=120) as resp, open(dest, "wb") as out:
                while True:
                    chunk = resp.read(1024 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"PRODUCTION_ASSET_NOT_DOWNLOADABLE entity={entity} http={exc.code}") from exc
        if dest.stat().st_size < 1024:
            raise RuntimeError(f"PRODUCTION_ASSET_TOO_SMALL entity={entity}")
        digest = sha256_file(dest)
        expected = str(binding.get("readySha256") or "").strip().lower()
        if expected and digest.lower() != expected:
            raise RuntimeError(f"PRODUCTION_ASSET_SHA256_MISMATCH entity={entity}")
        mapping.append({**binding, "localPath": str(dest.resolve()), "downloadedSha256": digest})
        log("ASSET_DOWNLOAD_PASS", entityId=entity, bytes=dest.stat().st_size, sha256=digest)
    ASSET_MAP_FILE.write_text(json.dumps(mapping, indent=2), encoding="utf-8")
    return mapping


def run_blender(job_id, worker_id):
    blender = ensure_blender()
    cmd = [blender, "--background", "--factory-startup", "--python", "blender/iss_blender_production_worker.py", "--", "--job", str(JOB_FILE), "--assets", str(ASSET_MAP_FILE), "--output", str(OUTPUT), "--result", str(RESULT_FILE)]
    log("BLENDER_CHILD_START", workerVersion=WORKER_VERSION)
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    last_heartbeat = time.monotonic()
    stdout_tail = []
    while True:
        line = process.stdout.readline() if process.stdout else ""
        if line:
            print(line, end="", flush=True)
            stdout_tail.append(line.rstrip())
            stdout_tail = stdout_tail[-40:]
        rc = process.poll()
        now = time.monotonic()
        if now - last_heartbeat >= 60:
            elapsed = int(now - start_monotonic)
            control("heartbeat", jobId=job_id, workerId=worker_id, leaseSeconds=1800)
            control("progress", jobId=job_id, workerId=worker_id, progress={"latestMarker":"BLENDER_RUNTIME_ACTIVE","childElapsedSeconds":elapsed,"stdoutTail":"\n".join(stdout_tail[-20:])})
            log("WORKER_HEARTBEAT", elapsedSeconds=elapsed)
            last_heartbeat = now
        if rc is not None:
            break
        if not line:
            time.sleep(0.5)
    if process.returncode != 0:
        raise RuntimeError(f"BLENDER_CHILD_FAILED rc={process.returncode}")
    if not RESULT_FILE.is_file():
        raise RuntimeError("BLENDER_RUNTIME_RESULT_MISSING")
    return json.loads(RESULT_FILE.read_text(encoding="utf-8"))


def put_signed(url, file_path):
    data = pathlib.Path(file_path).read_bytes()
    req = urllib.request.Request(url, data=data, method="PUT", headers={"Content-Type":"video/mp4", "x-upsert":"true"})
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            if resp.status not in (200, 201):
                raise RuntimeError(f"SIGNED_UPLOAD_STATUS_{resp.status}")
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"SIGNED_UPLOAD_HTTP_{exc.code}: {exc.read().decode('utf-8','replace')[:600]}") from exc


job_id = None
worker_id = None
start_monotonic = time.monotonic()
try:
    status = control("status")
    log("WORKER_CONTROL_PASS", service=status.get("service"), version=status.get("version"), runId=status.get("runId"))
    worker_id = f"github-{os.environ.get('GITHUB_RUN_ID','')}-{os.environ.get('GITHUB_RUN_ATTEMPT','1')}"
    claim = control("claim", workerId=worker_id)
    job = claim.get("data") or {}
    if job.get("status") == "EMPTY" or not job.get("id"):
        log("BLENDER_QUEUE_EMPTY_PASS")
        raise SystemExit(0)
    job_id = str(job["id"])
    JOB_FILE.write_text(json.dumps(job, indent=2), encoding="utf-8")
    log("BLENDER_JOB_CLAIMED", jobId=job_id, workflowId=job.get("workflow_id"), attemptCount=job.get("attempt_count"))
    control("progress", jobId=job_id, workerId=worker_id, progress={"latestMarker":"ASSET_DOWNLOAD_START","childElapsedSeconds":0})
    download_assets(job)
    control("progress", jobId=job_id, workerId=worker_id, progress={"latestMarker":"ASSETS_DOWNLOADED","childElapsedSeconds":int(time.monotonic()-start_monotonic)})
    result = run_blender(job_id, worker_id)
    result["workerVersion"] = WORKER_VERSION
    videos = result.pop("videoFiles", [])
    uploads = control("prepare_uploads", jobId=job_id, workerId=worker_id).get("uploads") or []
    if len(videos) != len(uploads):
        raise RuntimeError(f"VIDEO_UPLOAD_COUNT_MISMATCH files={len(videos)} slots={len(uploads)}")
    video_objects = []
    for local, slot in zip(sorted(videos, key=lambda x: int(x["sceneNumber"])), sorted(uploads, key=lambda x: int(x["sceneNumber"]))):
        put_signed(slot["signedUrl"], local["path"])
        video_objects.append({"sceneNumber":int(slot["sceneNumber"]), "path":slot["path"], "bytes":pathlib.Path(local["path"]).stat().st_size, "sha256":sha256_file(local["path"])})
        log("SCENE_UPLOAD_PASS", sceneNumber=slot["sceneNumber"], bytes=video_objects[-1]["bytes"])
    result["videoObjects"] = video_objects
    completion = control("complete", jobId=job_id, workerId=worker_id, success=True, result=result)
    log("BLENDER_PRODUCTION_JOB_PASS", jobId=job_id, completion=completion.get("data"))
except SystemExit:
    raise
except Exception as exc:
    log("BLENDER_PRODUCTION_JOB_FAIL", jobId=job_id, error=str(exc))
    if job_id and worker_id:
        try:
            control("complete", jobId=job_id, workerId=worker_id, success=False, result={"engine":"BLENDER","engineVersion":ENGINE_VERSION,"workerVersion":WORKER_VERSION,"error":str(exc)[:1800]})
        except Exception as close_exc:
            log("BLENDER_JOB_FAIL_CLOSE_ERROR", error=str(close_exc))
    raise
