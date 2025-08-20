from utils import execute


class MusicPlayer:
    def __init__(self):
        pass

    def is_playing(self):
        return execute("playerctl -p spotify status").stdout == "Playing\n"

    # Title, Artist, Position, Track Length, Album Cover
    def get_metadata(self):
        data = []
        tags = {
            "title": '', "artist": '', "mpris:length": 0, "mpris:artUrl": ''
        }
        for tag in tags.keys():
            try:
                data_point = execute(f"playerctl -p spotify metadata {tag}").stdout[:-1]
                if tag == "mpris:length":
                    data_point = int(data_point[:-6])
                data.append(data_point)
            except Exception as e:
                print(e)
                data.append(tags[tag])
        data.insert(2, execute("playerctl -p spotify position").stdout[:-1])
        if data[2] != "":
            data[2] = int(float(data[2])) # Convert position to int (seconds)
        else:
            data[2] = 0
        return (data)
    

if __name__ == "__main__":
    mp = MusicPlayer()
    print(mp.is_playing())
    print(mp.get_metadata())