#!/usr/bin/env python3
import os
import time
import vlc
from pathlib import Path

# ---- Config ----
ALARM_MP3   = "/home/bryson/code_projects/ControllerV1/daily-digest/alarm.mp3"    # change to absolute paths if you prefer
PODCAST_MP3 = "/home/bryson/code_projects/ControllerV1/daily-digest/podcast.mp3"
STOP_FLAG   = "/home/bryson/code_projects/ControllerV1/daily-digest/stop.flag"    # presence/absence flag file
RUNNING_FLAG = "/home/bryson/code_projects/ControllerV1/daily-digest/running.flag"  # indicates this program is active
POLL_SEC    = 0.1                  # how often we poll for the flag

# Volume (0.0 - 1.0)
ALARM_VOLUME   = 0.5  # example: 80%
PODCAST_VOLUME = 0.4  # example: 50%

def set_system_volume(volume: float):
    """Set system Master volume using amixer (0.0 - 1.0)."""
    percent = int(max(0, min(1, volume)) * 100)
    os.system(f"amixer set Master {percent}% >/dev/null 2>&1")

def make_player(media_path: Path) -> vlc.MediaPlayer:
    """Create a VLC player for a given file (audio-only)."""
    instance = vlc.Instance("--no-video", "--quiet")
    media = instance.media_new(str(media_path))
    player = instance.media_player_new()
    player.set_media(media)
    return player

def play_alarm_loop_until_flag(alarm_path: Path, flag_path: Path):
    """Play alarm looping until flag appears."""
    set_system_volume(ALARM_VOLUME)
    player = make_player(alarm_path)
    player.play()
    time.sleep(0.05)

    try:
        while True:
            if flag_path.exists():
                player.stop()
                return
            st = player.get_state()
            if st in (vlc.State.Ended, vlc.State.Stopped, vlc.State.NothingSpecial, vlc.State.Error):
                player.stop()
                player = make_player(alarm_path)
                player.play()
            time.sleep(POLL_SEC)
    finally:
        player.stop()

def play_podcast_once_with_interrupt(podcast_path: Path, flag_path: Path):
    """Play podcast once; if flag appears, stop immediately and delete flag.
    Also clears RUNNING_FLAG when the podcast is interrupted or finishes naturally.
    """
    set_system_volume(PODCAST_VOLUME)
    player = make_player(podcast_path)
    player.play()
    time.sleep(0.05)

    try:
        while True:
            if flag_path.exists():
                player.stop()
                # Remove the stop flag and running flag on interrupt request
                try:
                    flag_path.unlink(missing_ok=True)
                except Exception:
                    pass
                try:
                    RUNNING_FLAG.unlink(missing_ok=True)
                except Exception:
                    pass
                return

            st = player.get_state()
            if st == vlc.State.Ended:
                # Podcast finished naturally; clear running flag and exit
                try:
                    RUNNING_FLAG.unlink(missing_ok=True)
                except Exception:
                    pass
                return
            if st == vlc.State.Error:
                player.stop()
                # On error, ensure running flag is cleared as we're exiting
                try:
                    RUNNING_FLAG.unlink(missing_ok=True)
                except Exception:
                    pass
                return
            time.sleep(POLL_SEC)
    finally:
        player.stop()


def main():
    try:
        RUNNING_FLAG.parent.mkdir(parents=True, exist_ok=True)
        with open(RUNNING_FLAG, "w") as f:
            f.write(str(os.getpid()))
    except Exception:
        pass
    play_alarm_loop_until_flag(ALARM_MP3, STOP_FLAG)

    try:
        STOP_FLAG.unlink(missing_ok=True)
    except Exception:
        pass

    play_podcast_once_with_interrupt(PODCAST_MP3, STOP_FLAG)

if __name__ == "__main__":
    for p in (ALARM_MP3, PODCAST_MP3):
        if not p.exists():
            raise FileNotFoundError(f"Missing file: {p.resolve()}")
    try:
        main()
    except KeyboardInterrupt:
        pass
    finally:
        # Final safety: if the program exits for any reason and the podcast did
        # not already clear it, remove RUNNING_FLAG.
        try:
            RUNNING_FLAG.unlink(missing_ok=True)
        except Exception:
            pass
