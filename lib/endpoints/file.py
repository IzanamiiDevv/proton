import os
import sys

from lib.executor.adb import adb
from utils.status import info, good, bad, warn

DEVICE_ROOT = "/sdcard/"
def _remote_path(name: str) -> str:
    return DEVICE_ROOT + name.lstrip("/")


def file(args: dict) -> None:
    if args["all"] and not args["pull"]:
        bad('"all" can only be used together with "pull" (e.g. `file pull all`).')
        sys.exit(1)

    if args["swap"]:
        if not args["local"]:
            bad('"file swap" requires -local <path> (the file to push in).')
            sys.exit(1)

        remote_name = args["remote"] or os.path.basename(args["local"])
        remote_path = _remote_path(remote_name)

        info(f"Swapping {remote_path} with local file {args['local']}")
        adb(["push", args["local"], remote_path])
        good(f"Replaced {remote_path}")

    elif args["list"]:
        info(f"Listing files in {DEVICE_ROOT}")
        output = adb(["shell", "ls", DEVICE_ROOT])
        for line in output.splitlines():
            print(line)

    elif args["pull"]:
        dest = args["local"] or "."

        if args["all"]:
            info(f"Pulling all files from {DEVICE_ROOT} to {dest}")
            adb(["pull", DEVICE_ROOT, dest])
            good(f"Pulled all files from {DEVICE_ROOT}")
        else:
            if not args["remote"]:
                bad('"file pull" requires -remote <name>, or use `file pull all`.')
                sys.exit(1)

            remote_path = _remote_path(args["remote"])
            info(f"Pulling {remote_path} to {dest}")
            adb(["pull", remote_path, dest])
            good(f"Pulled {remote_path}")

    elif args["push"]:
        if not args["local"]:
            bad('"file push" requires -local <path> (the file to push in).')
            sys.exit(1)

        remote_name = args["remote"] or os.path.basename(args["local"])
        remote_path = _remote_path(remote_name)

        info(f"Pushing {args['local']} to {remote_path}")
        adb(["push", args["local"], remote_path])
        good(f"Pushed to {remote_path}")
