from phue import Bridge
import requests


BRIDGE_IP = "192.168.1.191"

scenes = {
    # 82 = "Bryson" Room
    # Lights : {17, 16, 3}
    # Order: brightness, hue, saturation
    # NOTE: Hue & Sat values are sticky, keep polling until update.
    "Day": [[254, 8401, 142],[254, 8401, 142],[254, 8401, 142]],
    "Reading": [[168, 5346, 254],[168, 5346, 254],[168, 5346, 254]],
    "Night": [[125, 65140, 254],[125, 65140, 254],[125, 65140, 254]]
}

lights_id = [17, 16, 3]

b = Bridge(BRIDGE_IP)
b.connect()


def lights_off():
    b.set_group(82, 'on', False)

def set_scene(scene: str):
    lights = b.get_light_objects('id')
    for light in range(len(lights_id)):
        lights[lights_id[light]].on = True
        lights[lights_id[light]].brightness = scenes[scene][light][0]
        lights[lights_id[light]].hue = scenes[scene][light][1]
        lights[lights_id[light]].saturation = scenes[scene][light][2]



if __name__ == "__main__":
    set_scene("Night")
    print(b.get_light(3))