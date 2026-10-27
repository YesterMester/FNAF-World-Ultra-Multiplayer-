#!/usr/bin/env python3
"""Build the 32-bit Fusion extension with MSVC or an i686 MinGW compiler."""
import argparse
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
SDK_COMMIT = "a024b1117ca67713a45fcfbb5fd3c981b688f759"


def dependencies(work):
    work.mkdir(parents=True, exist_ok=True)
    sdk = work / "fusion-sdk"
    if not (sdk / "Inc/Ccxhdr.h").exists():
        archive = work / "fusion-sdk.tar.gz"
        urllib.request.urlretrieve("https://codeload.github.com/clickteam-plugin/windows/tar.gz/" + SDK_COMMIT, archive)
        with tarfile.open(archive) as tar:
            for member in tar.getmembers():
                parts = Path(member.name).parts[1:]
                if not parts or parts[0] not in ("Inc", "Lib") or not member.isfile():
                    continue
                dest = sdk.joinpath(*parts)
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(tar.extractfile(member).read())
    inc = sdk / "Inc"
    if not (sdk / "Lib/mmfs2.lib").exists():
        lib = sdk / "Lib/mmfs2.lib"
        lib.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve("https://raw.githubusercontent.com/clickteam-plugin/windows/" + SDK_COMMIT + "/Lib/mmfs2.lib", lib)
    # The original Windows SDK uses inconsistent include casing. Copies also
    # work on Linux and on Windows without permission to create symlinks.
    lookup = {f.name.lower(): f for f in inc.iterdir() if f.is_file()}
    names = set(lookup)
    for f in list(inc.iterdir()):
        if f.is_file():
            names.update(re.findall(r'#include\s+"([^"/\\]+)"', f.read_text(errors="ignore")))
    for name in names:
        if not (inc / name).exists() and name.lower() in lookup:
            shutil.copyfile(lookup[name.lower()], inc / name)
    header = work / "include/nlohmann/json.hpp"
    if not header.exists():
        header.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve("https://raw.githubusercontent.com/nlohmann/json/v3.12.0/single_include/nlohmann/json.hpp", header)
    if hashlib.sha256(header.read_bytes()).hexdigest() != "aaf127c04cb31c406e5b04a63f1ae89369fccde6d8fa7cdda1ed4f32dfc5de63":
        raise RuntimeError("Unexpected nlohmann/json header checksum")
    return inc, header.parent.parent


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--compiler", default=os.environ.get("CXX", "cl" if os.name == "nt" else "i686-w64-mingw32-g++"))
    ap.add_argument("--out", type=Path, default=ROOT / "build/online")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / "online/notices/nlohmann-json-MIT.txt", args.out / "FWUM-THIRD-PARTY-NOTICES.txt")
    inc, json_inc = dependencies(args.out / "deps")
    src = ROOT / "online/native"
    source_hash = lambda: {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in sorted(src.iterdir()) if p.suffix in (".cpp", ".hpp", ".def")}
    inputs = source_hash()
    output = args.out / "FWUMOnline.mfx"
    if Path(args.compiler).name.lower() in ("cl", "cl.exe"):
        command = [args.compiler, "/nologo", "/std:c++17", "/EHsc", "/O2", "/MT", "/LD", "/DWINVER=0x0602", "/D_WIN32_WINNT=0x0602",
                   "/I" + str(inc), "/I" + str(json_inc), str(src / "runtime.cpp"), "/link",
                   "/Brepro", "/DEF:" + str(src / "FWUMOnline.def"), "/OUT:" + str(output), str(inc.parent / "Lib/mmfs2.lib"),
                   "winhttp.lib", "user32.lib", "gdi32.lib", "advapi32.lib"]
    else:
        command = [args.compiler, "-std=c++17", "-shared", "-static", "-O2", "-fms-extensions", "-Wno-nonportable-include-path",
                   "-Wno-ignored-attributes", "-Wno-return-type", "-Wno-extra-tokens", "-DWINVER=0x0602", "-D_WIN32_WINNT=0x0602",
                   "-I" + str(inc), "-I" + str(json_inc), str(src / "runtime.cpp"), str(src / "FWUMOnline.def"),
                   "-Wl,--no-insert-timestamp", "-o", str(output), str(inc.parent / "Lib/mmfs2.lib"), "-lwinhttp", "-luser32", "-lgdi32", "-ladvapi32"]
    subprocess.run(command, check=True, cwd=args.out)
    if source_hash() != inputs:
        raise RuntimeError("Native sources changed during compilation; rebuild before using this extension.")
    print("Built", output)
    print("SHA-256", hashlib.sha256(output.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
