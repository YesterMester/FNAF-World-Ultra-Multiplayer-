#!/usr/bin/env python3
"""FNaF World Ultra Multiplayer patcher (command line).

  python3 patch.py --download --out "FNaF World Ultra Multiplayer"
  python3 patch.py --ultra "<FNaF World Ultra folder>" --mp "<fnaf-world-multiplayer-beta.exe>" --out "<folder>"

Without arguments the graphical patcher opens.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fwump import download  # noqa: E402
from fwump.merge import MergeError  # noqa: E402
from fwump.pipeline import build  # noqa: E402


def main():
    if len(sys.argv) == 1:
        from gui import run_gui
        return run_gui()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ultra", help="folder containing 'Fnaf World Ultra.exe' and 'Fnaf World Ultra.dat'")
    ap.add_argument("--mp", help="FNaF World Local Multiplayer exe (fnaf-world-multiplayer-beta.exe)")
    ap.add_argument("--download", action="store_true",
                    help="download whichever of the two games was not given from Game Jolt")
    ap.add_argument("--downloads", default="fwum-downloads", help="where downloads are kept")
    ap.add_argument("--out", required=True, help="output folder for the merged game")
    ap.add_argument("--debug", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--test-jump", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--baseline", action="store_true", help=argparse.SUPPRESS)
    args = ap.parse_args()
    try:
        ultra, mp = args.ultra, args.mp
        if not ultra or not mp:
            if not args.download:
                ap.error("give --ultra and --mp, or use --download")
            if not ultra:
                ultra = download.get_ultra(args.downloads)
            if not mp:
                mp = download.get_mp(args.downloads)
        build(ultra, mp, args.out, debug=args.debug, test_jump=args.test_jump, baseline=args.baseline)
    except (MergeError, RuntimeError, OSError) as e:
        print("error:", e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
