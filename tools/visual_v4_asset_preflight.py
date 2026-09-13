from __future__ import annotations

import hashlib
import html
import http.cookiejar
import json
import re
import shutil
import stat
import struct
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = Path("artifacts/visual-v4-preflight")
ASSET_ROOT = Path("runtime-assets/visual-v4")
ROOT.mkdir(parents=True, exist_ok=True)
ASSET_ROOT.mkdir(parents=True, exist_ok=True)

UA = "InfiniteShortsStudio-VisualV4Preflight/2.1"
MAX_BYTES = 1024 * 1024 * 1024
MAX_UNCOMPRESSED = 4 * 1024 * 1024 * 1024

SPECS: dict[str, dict[str, Any]] = {
    "bugatti": {
        "uid": "4af92c51ecdd4efa9b1c19a1163d9f46",
        "nameContains": "bugatti eb110 super sport 1992",
        "creatorContains": "alex",
        "licenseMarkers": ("noncommercial", "by-nc", "cc by-nc"),
        "referenceSha256": "8cc074c40fe9ced7271cbeddf223cd9a520dee868977ffcbd439cec1c2b62cb4",
        "transport": "https://downloadfree3d.com/file/GnYzeIxJV7DoPtIZkDg2Yg%2C%2C",
        "fingerprint": {"meshCount": 61, "materialCount": 61, "imageCount": 29, "nodeCount": 63},
        "vertexRange": (100000, 120000),
        "triangleRange": (160000, 180000),
        "internalTestOnly": True,
    },
    "bulldozer": {
        "uid": "b06a715d23a7450babac383b8bb7fb0a",
        "nameContains": "bulldozer",
        "creatorContains": "semyon",
        "licenseMarkers": ("attribution", "cc by", "by"),
        "referenceSha256": "187f81c3c4638180fb8d82c5b2bbc7510f01bc970ee149713b2de993089f1e18",
        "transport": "https://drive.google.com/uc?export=download&confirm=t&id=1HtMGJkcCHuYpQyc22eho5ammun0LLHP-",
        "fingerprint": {"meshCount": 441, "materialCount": 14, "imageCount": 44, "nodeCount": 904},
        "vertexRange": None,
        "triangleRange": None,
        "internalTestOnly": False,
    },
}


def fail(msg: str) -> None:
    raise RuntimeError(msg)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def public_json(url: str) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as r:
        raw = r.read(8 * 1024 * 1024 + 1)
    if len(raw) > 8 * 1024 * 1024:
        fail("METADATA_RESPONSE_TOO_LARGE")
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        fail("METADATA_NOT_OBJECT")
    return data


def norm_license(raw: Any) -> str:
    if isinstance(raw, dict):
        raw = " ".join(str(raw.get(k) or "") for k in ("slug", "label", "name", "fullName", "url"))
    return re.sub(r"\s+", " ", str(raw or "").lower()).strip()


def validate_metadata(kind: str) -> dict[str, Any]:
    s = SPECS[kind]
    d = public_json(f"https://api.sketchfab.com/v3/models/{s['uid']}")
    if str(d.get("uid") or "") != s["uid"]:
        fail(f"{kind.upper()}_UID_MISMATCH")
    name = str(d.get("name") or "")
    if s["nameContains"] not in name.lower():
        fail(f"{kind.upper()}_NAME_MISMATCH:{name}")
    user = d.get("user") or {}
    creator_username = str(user.get("username") or "") if isinstance(user, dict) else ""
    creator_display = str(user.get("displayName") or "") if isinstance(user, dict) else ""
    creator_candidates = (creator_username.lower(), creator_display.lower())
    if not any(s["creatorContains"] in value for value in creator_candidates):
        fail(f"{kind.upper()}_CREATOR_MISMATCH:username={creator_username}|display={creator_display}")
    if d.get("isDownloadable") is not True:
        fail(f"{kind.upper()}_NOT_DOWNLOADABLE")
    if d.get("isAgeRestricted") is True:
        fail(f"{kind.upper()}_AGE_RESTRICTED")
    tags = d.get("tags") or []
    tag_text = " ".join(str(x.get("slug") or x.get("name") or "") for x in tags if isinstance(x, dict)).lower()
    if "noai" in re.sub(r"[^a-z0-9]", "", tag_text):
        fail(f"{kind.upper()}_NOAI_TAG")
    lic = norm_license(d.get("license"))
    if not any(m in lic for m in s["licenseMarkers"]):
        fail(f"{kind.upper()}_LICENSE_MISMATCH:{lic}")
    return {
        "uid": s["uid"],
        "name": name,
        "creatorUsername": creator_username,
        "creatorDisplayName": creator_display,
        "license": lic,
        "isDownloadable": True,
    }


def html_confirm_url(raw: bytes, base_url: str) -> str | None:
    text = raw.decode("utf-8", "ignore")
    form = re.search(r'<form[^>]+action="([^"]+)"[^>]*>(.*?)</form>', text, re.I | re.S)
    if not form:
        return None
    action = html.unescape(form.group(1))
    body = form.group(2)
    params: dict[str, str] = {}
    for m in re.finditer(r'<input[^>]+name="([^"]+)"[^>]+value="([^"]*)"', body, re.I):
        params[html.unescape(m.group(1))] = html.unescape(m.group(2))
    if not params:
        return None
    return urllib.parse.urljoin(base_url, action) + "?" + urllib.parse.urlencode(params)


def download(kind: str) -> tuple[Path, dict[str, Any]]:
    s = SPECS[kind]
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    url = s["transport"]
    for attempt in range(1, 4):
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
        with opener.open(req, timeout=240) as r:
            ctype = (r.headers.get("Content-Type") or "").lower()
            dispo = (r.headers.get("Content-Disposition") or "").lower()
            if "text/html" in ctype and "attachment" not in dispo:
                page = r.read(2 * 1024 * 1024 + 1)
                if len(page) > 2 * 1024 * 1024:
                    fail(f"{kind.upper()}_HTML_GATE_TOO_LARGE")
                nxt = html_confirm_url(page, r.geturl())
                if not nxt:
                    snippet = re.sub(r"\s+", " ", page[:300].decode("utf-8", "ignore"))
                    fail(f"{kind.upper()}_TRANSPORT_HTML_NOT_FILE:{snippet}")
                url = nxt
                continue
            suffix = ".zip"
            name = dispo
            if ".glb" in name or "model/gltf-binary" in ctype:
                suffix = ".glb"
            dest = ASSET_ROOT / f"{kind}{suffix}"
            tmp = dest.with_suffix(dest.suffix + ".part")
            total = 0
            h = hashlib.sha256()
            with tmp.open("wb") as f:
                while True:
                    chunk = r.read(1024 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > MAX_BYTES:
                        fail(f"{kind.upper()}_TRANSPORT_TOO_LARGE")
                    h.update(chunk)
                    f.write(chunk)
            if total < 20:
                fail(f"{kind.upper()}_TRANSPORT_TOO_SMALL:{total}")
            head = tmp.read_bytes()[:4]
            if head == b"glTF":
                final = ASSET_ROOT / f"{kind}.glb"
            elif head[:2] == b"PK":
                final = ASSET_ROOT / f"{kind}.zip"
            else:
                fail(f"{kind.upper()}_TRANSPORT_SIGNATURE_INVALID:{head!r}")
            tmp.replace(final)
            return final, {"bytes": total, "sha256": h.hexdigest(), "finalUrl": r.geturl(), "attempt": attempt}
    fail(f"{kind.upper()}_TRANSPORT_CONFIRM_LOOP")


def safe_member(name: str) -> PurePosixPath:
    p = PurePosixPath(name.replace("\\", "/"))
    if not name or p.is_absolute() or ".." in p.parts or re.match(r"^[A-Za-z]:", name):
        fail(f"UNSAFE_ARCHIVE_MEMBER:{name}")
    return p


def extract(kind: str, path: Path) -> Path:
    if path.suffix.lower() == ".glb":
        return path
    out = ASSET_ROOT / f"{kind}-extracted"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    total = 0
    seen: set[str] = set()
    with zipfile.ZipFile(path, "r") as z:
        if len(z.infolist()) > 5000:
            fail(f"{kind.upper()}_ARCHIVE_FILE_COUNT")
        bad = z.testzip()
        if bad:
            fail(f"{kind.upper()}_ARCHIVE_CRC:{bad}")
        for info in z.infolist():
            p = safe_member(info.filename)
            key = p.as_posix().casefold()
            if key in seen:
                fail(f"{kind.upper()}_ARCHIVE_DUPLICATE:{p}")
            seen.add(key)
            mode = (info.external_attr >> 16) & 0o177777
            if stat.S_ISLNK(mode):
                fail(f"{kind.upper()}_ARCHIVE_SYMLINK:{p}")
            if info.is_dir():
                continue
            total += int(info.file_size)
            if total > MAX_UNCOMPRESSED:
                fail(f"{kind.upper()}_UNCOMPRESSED_TOO_LARGE")
            if Path(p.name).suffix.lower() in {".exe", ".dll", ".so", ".sh", ".py", ".ps1", ".bat", ".cmd", ".rar", ".7z", ".tar"}:
                fail(f"{kind.upper()}_UNSAFE_ARCHIVE_PAYLOAD:{p}")
            dest = out.joinpath(*p.parts).resolve()
            root = out.resolve()
            if dest != root and root not in dest.parents:
                fail(f"{kind.upper()}_ARCHIVE_ESCAPE:{p}")
            dest.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as src, dest.open("wb") as dst:
                shutil.copyfileobj(src, dst, 1024 * 1024)
    return out


def load_glb_json(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    if len(raw) < 20:
        fail("GLB_TOO_SMALL")
    magic, ver, declared = struct.unpack_from("<4sII", raw, 0)
    if magic != b"glTF" or ver != 2 or declared != len(raw):
        fail("GLB_HEADER_INVALID")
    pos = 12
    chunk = None
    while pos + 8 <= len(raw):
        n, typ = struct.unpack_from("<II", raw, pos)
        pos += 8
        body = raw[pos:pos+n]
        pos += n
        if typ == 0x4E4F534A:
            if chunk is not None:
                fail("GLB_MULTIPLE_JSON")
            chunk = body
    if chunk is None:
        fail("GLB_JSON_MISSING")
    return json.loads(chunk.rstrip(b"\x00 \t\r\n").decode("utf-8"))


def choose_primary(root: Path) -> tuple[Path, dict[str, Any]]:
    if root.is_file():
        return root, load_glb_json(root)
    scene = sorted(root.rglob("scene.gltf"))
    if len(scene) == 1:
        p = scene[0]
        return p, json.loads(p.read_text(encoding="utf-8"))
    all_files = sorted(root.rglob("*.glb")) + sorted(root.rglob("*.gltf"))
    if len(all_files) != 1:
        fail("PRIMARY_SCENE_AMBIGUOUS:" + ",".join(str(x.relative_to(root)) for x in all_files[:20]))
    p = all_files[0]
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
            target = (path.parent / urllib.parse.unquote(parsed.path)).resolve()
            if path.parent.resolve() not in target.parents and target != path.parent.resolve():
                fail(f"GLTF_RESOURCE_ESCAPE:{uri}")
            if not target.is_file():
                fail(f"GLTF_RESOURCE_MISSING:{uri}")


def stats(data: dict[str, Any]) -> dict[str, int]:
    acc = data.get("accessors") or []
    meshes = data.get("meshes") or []
    verts = tris = prims = 0
    for mesh in meshes:
        if not isinstance(mesh, dict):
            continue
        for prim in mesh.get("primitives") or []:
            if not isinstance(prim, dict):
                continue
            prims += 1
            attrs = prim.get("attributes") or {}
            pi = attrs.get("POSITION") if isinstance(attrs, dict) else None
            vc = int((acc[pi] or {}).get("count") or 0) if isinstance(pi, int) and 0 <= pi < len(acc) else 0
            verts += vc
            if int(prim.get("mode", 4)) != 4:
                continue
            ii = prim.get("indices")
            tris += int((acc[ii] or {}).get("count") or 0) // 3 if isinstance(ii, int) and 0 <= ii < len(acc) else vc // 3
    return {
        "meshCount": len(meshes), "primitiveCount": prims, "vertexCount": verts,
        "triangleCount": tris, "materialCount": len(data.get("materials") or []),
        "textureCount": len(data.get("textures") or []), "imageCount": len(data.get("images") or []),
        "nodeCount": len(data.get("nodes") or []),
    }


def identity_gate(kind: str, primary: Path, data: dict[str, Any], g: dict[str, int]) -> dict[str, Any]:
    s = SPECS[kind]
    if str((data.get("asset") or {}).get("version") or "").split(".")[0] != "2":
        fail(f"{kind.upper()}_GLTF_VERSION_NOT_2")
    for k, expected in s["fingerprint"].items():
        if g.get(k) != expected:
            fail(f"{kind.upper()}_FINGERPRINT_{k.upper()}:{g.get(k)}!={expected}")
    vr = s["vertexRange"]
    tr = s["triangleRange"]
    if vr and not (vr[0] <= g["vertexCount"] <= vr[1]):
        fail(f"{kind.upper()}_VERTEX_RANGE:{g['vertexCount']}")
    if tr and not (tr[0] <= g["triangleCount"] <= tr[1]):
        fail(f"{kind.upper()}_TRIANGLE_RANGE:{g['triangleCount']}")
    primary_sha = sha256_file(primary)
    binary_exact = primary_sha == s["referenceSha256"]
    if kind == "bulldozer" and not binary_exact:
        fail(f"BULLDOZER_EXACT_SHA_MISMATCH:{primary_sha}")
    return {
        "primarySceneSha256": primary_sha,
        "referenceSha256": s["referenceSha256"],
        "binaryExact": binary_exact,
        "identityVerifiedBy": "EXACT_BINARY_SHA256" if binary_exact else "EXACT_SKETCHFAB_METADATA_PLUS_STRICT_GEOMETRY_FINGERPRINT",
    }


def run_one(kind: str) -> dict[str, Any]:
    metadata = validate_metadata(kind)
    payload, transport = download(kind)
    root = extract(kind, payload)
    primary, data = choose_primary(root)
    resource_gate(primary, data)
    g = stats(data)
    identity = identity_gate(kind, primary, data, g)
    return {
        "kind": kind,
        "sourceIdentity": metadata,
        "fullGeometryGate": True,
        "representation": "FULL_SOURCE_GLTF",
        "primaryScene": str(primary),
        "transport": transport,
        "geometry": g,
        "identity": identity,
        "internalTestOnly": SPECS[kind]["internalTestOnly"],
    }


def main() -> None:
    result = {k: run_one(k) for k in ("bugatti", "bulldozer")}
    out = {
        "status": "PASS",
        "scope": "ISS_VISUAL_V4_ASSET_PREFLIGHT",
        "visualProxyForbidden": True,
        "quant120Forbidden": True,
        "assets": result,
    }
    (ROOT / "assets.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("ASSET_PREFLIGHT=PASS")
    for k, row in result.items():
        g = row["geometry"]
        print(f"{k.upper()}_FULL_GEOMETRY=PASS|meshes={g['meshCount']}|vertices={g['vertexCount']}|triangles={g['triangleCount']}")
        print(f"{k.upper()}_PRIMARY_SCENE={row['primaryScene']}")
        print(f"{k.upper()}_BINARY_EXACT={row['identity']['binaryExact']}")


if __name__ == "__main__":
    main()
