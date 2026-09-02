#!/usr/bin/env python3
"""Admin CLI for Livestock Dashboard."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))


def cmd_upload(args):
    import requests

    with open(args.file, "rb") as f:
        r = requests.post(
            f"{args.api}/api/admin/farms/{args.farm}/upload",
            headers={"Authorization": f"Bearer {args.token}"},
            files={"file": f},
            data={"duplicate_mode": args.mode},
        )
    print(r.json())


def cmd_seed(args):
    from scripts.seed import main
    main()


def main():
    parser = argparse.ArgumentParser(description="Livestock Dashboard Admin CLI")
    sub = parser.add_subparsers(dest="command")

    upload = sub.add_parser("upload", help="Upload CSV for a farm")
    upload.add_argument("--farm", required=True)
    upload.add_argument("--file", required=True)
    upload.add_argument("--mode", default="skip", choices=["skip", "overwrite"])
    upload.add_argument("--api", default="http://localhost:8000")
    upload.add_argument("--token", required=True)

    sub.add_parser("seed", help="Seed database with users and KF sample data")

    args = parser.parse_args()
    if args.command == "upload":
        cmd_upload(args)
    elif args.command == "seed":
        cmd_seed(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
