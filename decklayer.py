from PIL import Image, ImageDraw, ImageFont
from StreamDeck.ImageHelpers import PILHelper
import threading
import time

class DeckLayer:
    def __init__(self, deck, rows, cols):
        self.rows = rows
        self.cols = cols
        self.deck = deck
        self.deck.open()
        self.deck.reset()
        self.deck.set_brightness(50)

        self.font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
        self.pages = []
        self.current_page = 0
        self.grid = []
        self.key_callbacks = {}
        self.running = True
        self.deck_lock = threading.Lock()

        self.deck.set_key_callback(self._key_change)

    def _key_change(self, deck, key, state):
        if state and key in self.key_callbacks:
            if self._is_enabled(self.grid[key]):
                self.key_callbacks[key]()  # Only call if enabled

    def _is_enabled(self, key_dict):
        enabled = key_dict.get("enabled", True)
        return enabled() if callable(enabled) else bool(enabled)

    def _make_image(self, text="", image_path=None, disabled=False):
        # Evaluate image_path if it's a function
        if callable(image_path):
            try:
                image_path = image_path()
            except Exception as e:
                print(f"[DeckLayer] Failed to evaluate image lambda: {e}")
                image_path = None

        # Create base image and drawing context
        image = PILHelper.create_image(self.deck)
        draw = ImageDraw.Draw(image)

        # Set background and text color based on disabled state
        bg_color = "gray" if disabled else "black"
        text_color = "darkgray" if disabled else "white"
        draw.rectangle((0, 0, image.size[0], image.size[1]), fill=bg_color)

        # Load and paste the icon if available
        if image_path:
            try:
                icon = Image.open(image_path).resize(image.size).convert("RGBA")
                image.paste(icon, (0, 0), icon)  # Use alpha for transparency
            except Exception as e:
                print(f"[DeckLayer] Error loading image '{image_path}': {e}")

        # Draw text label (only if no image OR you want both)
        elif text:
            draw.text((10, 10), text, fill=text_color, font=self.font)

        return PILHelper.to_native_format(self.deck, image)


    def update_key(self, i, text=None, image_path=None):
        if i >= len(self.grid):
            return
        key = self.grid[i]
        if text is not None:
            key['text'] = text
        if image_path is not None:
            key['image'] = image_path
        disabled = not self._is_enabled(key)
        image = self._make_image(key.get('text', ''), key.get('image'), disabled)
        with self.deck_lock:
            self.deck.set_key_image(i, image)

    def update_all_states(self):
        for i, key in enumerate(self.grid):
            disabled = not self._is_enabled(key)
            image = self._make_image(key.get('text', ''), key.get('image'), disabled=disabled)
            with self.deck_lock:
                self.deck.set_key_image(i, image)

    def set_page(self, page_index):
        if page_index >= len(self.pages):
            return

        with self.deck_lock:
            self.deck.reset()

        self.current_page = page_index
        flat = []
        for row in self.pages[page_index]:
            padded_row = row + [{"text": ""}] * (self.cols - len(row))
            flat.extend(padded_row)

        while len(flat) < self.rows * self.cols:
            flat.append({"text": ""})

        self.grid = flat[:self.rows * self.cols]
        self._apply_grid()

    def _apply_grid(self):
        self.key_callbacks.clear()
        for i, key in enumerate(self.grid):
            disabled = not self._is_enabled(key)
            image = self._make_image(key.get('text', ''), key.get('image'), disabled=disabled)
            with self.deck_lock:
                self.deck.set_key_image(i, image)
            if 'callback' in key:
                self.key_callbacks[i] = key['callback']

    def add_page(self, grid):
        self.pages.append(grid)

    def close(self):
        self.running = False
        with self.deck_lock:
            self.deck.reset()
            self.deck.close()
