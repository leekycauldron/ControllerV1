from utils import execute


class MusicPlayer:
    def __init__(self):
        pass

    def is_playing(self):
        return execute("playerctl status").stdout == "Playing\n"

    # Title, Artist, Position, Track Length, Album Cover
    def get_metadata(self):
        try:
            data = execute("playerctl metadata --format '{{title}}|{{artist}}|{{mpris:length}}|{{mpris:artUrl}}'").stdout.split('|')
            data.insert(2, execute("playerctl position").stdout[:-1])
            if data[1] == 'DJ X':
                return ['Up Next', 'DJ X', 0,0,'']
            # Clean Data
            data[-1] = data[-1][:-1]#  Remove trailing \n and ' in album cover
            #data[0] = data[0][1:] # Remove starting ' in title
            data[2] = int(float(data[2])) # Convert position to int (seconds)
            data[3] = int(data[3][:-6]) # Convert track length to int (seconds)
            return data
        except:
            print(data)
    

if __name__ == "__main__":
    mp = MusicPlayer()
    print(mp.is_playing())
    print(mp.get_metadata())