import io, struct, sys, argparse, requests, serial
from PIL import Image

def fetch_image(url: str) -> Image.Image:
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    return Image.open(io.BytesIO(r.content)).convert("RGB")

def center_fit(img: Image.Image, target_w: int, target_h: int, bg=(0,0,0)) -> Image.Image:
    """Scale to fit within target, keep aspect, pad with bg."""
    src_w, src_h = img.size
    scale = min(target_w/src_w, target_h/src_h)
    new_w, new_h = int(src_w*scale), int(src_h*scale)
    resized = img.resize((new_w, new_h), Image.LANCZOS)
    canvas = Image.new("RGB", (target_w, target_h), bg)
    x = (target_w - new_w)//2
    y = (target_h - new_h)//2
    canvas.paste(resized, (x, y))
    return canvas

def to_rgb565_bytes(img: Image.Image) -> bytes:
    """Convert RGB PIL image to RGB565 little-endian bytes."""
    assert img.mode == "RGB"
    out = bytearray()
    for r, g, b in img.getdata():
        rgb565 = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
        out += struct.pack("<H", rgb565)
    return bytes(out)

def send_frame(ser: serial.Serial, fmt: int, w: int, h: int, payload: bytes):
    # IMG0 header: <4sHHBI
    header = struct.pack("<4sHHBI", b"IMG0", w, h, fmt, len(payload))
    ser.write(header)
    ser.write(payload)
    ser.flush()

def send_jpeg(url: str, port: str, baud=921600, target=(320,240), quality=85):
    img = fetch_image(url)
    fitted = center_fit(img, target[0], target[1])
    buf = io.BytesIO()
    fitted.save(buf, format="JPEG", quality=quality, optimize=True)
    jpg = buf.getvalue()
    with serial.Serial(port, baudrate=baud, timeout=5) as ser:
        send_frame(ser, fmt=1, w=target[0], h=target[1], payload=jpg)

def send_rgb565(url: str, port: str, baud=921600, target=(320,240)):
    img = fetch_image(url)
    fitted = center_fit(img, target[0], target[1])
    rgb565 = to_rgb565_bytes(fitted)
    with serial.Serial(port, baudrate=baud, timeout=5) as ser:
        send_frame(ser, fmt=2, w=target[0], h=target[1], payload=rgb565)

# ----------------------
# NEW: metadata & progress messages over Serial
# ----------------------

def send_meta(port: str, title: str, artist: str, duration_sec: int, baud=921600):
    """
    META(type=1): <4s B H H I> + title_bytes + artist_bytes
      magic="META", type=1, title_len, artist_len, duration_sec
    """
    t_bytes = title.encode("utf-8")
    a_bytes = artist.encode("utf-8")
    header = struct.pack("<4sBHHI", b"META", 1, len(t_bytes), len(a_bytes), int(duration_sec))
    with serial.Serial(port, baudrate=baud, timeout=5) as ser:
        ser.write(header)
        ser.write(t_bytes)
        ser.write(a_bytes)
        ser.flush()

def send_pos(port: str, position_sec: int, baud=921600):
    """
    META(type=2): <4s B I>
      magic="META", type=2, position_sec
    """
    header = struct.pack("<4sBI", b"META", 2, int(position_sec))
    with serial.Serial(port, baudrate=baud, timeout=5) as ser:
        ser.write(header)
        ser.flush()

def main():
    p = argparse.ArgumentParser(description="Send album cover and/or metadata/progress over Serial")
    sub = p.add_subparsers(dest="cmd", required=True)

    # send image (jpeg or rgb565)
    sp_img = sub.add_parser("jpeg", help="Send fitted JPEG")
    sp_img.add_argument("port")
    sp_img.add_argument("url")
    sp_img.add_argument("--w", type=int, default=320)
    sp_img.add_argument("--h", type=int, default=240)
    sp_img.add_argument("--quality", type=int, default=85)

    sp_rgb = sub.add_parser("rgb", help="Send fitted RGB565")
    sp_rgb.add_argument("port")
    sp_rgb.add_argument("url")
    sp_rgb.add_argument("--w", type=int, default=320)
    sp_rgb.add_argument("--h", type=int, default=240)

    # send meta (title/artist/duration)
    sp_meta = sub.add_parser("meta", help="Send title/artist/duration")
    sp_meta.add_argument("port")
    sp_meta.add_argument("--title", required=True)
    sp_meta.add_argument("--artist", required=True)
    sp_meta.add_argument("--duration", required=True, type=int, help="Track length in seconds")

    # send position only
    sp_pos = sub.add_parser("pos", help="Send position only")
    sp_pos.add_argument("port")
    sp_pos.add_argument("--pos", required=True, type=int, help="Position in seconds")

    args = p.parse_args()

    if args.cmd == "jpeg":
        send_jpeg(args.url, args.port, target=(args.w, args.h), quality=args.quality)
        print("Sent JPEG")
    elif args.cmd == "rgb":
        send_rgb565(args.url, args.port, target=(args.w, args.h))
        print("Sent RGB565")
    elif args.cmd == "meta":
        send_meta(args.port, args.title, args.artist, args.duration)
        print("Sent META")
    elif args.cmd == "pos":
        send_pos(args.port, args.pos)
        print("Sent position")

if __name__ == "__main__":
    main()
