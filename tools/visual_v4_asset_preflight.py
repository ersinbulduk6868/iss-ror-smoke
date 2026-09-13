from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import struct
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = Path("artifacts/visual-v4-preflight")
ASSET_ROOT = Path("runtime-assets/visual-v4")
ROOT.mkdir(parents=True, exist_ok=True)
ASSET_ROOT.mkdir(parents=True, exist_ok=True)

API = "https://api.sketchfab.com/v3/models"
UA = "InfiniteShortsStudio-VisualV4Preflight/1.0"
MAX_ARCHIVE = 1024 * 1024 * 1024
MAX_UNCOMPRESSED = 4 * 1024 * 1024 * 1024

# Exact source identities used by the already-reviewed/uploaded models.
SPECS = {
    "bugatti": {
        "uid": "4af92c51ecdd4efa9b1c19a1163d9f46",
        "nameContains": "bugatti eb110",
        "uploadedReferenceSha256": "8cc074c40fe9ced7271cbeddf223cd9a520dee868977ffcbd439cec1c2b62cb4",
        "licenseMustContain": ("noncommercial", "cc by-nc", "cc_by_nc", "ccbync"),
        "meshMin": 40,
        "vertexMin": 80000,
        "vertexMax": 150000,
        "triangleMin": 120000,
        "triangleMax": 220000,
    },
    "bulldozer": {
        "uid": "b06a715d23a7450babac383b8bb7fb0a",
        "nameContains": "bulldozer",
        "uploadedReferenceSha256": "187f81c3c4638180fb8d82c5b2bbc7510f01bc970ee149713b2de993089f1e18",
        "licenseMustContain": ("attribution", "cc by", "cc_by", "ccby"),
        "meshMin": 80,
        "vertexMin": 45000,
        "vertexMax": 100000,
        "triangleMin": 75000,
        "triangleMax": 160000,
    },
}


def fail(msg: str) -> None:
    raise RuntimeError(msg)


def token() -> str:
    for key in ("SKETCHFAB_OAUTH_ACCESS_TOKEN", "SKETCHFAB_API_TOKEN", "SKETCHFAB_TOKEN"):
        value = os.environ.get(key, "").strip()
        if value:
            return value
    fail("SKETCHFAB_AUTH_TOKEN_MISSING")


def request_json(url: str) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token()}",
            "Accept": "application/json",
            "User-Agent": UA,
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            if urllib.parse.urlparse(r.geturl()).scheme != "https":
                fail("NON_HTTPS_API_REDIRECT")
            raw = r.read(8 * 1024 * 1024 + 1)
    except urllib.error.HTTPError as exc:
        fail(f"SKETCHFAB_API_HTTP_{exc.code}")
    if len(raw) > 8 * 1024 * 1024:
        fail("SKETCHFAB_API_RESPONSE_TOO_LARGE")
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        fail("SKETCHFAB_API_NON_OBJECT")
    return data


def norm_license(raw: Any) -> str:
    if isinstance(raw, dict):
        raw = " ".join(str(raw.get(k) or "") for k in ("slug", "label", "name", "fullName", "url"))
    return re.sub(r"\s+", " ", str(raw or "").lower()).strip()


def validate_detail(kind: str, detail: dict[str, Any]) -> dict[str, Any]:
    spec = SPECS[kind]
    if str(detail.get("uid") or "") != spec["uid"]:
        fail(f"{kind.upper()}_SOURCE_UID_MISMATCH")
    name = str(detail.get("name") or "")
    if spec["nameContains"] not in name.lower():
        fail(f"{kind.upper()}_SOURCE_NAME_MISMATCH:{name}")
    if detail.get("isDownloadable") is not True:
        fail(f"{kind.upper()}_NOT_DOWNLOADABLE")
    if detail.get("isAgeRestricted") is True:
        fail(f"{kind.upper()}_AGE_RESTRICTED")
    tags = detail.get("tags") or []
    tag_text = " ".join(str((x or {}).get("slug") or (x or {}).get("name") or x) for x in tags if isinstance(x, (dict, str)))
    if "noai" in re.sub(r"[^a-z0-9]", "", tag_text.lower()):
        fail(f"{kind.upper()}_NOAI_TAG_PRESENT")
    lic = norm_license(detail.get("license"))
    compact = re.sub(r"[^a-z0-9]", "", lic)
    accepted = False
    for marker in spec["licenseMustContain"]:
        if marker in lic or re.sub(r"[^a-z0-9]", "", marker) in compact:
            accepted = True
            break
    if not accepted:
        fail(f"{kind.upper()}_LICENSE_UNEXPECTED:{lic}")
    return {"uid": spec["uid"], "name": name, "license": lic, "viewerUrl": detail.get("viewerUrl")}


def safe_member(name: str) -> PurePosixPath:
    name = name.replace("\\", "/")
    p = PurePosixPath(name)
    if not name or p.is_absolute() or ".." in p.parts or re.match(r"^[A-Za-z]:", name):
        fail(f"UNSAFE_ZIP_MEMBER:{name}")
    return p


def download_archive(kind: str) -> tuple[Path, dict[str, Any]]:
    spec = SPECS[kind]
    info = request_json(f"{API}/{spec['uid']}/download")
    gltf = info.get("gltf")
    if not isinstance(gltf, dict):
        fail(f"{kind.upper()}_GLTF_DOWNLOAD_MISSING")
    url = gltf.get("url")
    if not isinstance(url, str) or urllib.parse.urlparse(url).scheme != "https":
        fail(f"{kind.upper()}_SIGNED_URL_INVALID")
    declared = gltf.get("size")
    if isinstance(declared, int) and declared > MAX_ARCHIVE:
        fail(f"{kind.upper()}_ARCHIVE_TOO_LARGE")
    dest = ASSET_ROOT / f"{kind}.zip"
    tmp = dest.with_suffix(".zip.part")
    h = hashlib.sha256()
    total = 0
    req = urllib.request.Request(url, headers={"User-Agent": UA}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=240) as r, tmp.open("wb") as f:
            if urllib.parse.urlparse(r.geturl()).scheme != "https":
                fail(f"{kind.upper()}_SIGNED_REDIRECT_NON_HTTPS")
            while True:
                chunk = r.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_ARCHIVE:
                    fail(f"{kind.upper()}_ARCHIVE_STREAM_TOO_LARGE")
                h.update(chunk)
                f.write(chunk)
        if isinstance(declared, int) and declared >= 0 and total != declared:
            fail(f"{kind.upper()}_ARCHIVE_SIZE_MISMATCH:{total}!={declared}")
        if total < 4 or tmp.read_bytes()[:2] != b"PK":
            fail(f"{kind.upper()}_ARCHIVE_NOT_ZIP")
        tmp.replace(dest)
    finally:
        tmp.unlink(missing_ok=True)
    return dest, {"archiveBytes": total, "archiveSha256": h.hexdigest()}


def extract_archive(kind: str, archive: Path) -> Path:
    out = ASSET_ROOT / kind
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    total = 0
    seen: set[str] = set()
    seen_fold: set[str] = set()
    with zipfile.ZipFile(archive, "r") as z:
        if len(z.infolist()) > 5000:
            fail(f"{kind.upper()}_ARCHIVE_FILE_COUNT")
        bad = z.testzip()
        if bad is not None:
            fail(f"{kind.upper()}_ARCHIVE_CRC:{bad}")
        for info in z.infolist():
            p = safe_member(info.filename)
            key = p.as_posix()
            if key in seen or key.casefold() in seen_fold:
                fail(f"{kind.upper()}_ARCHIVE_DUPLICATE:{key}")
            seen.add(key)
            seen_fold.add(key.casefold())
            mode = (info.external_attr >> 16) & 0o177777
            if stat.S_ISLNK(mode):
                fail(f"{kind.upper()}_ARCHIVE_SYMLINK:{key}")
            if info.is_dir():
                continue
            total += int(info.file_size)
            if total > MAX_UNCOMPRESSED:
                fail(f"{kind.upper()}_ARCHIVE_UNCOMPRESSED_TOO_LARGE")
            suffix = Path(key).suffix.lower()
            if suffix in {".exe", ".dll", ".so", ".sh", ".py", ".ps1", ".bat", ".cmd", ".zip", ".7z", ".rar", ".tar"}:
                fail(f"{kind.upper()}_ARCHIVE_UNSAFE_PAYLOAD:{key}")
            dest = out.joinpath(*p.parts).resolve()
            root = out.resolve()
            if root != dest and root not in dest.parents:
                fail(f"{kind.upper()}_ARCHIVE_ESCAPE:{key}")
            dest.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as src, dest.open("wb") as dst:
                shutil.copyfileobj(src, dst, 1024 * 1024)
    return out


def load_glb_json(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    if len(raw) < 20:
        fail("GLB_TOO_SMALL")
    magic, version, declared = struct.unpack_from("<4sII", raw, 0)
    if magic != b"glTF" or version != 2 or declared != len(raw):
        fail("GLB_HEADER_INVALID")
    pos = 12
    js = None
    while pos + 8 <= len(raw):
        n, typ = struct.unpack_from("<II", raw, pos)
        pos += 8
        chunk = raw[pos:pos+n]
        pos += n
        if typ == 0x4E4F534A:
            if js is not None:
                fail("GLB_MULTIPLE_JSON")
            js = chunk
    if js is None:
        fail("GLB_JSON_MISSING")
    return json.loads(js.rstrip(b"\x00 \t\r\n").decode("utf-8"))


def choose_primary(root: Path) -> tuple[Path, dict[str, Any]]:
    scene = sorted(root.rglob("scene.gltf"))
    if len(scene) == 1:
        p = scene[0]
        return p, json.loads(p.read_text(encoding="utf-8"))
    candidates = sorted(root.rglob("*.gltf")) + sorted(root.rglob("*.glb"))
    if len(candidates) != 1:
        fail(f"PRIMARY_SCENE_AMBIGUOUS:{[str(x.relative_to(root)) for x in candidates[:20]]}")
    p = candidates[0]
    return p, load_glb_json(p) if p.suffix.lower() == ".glb" else json.loads(p.read_text(encoding="utf-8"))


def resource_gate(path: Path, data: dict[str, Any]) -> None:
    for group in ("buffers", "images"):
        for item in data.get(group) or []:
            if not isinstance(item, dict):
                continue
            uri = item.get("uri")
            if not isinstance(uri, str) or not uri or uri.startswith("data:"):
                continue
            parsed = urllib.parse.urlparse(uri)
            if parsed.scheme or uri.startswith("//"):
                fail(f"EXTERNAL_GLTF_RESOURCE:{uri}")
            candidate = (path.parent / urllib.parse.unquote(parsed.path)).resolve()
            if path.parent.resolve() not in candidate.parents and candidate != path.parent.resolve():
                fail(f"GLTF_RESOURCE_ESCAPE:{uri}")
            if not candidate.is_file():
                fail(f"GLTF_RESOURCE_MISSING:{uri}")


def geometry_stats(data: dict[str, Any]) -> dict[str, int]:
    accessors = data.get("accessors") or []
    meshes = data.get("meshes") or []
    vertices = 0
    triangles = 0
    primitives = 0
    for mesh in meshes:
        if not isinstance(mesh, dict):
            continue
        for prim in mesh.get("primitives") or []:
            if not isinstance(prim, dict):
                continue
            primitives += 1
            attrs = prim.get("attributes") or {}
            pos = attrs.get("POSITION") if isinstance(attrs, dict) else None
            if isinstance(pos, int) and 0 <= pos < len(accessors):
                vertices += int((accessors[pos] or {}).get("count") or 0)
            mode = int(prim.get("mode", 4))
            if mode != 4:
                continue
            idx = prim.get("indices")
            if isinstance(idx, int) and 0 <= idx < len(accessors):
                triangles += int((accessors[idx] or {}).get("count") or 0) // 3
            elif isinstance(pos, int) and 0 <= pos < len(accessors):
                triangles += int((accessors[pos] or {}).get("count") or 0) // 3
    return {
        "meshCount": len(meshes),
        "primitiveCount": primitives,
        "vertexCount": vertices,
        "triangleCount": triangles,
        "materialCount": len(data.get("materials") or []),
        "textureCount": len(data.get("textures") or []),
        "imageCount": len(data.get("images") or []),
        "nodeCount": len(data.get("nodes") or []),
    }


def geometry_gate(kind: str, stats: dict[str, int]) -> None:
    s = SPECS[kind]
    if stats["meshCount"] < s["meshMin"]:
        fail(f"{kind.upper()}_MESH_COUNT_TOO_LOW:{stats['meshCount']}")
    if not (s["vertexMin"] <= stats["vertexCount"] <= s["vertexMax"]):
        fail(f"{kind.upper()}_VERTEX_COUNT_OUT_OF_RANGE:{stats['vertexCount']}")
    if not (s["triangleMin"] <= stats["triangleCount"] <= s["triangleMax"]):
        fail(f"{kind.upper()}_TRIANGLE_COUNT_OUT_OF_RANGE:{stats['triangleCount']}")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def run_one(kind: str) -> dict[str, Any]:
    spec = SPECS[kind]
    detail = request_json(f"{API}/{spec['uid']}")
    provenance = validate_detail(kind, detail)
    archive, transport = download_archive(kind)
    extracted = extract_archive(kind, archive)
    primary, data = choose_primary(extracted)
    if str((data.get("asset") or {}).get("version") or "").split(".")[0] != "2":
        fail(f"{kind.upper()}_GLTF_VERSION_NOT_2")
    resource_gate(primary, data)
    stats = geometry_stats(data)
    geometry_gate(kind, stats)
    primary_sha = sha256_file(primary)
    return {
        "kind": kind,
        "sourceIdentity": provenance,
        "sourceUidGate": True,
        "fullGeometryGate": True,
        "representation": "SOURCE_GLTF_ARCHIVE",
        "primaryScene": str(primary),
        "primarySceneSha256": primary_sha,
        "uploadedReferenceSha256": spec["uploadedReferenceSha256"],
        "binaryShaMatchRequired": False,
        "identityBasis": "EXACT_SKETCHFAB_UID_PLUS_GEOMETRY_RANGE_PLUS_SOURCE_METADATA",
        "internalTestOnly": kind == "bugatti",
        "transport": transport,
        "geometry": stats,
    }


def main() -> None:
    results = {kind: run_one(kind) for kind in ("bugatti", "bulldozer")}
    out = {
        "status": "PASS",
        "scope": "ISS_VISUAL_V4_ASSET_PREFLIGHT",
        "visualProxyForbidden": True,
        "quant120Forbidden": True,
        "assets": results,
    }
    (ROOT / "assets.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("ASSET_PREFLIGHT=PASS")
    for kind, row in results.items():
        g = row["geometry"]
        print(f"{kind.upper()}_FULL_GEOMETRY=PASS|meshes={g['meshCount']}|vertices={g['vertexCount']}|triangles={g['triangleCount']}")
        print(f"{kind.upper()}_PRIMARY_SCENE={row['primaryScene']}")


if __name__ == "__main__":
    main()
