#include <M5Unified.h>

// Layout constants
static const int OVERLAY_H = 60;  // a bit taller to fit two rows cleanly
static const int PAD = 6;
static const int BAR_H = 12;
static const int GAP = 4;         // small vertical gap between rows



struct __attribute__((packed)) ImgHeader {
  char     magic[4];   // "IMG0"
  uint16_t width;
  uint16_t height;
  uint8_t  fmt;        // 1=JPEG, 2=RGB565
  uint32_t length;
};

// META packets share the same magic and vary by type.
enum MetaType : uint8_t {
  META_FULL = 1,  // title/artist/duration
  META_POS  = 2   // position only
};

// META_FULL header (followed by title and artist UTF-8 bytes)
struct __attribute__((packed)) MetaFullHeader {
  char     magic[4];   // "META"
  uint8_t  type;       // 1
  uint16_t title_len;  // bytes
  uint16_t artist_len; // bytes
  uint32_t duration;   // seconds
};

// META_POS header
struct __attribute__((packed)) MetaPosHeader {
  char     magic[4];   // "META"
  uint8_t  type;       // 2
  uint32_t position;   // seconds
};

static String g_title = "";
static String g_artist = "";
static uint32_t g_duration = 0;  // sec
static uint32_t g_position = 0;  // sec


// Progress bar sprite to prevent flicker
M5Canvas barSpr(&M5.Display);

// ---------- IO helpers ----------
bool readExact(uint8_t* dst, size_t n, uint32_t timeout_ms = 5000) {
  uint32_t start = millis();
  size_t got = 0;
  while (got < n) {
    size_t avail = Serial.available();
    if (avail) {
      got += Serial.readBytes(dst + got, n - got);
    } else {
      if (millis() - start > timeout_ms) return false;
      delay(1);
    }
  }
  return true;
}

// Read 1 byte and discard (for resync)
void dropOne() { if (Serial.available()) Serial.read(); }

// ---------- UI helpers ----------
int textWidthWithFont(const String& s, const lgfx::IFont* font) {
  M5.Display.setFont(font);
  return M5.Display.textWidth(s);
}

String ellipsizeToWidth(const String& s, int max_px, const lgfx::IFont* font) {
  if (textWidthWithFont(s, font) <= max_px) return s;
  String out = s;
  const String ell = "…";
  // Reserve width for ellipsis
  int reserve = textWidthWithFont(ell, font);
  while (out.length() && textWidthWithFont(out, font) + reserve > max_px) {
    out.remove(out.length()-1);
  }
  return out + ell;
}

static inline String mmss(uint32_t s) {
  uint32_t m = s / 60;
  uint32_t r = s % 60;
  char buf[8];
  snprintf(buf, sizeof(buf), "%u:%02u", (unsigned)m, (unsigned)r);
  return String(buf);
}

void drawTextOverlayLine() {
  int sw = M5.Display.width();
  int sh = M5.Display.height();
  int y0 = sh - OVERLAY_H;

  // Background strip
  M5.Display.fillRect(0, y0, sw, OVERLAY_H, TFT_BLACK);

  // Compose "Title · Artist"
  const lgfx::IFont* titleFont = &fonts::Font4;
  const lgfx::IFont* metaFont  = &fonts::Font2;

  String title  = g_title.length()  ? g_title  : String("(No Title)");
  String artist = g_artist.length() ? g_artist : String("(Unknown Artist)");
  String line   = title + " \xC2\xB7 " + artist; // " · " bullet

  // Ellipsize to fit width minus side padding
  int usable = sw - PAD*2;
  line = ellipsizeToWidth(line, usable, titleFont);

  // Draw the line centered-left in overlay top row
  M5.Display.setTextDatum(textdatum_t::top_left);
  M5.Display.setTextColor(TFT_WHITE, TFT_BLACK);
  M5.Display.setFont(titleFont);
  int textY = y0 + PAD;
  M5.Display.drawString(line, PAD, textY);
}


void initBarSpriteIfNeeded() {
  if (barSpr.width() > 0 && barSpr.height() > 0) return;
  int sw = M5.Display.width();

  // Leave room for times on both sides; bar spans the middle
  int timeCol = 42; // ~width for "mm:ss"
  int barW = sw - PAD*2 - timeCol*2;
  if (barW < 40) barW = 40;

  barSpr.setColorDepth(16);
  barSpr.createSprite(barW, BAR_H);
}

void drawProgressRow() {
  initBarSpriteIfNeeded();

  int sw = M5.Display.width();
  int sh = M5.Display.height();
  int y0 = sh - OVERLAY_H;

  // Row baselines
  const lgfx::IFont* metaFont = &fonts::Font2;
  M5.Display.setFont(metaFont);
  M5.Display.setTextColor(TFT_WHITE, TFT_BLACK);
  M5.Display.setTextWrap(false);

  // Y for progress row (under the title line)
  int titleRowH = M5.Display.fontHeight(metaFont) + PAD + GAP; // approx spacing below title
  int rowY = y0 + titleRowH + 2;

  // Left/right times
  String left  = mmss(g_position);
  String right = mmss(g_duration);

  // Reserve columns for times
  int timeCol = 42; // matches initBarSpriteIfNeeded
  int barX = PAD + timeCol;
  int barW = barSpr.width();

  // Draw times
  M5.Display.setTextDatum(textdatum_t::middle_left);
  M5.Display.drawString(left, PAD, rowY + BAR_H/2);

  M5.Display.setTextDatum(textdatum_t::middle_right);
  M5.Display.drawString(right, sw - PAD, rowY + BAR_H/2);

  // Build bar sprite
  barSpr.fillRect(0, 0, barW, BAR_H, TFT_DARKGREY);
  barSpr.drawRect(0, 0, barW, BAR_H, TFT_WHITE);

  uint32_t dur = g_duration ? g_duration : 1;
  float frac = min(1.0f, (float)g_position / (float)dur);
  int fillW = (int)((barW - 2) * frac);
  if (fillW > 0) barSpr.fillRect(1, 1, fillW, BAR_H - 2, TFT_WHITE);

  // Push sprite (center row)
  barSpr.pushSprite(barX, rowY);
}

void redrawOverlay() {
  drawTextOverlayLine();
  drawProgressRow();
}

// ---------- Packet handlers ----------
bool handleIMG0() {
  ImgHeader hdr;
  memcpy(hdr.magic, "IMG0", 4);
  if (!readExact(reinterpret_cast<uint8_t*>(&hdr.width), sizeof(hdr) - 4)) return false;

  if (hdr.width == 0 || hdr.height == 0 || hdr.width > 480 || hdr.height > 480 || hdr.length == 0) {
    return false;
  }

  uint8_t* buf = (uint8_t*)heap_caps_malloc(hdr.length, MALLOC_CAP_8BIT);
  if (!buf) {
    M5.Display.clear(BLACK);
    M5.Display.drawString("Alloc failed", M5.Display.width()/2, M5.Display.height()/2);
    while (Serial.available()) Serial.read();
    delay(500);
    return false;
  }
  if (!readExact(buf, hdr.length)) {
    free(buf);
    return false;
  }

  // ----- Cover area (square) -----
  int sw = M5.Display.width();
  int sh = M5.Display.height();

  // Square viewport height = screen minus overlay, minus padding
  int coverSide = min(sw, sh - OVERLAY_H) - PAD*2;
  if (coverSide < 40) coverSide = 40; // safety

  int coverX = (sw - coverSide) / 2;
  int coverY = PAD;

  // Clear only the cover area
  M5.Display.fillRect(0, 0, sw, sh - OVERLAY_H, BLACK);

  // Clip to the square viewport so nothing bleeds
  M5.Display.setClipRect(coverX, coverY, coverSide, coverSide);

  // Center incoming image inside the square viewport (no scaling here;
  // if sender provides larger image, it will be cropped by the clip rect)
  int drawX = coverX + (coverSide - (int)hdr.width)  / 2;
  int drawY = coverY + (coverSide - (int)hdr.height) / 2;

  if (hdr.fmt == 1) {
    M5.Display.drawJpg(buf, hdr.length, drawX, drawY);
  } else if (hdr.fmt == 2) {
    M5.Display.pushImage(drawX, drawY, hdr.width, hdr.height, (const uint16_t*)buf);
  }

  // Remove clip
  M5.Display.clearClipRect();

  free(buf);

  // Redraw overlay on top
  redrawOverlay();
  return true;
}


bool handleMETA_full() {
  MetaFullHeader mh;
  memcpy(mh.magic, "META", 4);
  if (!readExact(reinterpret_cast<uint8_t*>(&mh.type), sizeof(mh) - 4)) return false;
  if (mh.type != META_FULL) return false;

  if (mh.title_len > 1024 || mh.artist_len > 1024) return false;

  std::unique_ptr<uint8_t[]> tbuf(new uint8_t[mh.title_len]);
  std::unique_ptr<uint8_t[]> abuf(new uint8_t[mh.artist_len]);
  if (!readExact(tbuf.get(), mh.title_len)) return false;
  if (!readExact(abuf.get(), mh.artist_len)) return false;

  g_title = String((const char*)tbuf.get(), mh.title_len);
  g_artist = String((const char*)abuf.get(), mh.artist_len);
  g_duration = mh.duration;

  // Reset position on new meta unless you want to keep previous
  if (g_position > g_duration) g_position = 0;

  redrawOverlay();
  return true;
}

bool handleMETA_pos() {
  MetaPosHeader ph;
  memcpy(ph.magic, "META", 4);
  if (!readExact(reinterpret_cast<uint8_t*>(&ph.type), sizeof(ph) - 4)) return false;
  if (ph.type != META_POS) return false;

  g_position = ph.position;
  if (g_position > g_duration && g_duration > 0) g_position = g_duration;

  // Fast path: only update bar/times sprite area to avoid flicker
  drawProgressRow();
  return true;
}

// ---------- Setup / Loop ----------
void setup() {
  auto cfg = M5.config();
  M5.begin(cfg);
  M5.Display.setBrightness(200);
  M5.Display.clear(BLACK);
  M5.Display.setTextDatum(middle_center);
  M5.Display.setFont(&fonts::Font2);
  M5.Display.setTextColor(0xC618);
  M5.Display.drawString("Waiting for image over Serial...", M5.Display.width()/2, M5.Display.height()/2);

  Serial.begin(921600);
}

void loop() {
  if (Serial.available() < 4) { delay(2); return; }

  // Peek at magic
  uint8_t magic[4];
  if (!readExact(magic, 4)) return;

  if (memcmp(magic, "IMG0", 4) == 0) {
    // IMG0: process remaining header/payload
    handleIMG0();
  } else if (memcmp(magic, "META", 4) == 0) {
    // Peek next byte (type)
    uint8_t type;
    if (!readExact(&type, 1)) return;

    if (type == META_FULL) {
      // We already consumed "META" + type, read the rest of MetaFullHeader then payloads
      // Reconstruct by reading remaining fields of the header:
      // We'll push back the 'type' into handler by setting stream position logically.
      // Simpler: handler will assume "META" already read; here we pass through by manually reading rest:
      // We need to read the rest of the MetaFullHeader and payloads inside handler, so we put the 'type' back?
      // Since Serial has no un-read, we implement handler to expect that we've already read 'type'.
      // But current handler expects to read from 'type' onwards; we already read type, so we must emulate:
      // Easiest: call a small inline that continues reading from 'title_len' onwards.

      // Continue as in handler:
      uint16_t title_len, artist_len; uint32_t duration;
      if (!readExact(reinterpret_cast<uint8_t*>(&title_len), 2)) return;
      if (!readExact(reinterpret_cast<uint8_t*>(&artist_len), 2)) return;
      if (!readExact(reinterpret_cast<uint8_t*>(&duration), 4)) return;

      if (title_len > 1024 || artist_len > 1024) { return; }

      std::unique_ptr<uint8_t[]> tbuf(new uint8_t[title_len]);
      std::unique_ptr<uint8_t[]> abuf(new uint8_t[artist_len]);
      if (!readExact(tbuf.get(), title_len)) return;
      if (!readExact(abuf.get(), artist_len)) return;

      g_title = String((const char*)tbuf.get(), title_len);
      g_artist = String((const char*)abuf.get(), artist_len);
      g_duration = duration;
      if (g_position > g_duration) g_position = 0;

      redrawOverlay();

    } else if (type == META_POS) {
      // Read remaining 4 bytes position
      uint32_t pos;
      if (!readExact(reinterpret_cast<uint8_t*>(&pos), 4)) return;
      g_position = pos;
      if (g_duration && g_position > g_duration) g_position = g_duration;
      drawProgressRow();
    } else {
      // Unknown meta type -> resync (drop stream until next recognizable magic)
      // Do nothing; next loop will try to read next magic
    }
  } else {
    // Bad sync: drop one byte and try again
    dropOne();
  }
}
