import subprocess, shlex, re


def execute(command: str):
    return subprocess.run(shlex.split(command), capture_output=True, text=True)
