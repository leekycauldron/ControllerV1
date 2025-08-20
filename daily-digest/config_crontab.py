#!/usr/bin/env python3
"""
cron_wakeup_manager.py

Manage a single crontab entry that runs a given Python script (e.g., "wakeup.py").

Capabilities:
- get_scheduled_time(script_name): returns (hour, minute) for a simple daily cron like "MM HH * * * ..."
- set_scheduled_time(script_name, when_dt, create_if_missing=False, command_if_create=None):
    updates that entry to when_dt.hour / when_dt.minute. Optionally creates it.

Assumptions / limitations:
- Expects a single matching cron line for the script. Raises if 0 or >1 matches (unless create_if_missing=True).
- Only "simple daily" schedules are supported for reading (i.e., minute and hour are specific integers,
  and day-of-month, month, day-of-week are "*" or simple exact forms). For updating, we just replace
  the minute and hour fields and keep the rest.
"""

import subprocess
from datetime import datetime
from typing import List, Tuple, Optional

# ========== CONFIG ==========
# The thing to look for in the COMMAND part of the cron line.
# This can be a filename like "wakeup.py" or a full path.
SCRIPT_NAME = "wakeup.py"

# Default schedule (used only if creating a new entry)
#     minute hour * * *  <command>
DEFAULT_MINUTE = 0
DEFAULT_HOUR = 7
# ========== END CONFIG ==========


class CronError(Exception):
    pass


def _run(cmd: List[str], input_text: Optional[str] = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        input=(input_text.encode() if input_text is not None else None),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def _read_crontab() -> List[str]:
    """Return current user crontab as a list of lines (without trailing newlines)."""
    cp = _run(["crontab", "-l"])
    if cp.returncode != 0:
        # If user has no crontab, some systems return nonzero; treat as empty.
        if b"no crontab for" in cp.stderr.lower():
            return []
        raise CronError(f"Failed to read crontab: {cp.stderr.decode().strip()}")
    text = cp.stdout.decode()
    return [line.rstrip("\n") for line in text.splitlines()]


def _write_crontab(lines: List[str]) -> None:
    """Overwrite user crontab with the given lines."""
    new_text = "\n".join(lines) + "\n"
    cp = _run(["crontab", "-"], input_text=new_text)
    if cp.returncode != 0:
        raise CronError(f"Failed to write crontab: {cp.stderr.decode().strip()}")


def _split_cron_line(line: str) -> Tuple[str, str, str, str, str, str]:
    """
    Split a cron line into the 5 schedule fields and the command.
    Raises if the line doesn't look like a standard cron entry.
    """
    parts = line.split(None, 5)
    if len(parts) < 6:
        raise CronError(f"Line doesn't look like a cron entry: {line!r}")
    return parts[0], parts[1], parts[2], parts[3], parts[4], parts[5]


def _is_comment_or_blank(line: str) -> bool:
    s = line.strip()
    return (not s) or s.startswith("#")


def _matches_script(line: str, script_name: str) -> bool:
    """Check if the COMMAND portion contains the script_name (simple substring)."""
    try:
        _, _, _, _, _, command = _split_cron_line(line)
    except CronError:
        return False
    return (script_name in command) and (not line.strip().startswith("#"))


def _find_matching_indices(lines: List[str], script_name: str) -> List[int]:
    return [i for i, line in enumerate(lines) if _matches_script(line, script_name)]


def get_scheduled_time(script_name: str = SCRIPT_NAME) -> Tuple[int, int]:
    """
    Return (hour, minute) of the matching cron entry.

    Only supports simple cases where minute and hour are explicit integers.
    Raises:
      - CronError if not found, multiple matches, or non-simple schedule.
    """
    lines = _read_crontab()
    idxs = _find_matching_indices(lines, script_name)
    if not idxs:
        raise CronError(f"No cron entry found containing {script_name!r}.")
    if len(idxs) > 1:
        raise CronError(f"Multiple cron entries found for {script_name!r}. Please disambiguate.")

    m, h, dom, mon, dow, _cmd = _split_cron_line(lines[idxs[0]])

    def _parse_int_field(name: str, val: str) -> int:
        if val.isdigit():
            return int(val)
        raise CronError(
            f"Unsupported {name} field {val!r}. Only exact integers supported for get_scheduled_time()."
        )

    minute = _parse_int_field("minute", m)
    hour = _parse_int_field("hour", h)

    # Very light sanity check on the rest; allow wildcards or exact numbers.
    for name, val in [("day-of-month", dom), ("month", mon), ("day-of-week", dow)]:
        allowed = val == "*" or val.isdigit()
        if not allowed:
            # We could still update time, but for "getting" we want to be honest about complexity.
            raise CronError(
                f"Non-simple schedule for {name}={val!r}. This tool only reads simple daily-like entries."
            )

    return (hour, minute)


def set_scheduled_time(
    when_dt: datetime,
    script_name: str = SCRIPT_NAME,
    create_if_missing: bool = False,
    command_if_create: Optional[str] = None,
) -> Tuple[int, int]:
    """
    Update the matching cron entry to run at when_dt.hour:when_dt.minute.

    If create_if_missing=True and no entry exists, creates a new one using:
        <minute> <hour> * * *  {command_if_create}
    If command_if_create is None, we try to infer from an existing match; if none, we raise.

    Returns (hour, minute) actually written.
    """
    target_minute = int(when_dt.minute)
    target_hour = int(when_dt.hour)

    if not (0 <= target_minute <= 59 and 0 <= target_hour <= 23):
        raise ValueError("Invalid time; hour must be 0..23 and minute 0..59.")

    lines = _read_crontab()
    idxs = _find_matching_indices(lines, script_name)

    if len(idxs) == 0:
        if not create_if_missing:
            raise CronError(
                f"No cron entry found containing {script_name!r}. "
                f"Pass create_if_missing=True with command_if_create to create one."
            )
        if not command_if_create:
            raise CronError(
                "command_if_create must be provided when creating a new entry."
            )
        # Create a new line
        new_line = f"{target_minute} {target_hour} * * * {command_if_create}"
        lines.append(new_line)
        _write_crontab(lines)
        return (target_hour, target_minute)

    if len(idxs) > 1:
        raise CronError(f"Multiple cron entries found for {script_name!r}. Please disambiguate.")

    i = idxs[0]
    m, h, dom, mon, dow, cmd = _split_cron_line(lines[i])

    # Replace minute and hour, keep the rest as-is.
    lines[i] = f"{target_minute} {target_hour} {dom} {mon} {dow} {cmd}"
    _write_crontab(lines)
    return (target_hour, target_minute)


# ---------- Convenience wrappers the way you asked for ----------

def get_task_time(script_name: str = SCRIPT_NAME) -> Tuple[int, int]:
    """Alias that returns (hour, minute)."""
    return get_scheduled_time(script_name)


def change_task_time(when_dt: datetime, script_name: str = SCRIPT_NAME) -> Tuple[int, int]:
    """
    Alias that updates the time using a datetime object (so you can do hour=7, minute=0).
    Returns (hour, minute) written.
    """
    
    return set_scheduled_time(when_dt, script_name, create_if_missing=True, command_if_create=f"/usr/bin/python3 {script_name} >> /home/bryson/wakeup.log 2>&1")


# ---------- Set Alarm Here ----------
if __name__ == "__main__":
    # Example: read time for "wakeup.py"
    try:
        h, m = get_task_time("wakeup.py")
        print(f"Current schedule for wakeup.py: {h:02d}:{m:02d}")
    except CronError as e:
        print(f"[INFO] {e}")

    # Set 10 minutes before desired wake up time.
    new_h, new_m = change_task_time(datetime.now().replace(hour=6, minute=50, second=0, microsecond=0),
                                     script_name="/home/bryson/code_projects/ControllerV1/daily-digest/entry_prep.py")
    print(f"Updated schedule for wakeup.py: {new_h:02d}:{new_m:02d}")
