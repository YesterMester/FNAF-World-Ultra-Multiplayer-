#!/usr/bin/env python3
"""Promote an already tested CI build; never rebuild during publication."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess


ARTIFACTS = {
    "FWUM-Online-Extension": "FWUMOnline.mfx",
    "FWUM-Patcher-Windows": "FWUM-Patcher-Windows.exe",
    "FWUM-Patcher-Linux-SteamDeck": "FWUM-Patcher-Linux-SteamDeck",
}
REQUIRED_CHECKS = {
    "embedded_native_matches",
    "party_and_ownership",
    "battle_and_reserves",
    "independent_cameras",
    "npc_lineups",
    "controller_menus",
    "minigames",
    "saved_progress_preserved",
    "paired_release_artifact",
}


def gh(*args, capture=False):
    return subprocess.run(
        ["gh", *map(str, args)],
        check=True,
        text=True,
        stdout=subprocess.PIPE if capture else None,
    ).stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "manifest", nargs="?", default=os.environ.get("QUALIFICATION_MANIFEST")
    )
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    if not args.manifest:
        parser.error("a committed qualification manifest is required")
    root = Path(__file__).resolve().parents[1]
    path = (root / args.manifest).resolve()
    if not path.is_relative_to(root / "qa/releases"):
        raise SystemExit("Qualification manifests must be under qa/releases/.")
    manifest = json.loads(path.read_text())
    if manifest.get("schema") != 1 or manifest.get("status") != "passed":
        raise SystemExit("The build has not passed release qualification.")
    if any(manifest.get("checks", {}).get(key) is not True for key in REQUIRED_CHECKS):
        raise SystemExit("A required release qualification check is missing.")
    commit = manifest["source_commit"]
    version = manifest["version"]
    if not re.fullmatch(r"[a-f0-9]{40}", commit) or not re.fullmatch(
        r"\d+\.\d+\.\d+", version
    ):
        raise SystemExit("Invalid release version or source commit.")
    repository = os.environ["GITHUB_REPOSITORY"]
    run_id = int(manifest["run_id"])
    run = json.loads(
        gh("api", f"repos/{repository}/actions/runs/{run_id}", capture=True)
    )
    if (
        run["head_sha"] != commit
        or run["conclusion"] != "success"
        or run["name"] != "Build patcher"
        or run["head_repository"]["full_name"] != repository
    ):
        raise SystemExit(
            "The qualification does not match a successful build of this repository."
        )
    output = root / "dist/qualified" / str(run_id)
    output.mkdir(parents=True, exist_ok=True)
    files = {}
    checksums = []
    for artifact, filename in ARTIFACTS.items():
        wanted = manifest["artifacts"][filename]
        if not re.fullmatch(r"[a-f0-9]{64}", wanted):
            raise SystemExit("Invalid qualified artifact checksum.")
        folder = output / artifact
        matches = [p for p in folder.rglob(filename) if p.is_file()]
        if not matches:
            gh(
                "run",
                "download",
                run_id,
                "--repo",
                repository,
                "--name",
                artifact,
                "--dir",
                folder,
            )
            matches = [p for p in folder.rglob(filename) if p.is_file()]
        if (
            len(matches) != 1
            or hashlib.sha256(matches[0].read_bytes()).hexdigest() != wanted
        ):
            raise SystemExit(f"{filename} differs from the tested artifact.")
        files[filename] = matches[0]
        if filename != "FWUMOnline.mfx":
            checksums.append(f"{wanted}  {filename}\n")
    sums = output / "SHA256SUMS.txt"
    sums.write_text(
        f"# Source commit: {commit}\n"
        f"# Embedded FWUMOnline.mfx: {manifest['artifacts']['FWUMOnline.mfx']}\n"
        + "".join(checksums)
    )
    notes = output / "release-notes.md"
    notes.write_text(
        (root / ".github/RELEASE_NOTES.md").read_text()
        + f"\nSource: [{commit[:12]}](https://github.com/{repository}/tree/{commit}).\n"
    )
    files["FWUM-Patcher-Linux-SteamDeck"].chmod(0o755)
    if not args.publish:
        print("Verified the qualified artifacts:", output)
        return
    tag = "v" + version

    def optional(path):
        result = subprocess.run(["gh", "api", path], capture_output=True, text=True)
        if result.returncode == 0:
            return json.loads(result.stdout)
        if "HTTP 404" in result.stderr:
            return None
        raise SystemExit(
            "Could not verify the existing release/tag: " + result.stderr.strip()
        )

    ref = optional(f"repos/{repository}/git/ref/tags/{tag}")
    if ref:
        obj = ref["object"]
        for _ in range(4):
            if obj["type"] != "tag":
                break
            obj = json.loads(
                gh("api", f"repos/{repository}/git/tags/{obj['sha']}", capture=True)
            )["object"]
        if obj["type"] != "commit" or obj["sha"] != commit:
            raise SystemExit("The existing tag points at a different source commit.")
    existing = optional(f"repos/{repository}/releases/tags/{tag}")
    if existing:
        if not existing["draft"]:
            raise SystemExit(
                "That version is already published; it will not be overwritten."
            )
        target = json.loads(
            gh(
                "api",
                f"repos/{repository}/commits/{existing['target_commitish']}",
                capture=True,
            )
        )["sha"]
        if target != commit:
            raise SystemExit("The existing draft targets a different source commit.")
    else:
        gh(
            "release",
            "create",
            tag,
            "--repo",
            repository,
            "--target",
            commit,
            "--draft",
            "--title",
            f"FNaF World Ultra Multiplayer v{version}",
            "--notes-file",
            notes,
        )
    gh(
        "release",
        "upload",
        tag,
        files["FWUM-Patcher-Windows.exe"],
        files["FWUM-Patcher-Linux-SteamDeck"],
        sums,
        root / "LICENSE",
        "--repo",
        repository,
        "--clobber",
    )
    gh(
        "release",
        "edit",
        tag,
        "--repo",
        repository,
        "--draft=false",
        "--latest",
        "--notes-file",
        notes,
    )


if __name__ == "__main__":
    main()
