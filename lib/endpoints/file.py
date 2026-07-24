import os
import sys
import posixpath
import shlex

from lib.executor.adb import adb
from utils.status import info, good, bad, warn

DEVICE_ROOT = "/sdcard/"


def _remote_path(name: str) -> str:
    return DEVICE_ROOT + name.lstrip("/")


def _resolve(cwd: str, path: str) -> str:
    """Resolve a user-typed path against cwd, clamped inside DEVICE_ROOT."""
    target = path if path.startswith("/") else posixpath.join(cwd, path)
    target = posixpath.normpath(target)
    root = DEVICE_ROOT.rstrip("/")
    if not (target == root or target.startswith(root + "/")):
        target = root  # don't let `cd ..` escape the device root
    return target


def _is_dir(path: str) -> bool:
    check = adb(["shell", f'[ -d "{path}" ] && echo OK || echo NO'])
    return check.strip() == "OK"


def interactive_shell() -> None:
    cwd = DEVICE_ROOT.rstrip("/")
    info("Entering interactive file shell. Type 'help' for commands, 'exit' to quit.")

    while True:
        try:
            raw = input(f"adb:{cwd}$ ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not raw:
            continue

        try:
            cmd, *rest = shlex.split(raw)
        except ValueError as e:
            bad(f"Parse error: {e}")
            continue

        if cmd in ("exit", "quit"):
            break

        if cmd == "help":
            print("Commands: ls [path], cd <path>, pwd, push <local> [remote_name], pull <remote_name> [local_dest], exit")
            continue

        try:
            if cmd == "pwd":
                print(cwd)

            elif cmd == "ls":
                target = _resolve(cwd, rest[0]) if rest else cwd
                print(adb(["shell", "ls", target]))

            elif cmd == "cd":
                if not rest:
                    bad("cd requires a path")
                    continue
                target = _resolve(cwd, rest[0])
                if not _is_dir(target):
                    bad(f"No such directory: {target}")
                    continue
                cwd = target

            elif cmd == "push":
                if not rest:
                    bad("push requires <local> [remote_name]")
                    continue
                local = rest[0]
                remote_name = rest[1] if len(rest) > 1 else os.path.basename(local)
                remote_path = posixpath.join(cwd, remote_name)
                adb(["push", local, remote_path])
                good(f"Pushed to {remote_path}")

            elif cmd == "pull":
                if not rest:
                    bad("pull requires <remote_name> [local_dest]")
                    continue
                remote_name = rest[0]
                local_dest = rest[1] if len(rest) > 1 else "."
                remote_path = posixpath.join(cwd, remote_name)
                adb(["pull", remote_path, local_dest])
                good(f"Pulled {remote_path}")

            else:
                bad(f"Unknown command: {cmd}")

        except SystemExit:
            continue


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

    elif args["interactive"]:
        interactive_shell()