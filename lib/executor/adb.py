import subprocess
import sys
from utils.status import bad

def adb(cmd):
    command = ["adb"] + cmd

    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )

    if result.returncode != 0:
        bad(" ".join(command))
        print(result.stdout.strip())
        sys.exit(1)

    return result.stdout.strip()