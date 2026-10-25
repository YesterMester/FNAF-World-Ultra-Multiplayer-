"""Fetches FNaF World Ultra and FNaF World Local Multiplayer from their Game Jolt pages."""
import json
import os
import shutil
import ssl
import urllib.request
import zipfile

try:  # bundled CA list, so downloads also work where the system store isn't found
    import certifi
    _CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _CTX = ssl.create_default_context()

ULTRA_GAME_ID = 996891   # https://gamejolt.com/games/FWU/996891
MP_GAME_ID = 937743      # https://gamejolt.com/games/FWLOCAL/937743

API = "https://gamejolt.com/site-api/web/discover/games"
UA = {"User-Agent": "FWU-Multiplayer-Patcher/1.0"}


def _get_json(url, data=None):
    req = urllib.request.Request(url, data=data, headers=dict(UA, **({"Content-Type": "application/json"}
                                                                       if data is not None else {})))
    with urllib.request.urlopen(req, timeout=60, context=_CTX) as r:
        return json.loads(r.read().decode("utf-8"))


def _windows_builds(game_id):
    ov = _get_json("%s/overview/%d" % (API, game_id))["payload"]
    releases = {r["id"]: r for r in ov.get("releases", [])}
    builds = []
    for b in ov.get("builds", []):
        if not (b.get("os_windows") or b.get("os_windows_64")):
            continue
        rel = releases.get(b.get("game_release_id"), {})
        builds.append((rel.get("published_on") or 0, rel.get("version_number", "?"), b))
    builds.sort(key=lambda x: x[0], reverse=True)
    return builds


def latest_windows_build(game_id):
    builds = _windows_builds(game_id)
    if not builds:
        raise RuntimeError("no Windows download found on Game Jolt for game %d" % game_id)
    _, version, b = builds[0]
    return version, b


def download_url(build_id):
    return _get_json("%s/builds/get-download-url/%d" % (API, build_id), data=b"{}")["payload"]["url"]


def fetch(url, dest, progress=None):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=120, context=_CTX) as r, open(dest + ".part", "wb") as out:
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            out.write(chunk)
            done += len(chunk)
            if progress:
                progress(done, total)
    os.replace(dest + ".part", dest)


def get_ultra(workdir, log=print, progress=None):
    """Download and unpack the latest FNaF World Ultra PC build. Returns its folder."""
    version, b = latest_windows_build(ULTRA_GAME_ID)
    name = b["primary_file"]["filename"]
    log("FNaF World Ultra %s: downloading %s ..." % (version, name))
    os.makedirs(workdir, exist_ok=True)
    archive = os.path.join(workdir, name)
    target = os.path.join(workdir, "FNaF World Ultra %s" % version)
    if os.path.isdir(target):
        return find_ultra_folder(target)
    if not os.path.exists(archive):
        fetch(download_url(b["id"]), archive, progress)
    if not name.lower().endswith(".zip"):
        raise RuntimeError("Ultra came as %s, which this patcher cannot unpack. Extract it yourself "
                           "and choose the folder instead." % name)
    if not os.path.isdir(target):
        log("unpacking ...")
        with zipfile.ZipFile(archive) as z:
            z.extractall(target + ".tmp")
        os.replace(target + ".tmp", target)
        os.remove(archive)
    return find_ultra_folder(target)


def get_mp(workdir, log=print, progress=None):
    """Download the FNaF World Local Multiplayer exe. Returns its path."""
    version, b = latest_windows_build(MP_GAME_ID)
    name = b["primary_file"]["filename"]
    log("FNaF World Local Multiplayer %s: downloading %s ..." % (version, name))
    os.makedirs(workdir, exist_ok=True)
    dest = os.path.join(workdir, name)
    if not os.path.exists(dest):
        fetch(download_url(b["id"]), dest, progress)
    return dest


def find_ultra_folder(root):
    for dirpath, dirnames, filenames in os.walk(root):
        if "Fnaf World Ultra.dat" in filenames:
            return dirpath
    raise RuntimeError("'Fnaf World Ultra.dat' not found under %s" % root)


def clean(workdir):
    shutil.rmtree(workdir, ignore_errors=True)
