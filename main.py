from music_player import MusicPlayer
from multiprocessing import Process
from StreamDeck.DeviceManager import DeviceManager
from decklayer import DeckLayer
from utils import execute
from pathlib import Path
from light_controller import *
import time

# TODO: Add Early Alarm dismissal -> Podcast.


STOP_FLAG   = Path("/home/bryson/code_projects/ControllerV1/daily-digest/stop.flag")    # presence/absence flag file
RUNNING_FLAG = Path("/home/bryson/code_projects/ControllerV1/daily-digest/running.flag")  # indicates this program is active
usb_out = "/dev/ttyACM0"


def m5_process():
    mp = MusicPlayer()
    current_title = ""
    try:
        while True:
            if mp.is_playing():
                metadata = mp.get_metadata()
                print(metadata)
                if current_title != metadata[0]:
                    # New song detected, update everything
                    execute(f'python send_cover.py jpeg {usb_out} {metadata[-1]}').stdout[:-1]
                    execute(f'python send_cover.py meta {usb_out} --title "{metadata[0]}" --artist "{metadata[1]}" --duration {metadata[3]}')
                    execute(f'python send_cover.py pos {usb_out} --pos {metadata[2]}')
                    current_title = metadata[0]
                else:
                    # Same song, update position only
                    execute(f'python send_cover.py pos {usb_out} --pos {metadata[2]}')

            time.sleep(0.25)
    except KeyboardInterrupt:
        return
    except Exception as e:
        print(e)

def sd_process():
    deck = DeviceManager().enumerate()[0]
    ui = DeckLayer(deck, 3, 5)

    ui.add_page([
        [{"text": "Previous Song", "callback": lambda: execute("playerctl  -p spotify previous"), "image": "assets/previous_song.jpg"},
        {"text": "Play/Pause", "callback": lambda: play_or_pause(), "image": lambda: play_or_pause(True)},
        {"text": "Next Song", "callback": lambda: execute("playerctl  -p spotify next"), "image": "assets/next_song.jpg"},
        {"text": "OFF", "callback": lambda: lights_off(), "image": "assets/lights_off.jpg"},
        {"text": "Day", "callback": lambda: set_scene("Day"), "image": "assets/day_lights.jpg"}],

        [{"text": "Rewind 10s", "callback": lambda: execute("playerctl -p spotify position 10-"), "image": "assets/rewind.jpg"},
        {"text": "Loop", "callback": lambda: loop_mode(), "image": lambda: loop_mode(True)},
        {"text": "Fast Forward 10s", "callback": lambda: execute("playerctl -p spotify position 10+"), "image": "assets/fast_forward.jpg"},
        {"text": "Night", "callback": lambda: set_scene("Night"), "image": "assets/night_lights.jpg"},
        {"text": "Read", "callback": lambda: set_scene("Reading"), "image": "assets/read.jpg"}],

        [{"text": "Mute", "callback": lambda: volume("amixer set Master 0%"), "image": "assets/mute.jpg"},
        {"text": "Volume Down", "callback": lambda: volume("amixer set Master 6%-"), "image": "assets/volume_down.jpg"},
        {"text": "Volume Up", "callback": lambda: volume("amixer set Master 6%+"), "image": "assets/volume_up.jpg"},
        {"text": "Wake Up", "callback": lambda: trigger_stop_if_running(), "image": "assets/wake_up.jpg"},
        {"text": "Sleep", "callback": lambda: execute("loginctl lock-session"), "image": "assets/sleep.jpg"}]
    ])
    ui.set_page(0)

    try:
        print("Stream Deck Online.")
        while True:
            ui.update_all_states()
            time.sleep(0.5)
    except KeyboardInterrupt:
        ui.close()
    except Exception as e:
        print('streamdeck error!',e)


def volume(query):
    execute(query)
    volume = execute("amixer get Master", True)
    execute(f"python send_cover.py vol {usb_out} --vol {volume}")

def loop_mode(readonly=False):
    try:
        loop = execute("playerctl -p spotify loop").stdout
        if loop == "None\n":
            if readonly:
                return "assets/no_loop.jpg"
            execute("playerctl -p spotify loop Playlist")
        elif loop == "Playlist\n":
            if readonly:
                return "assets/playlist_loop.jpg"
            execute("playerctl -p spotify loop Track")
        elif loop == "Track\n":
            if readonly:
                return "assets/track_loop.jpg"
            execute("playerctl -p spotify loop None")
    except Exception as e:
        print(e)
        if readonly:
            return "assets/no_loop.jpg"

def play_or_pause(readonly=False):
    try:
        if execute("playerctl -p spotify status").stdout == 'Playing\n':
            if readonly:
                return "assets/pause.jpg"
            
        else:
            if readonly:
                return "assets/play.jpg"
        execute("playerctl -p spotify play-pause")
    except:
        if readonly:
            return "assets/pause.jpg"
        
def trigger_stop_if_running():
    """If running.flag exists, create stop.flag."""
    if RUNNING_FLAG.exists():
        STOP_FLAG.write_text("stop\n") 

if __name__ == "__main__":
    p1 = Process(target=m5_process)
    p2 = Process(target=sd_process)
    p1.start()
    p2.start()

    p1.join()
    p2.join()
