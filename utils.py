import subprocess, shlex, re


def execute(command: str, volume=False):
    if volume:
        r=  subprocess.run(shlex.split(command), capture_output=True, text=True)
        if r.returncode != 0:
            return None
        m = re.search(r"(\d{1,3})%", r.stdout)
        return int(m.group(1)) if m else None
    return subprocess.run(shlex.split(command), capture_output=True, text=True)
