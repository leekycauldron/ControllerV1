#include <M5Unified.h>
#include <memory>

// ===================== Cover + Volume layout (struct FIRST) =====================
struct CoverLayout {
  int coverSide;
  int coverX;
  int coverY;
  int volX;      // left x of the volume column
  int volTop;    // top y of the bar box
  int volBarH;   // drawable bar height (without number)
  int overlayY0; // top of overlay
};

// ===================== Layout constants =====================
static const int OVERLAY_H = 60;  // a bit taller to fit two rows cleanly
static const int PAD = 6;
static const int BAR_H = 12;
static const int GAP = 4;         // small vertical gap between rows

// Volume column geometry (to the right of the cover)
static const int VOL_W   = 28;   // width of the volume column (bar area)
static const int VOL_PAD = 4;    // inner padding inside the volume column
static const int VOL_NUM_H = 14; // reserved height for the numeric label under the bar

// ===================== Protocol structs =====================
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
  META_POS  = 2,  // position only
  META_VOL  = 3   // volume percent (0..100)
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

// Optional tiny header for volume (we parse inline, but kept for reference)
struct __attribute__((packed)) MetaVolHeader {
  char     magic[4];   // "META"
  uint8_t  type;       // 3
  uint8_t  volume;     // 0..100
};

// ===================== State =====================
static String g_title = "";
static String g_artist = "";
static uint32_t g_duration = 0;  // sec
static uint32_t g_position = 0;  // sec
static uint8_t  g_volume  = 0;   // 0..100

// Progress bar and volume sprites to prevent flicker
M5Canvas barSpr(&M5.Display);
M5Canvas volSpr(&M5.Display);

// ===================== IO helpers =====================
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

// ===================== Text helpers =====================
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

// ===================== Cover + Volume layout (functions) =====================
static CoverLayout computeLayout() {
  CoverLayout L{};
  int sw = M5.Display.width();
  int sh = M5.Display.height();
  L.overlayY0 = sh - OVERLAY_H;

  // Cover side is max square that fits vertically above overlay
  L.coverSide = min(sw, L.overlayY0 - PAD*2);
  if (L.coverSide < 40) L.coverSide = 40;

  // Center the cover horizontally
  L.coverX = (sw - L.coverSide) / 2;
  L.coverY = PAD;

  // Volume column pinned to the right edge
  L.volX = sw - VOL_W - PAD;
  L.volTop = PAD;

  // Bar height fits above overlay
  L.volBarH = L.overlayY0 - PAD - VOL_NUM_H - GAP - L.volTop;
  if (L.volBarH < 20) L.volBarH = 20;

  return L;
}


void initVolSpriteIfNeeded(const CoverLayout& L) {
  if (volSpr.width() == VOL_W && volSpr.height() == L.volBarH) return;
  volSpr.setColorDepth(16);
  if (volSpr.width() || volSpr.height()) volSpr.deleteSprite();
  volSpr.createSprite(VOL_W, L.volBarH);
}

void drawVolumeColumn() {
  CoverLayout L = computeLayout();
  initVolSpriteIfNeeded(L);

  // Clear the whole volume column area (bar + number) to avoid ghosting
  M5.Display.fillRect(L.volX, PAD, VOL_W, L.overlayY0 - PAD - PAD, TFT_BLACK);

  // Draw the bar in a sprite
  volSpr.fillRect(0, 0, VOL_W, L.volBarH, TFT_DARKGREY);
  volSpr.drawRect(0, 0, VOL_W, L.volBarH, TFT_WHITE);

  int innerW = VOL_W - VOL_PAD*2;
  int innerH = L.volBarH - VOL_PAD*2;
  if (innerW < 4) innerW = 4;
  if (innerH < 4) innerH = 4;

  // Volume fill from bottom up
  float frac = max(0.0f, min(1.0f, g_volume / 100.0f));
  int fillH = (int)(innerH * frac);
  int fillY = VOL_PAD + (innerH - fillH);

  if (fillH > 0) {
    volSpr.fillRect(VOL_PAD, fillY, innerW, fillH, TFT_WHITE);
  }

  // Push sprite
  volSpr.pushSprite(L.volX, L.volTop);

  // Draw the numeric label centered under the bar, above overlay
  String num = String((int)g_volume); // no '%' per request
  const lgfx::IFont* metaFont = &fonts::Font2;
  M5.Display.setFont(metaFont);
  M5.Display.setTextColor(TFT_WHITE, TFT_BLACK);
  M5.Display.setTextDatum(textdatum_t::top_left);

  int numY = L.overlayY0 - VOL_NUM_H; // reserved strip for number
  int numW = M5.Display.textWidth(num);
  int numX = L.volX + (VOL_W - numW) / 2;
  if (numX < L.volX) numX = L.volX;

  M5.Display.drawString(num, numX, numY);
}

// ===================== Overlay (title + progress) =====================
void drawTextOverlayLine() {
  int sw = M5.Display.width();
  int sh = M5.Display.height();
  int y0 = sh - OVERLAY_H;

  // Background strip
  M5.Display.fillRect(0, y0, sw, OVERLAY_H, TFT_BLACK);

  // Compose "Title · Artist"
  const lgfx::IFont* titleFont = &fonts::Font4;
  const lgfx::IFont* metaFont  = &fonts::Font2;
  (void)metaFont; // reserved for future adjustments

  String title  = g_title.length()  ? g_title  : String("(No Title)");
  String artist = g_artist.length() ? g_artist : String("(Unknown Artist)");
  String line   = title + " \xC2\xB7 " + artist; // " · " bullet

  // Ellipsize to fit width minus side padding
  int usable = sw - PAD*2;
  line = ellipsizeToWidth(line, usable, titleFont);

  // Draw the line top-left in overlay (upper row)
  M5.Display.setTextDatum(textdatum_t::top_left);
  M5.Display.setTextColor(TFT_WHITE, TFT_BLACK);
  M5.Display.setFont(titleFont);
  int y0_text = y0 + PAD;
  M5.Display.drawString(line, PAD, y0_text);
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
  // Keep volume visible on overlay refreshes
  drawVolumeColumn();
}

// ===================== Packet handlers =====================
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

  // ----- Cover + Volume layout -----
  CoverLayout L = computeLayout();

  // Clear everything above overlay (cover + volume column region)
  M5.Display.fillRect(0, 0, M5.Display.width(), L.overlayY0, BLACK);

  // Clip strictly to the cover square so nothing bleeds into volume column
  M5.Display.setClipRect(L.coverX, L.coverY, L.coverSide, L.coverSide);

  int drawX = L.coverX + (L.coverSide - (int)hdr.width)  / 2;
  int drawY = L.coverY + (L.coverSide - (int)hdr.height) / 2;

  if (hdr.fmt == 1) {
    M5.Display.drawJpg(buf, hdr.length, drawX, drawY);
  } else if (hdr.fmt == 2) {
    M5.Display.pushImage(drawX, drawY, hdr.width, hdr.height, (const uint16_t*)buf);
  }

  // Remove clip
  M5.Display.clearClipRect();

  free(buf);

  // Draw volume column and overlay
  drawVolumeColumn();
  redrawOverlay();
  return true;
}

bool handleMETA_full_streamFastPath(uint8_t already_type) {
  (void)already_type; // we know it's META_FULL
  uint16_t title_len, artist_len; uint32_t duration;
  if (!readExact(reinterpret_cast<uint8_t*>(&title_len), 2)) return false;
  if (!readExact(reinterpret_cast<uint8_t*>(&artist_len), 2)) return false;
  if (!readExact(reinterpret_cast<uint8_t*>(&duration), 4)) return false;

  if (title_len > 1024 || artist_len > 1024) return false;

  std::unique_ptr<uint8_t[]> tbuf(new uint8_t[title_len]);
  std::unique_ptr<uint8_t[]> abuf(new uint8_t[artist_len]);
  if (!readExact(tbuf.get(), title_len)) return false;
  if (!readExact(abuf.get(), artist_len)) return false;

  g_title = String((const char*)tbuf.get(), title_len);
  g_artist = String((const char*)abuf.get(), artist_len);
  g_duration = duration;
  if (g_position > g_duration) g_position = 0;

  redrawOverlay();
  return true;
}

// Legacy/alternate handler not used by loop anymore, kept for reference
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

  if (g_position > g_duration) g_position = 0;

  redrawOverlay();
  return true;
}

bool handleMETA_pos_streamFastPath(uint8_t already_type) {
  (void)already_type; // META_POS
  uint32_t pos;
  if (!readExact(reinterpret_cast<uint8_t*>(&pos), 4)) return false;
  g_position = pos;
  if (g_duration && g_position > g_duration) g_position = g_duration;
  // Fast path UI update
  drawProgressRow();
  return true;
}

bool handleMETA_vol_streamFastPath(uint8_t already_type) {
  (void)already_type; // META_VOL
  uint8_t vol;
  if (!readExact(reinterpret_cast<uint8_t*>(&vol), 1)) return false;
  if (vol > 100) vol = 100;
  g_volume = vol;
  // Fast path UI update
  drawVolumeColumn();
  return true;
}

// ===================== Setup / Loop =====================
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

  // Optional: draw initial volume column (empty) so region is clean
  drawVolumeColumn();
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
      // Continue reading rest of MetaFull header + payloads
      if (!handleMETA_full_streamFastPath(type)) return;

    } else if (type == META_POS) {
      // Read remaining 4 bytes position
      if (!handleMETA_pos_streamFastPath(type)) return;

    } else if (type == META_VOL) {
      // Read remaining 1 byte volume
      if (!handleMETA_vol_streamFastPath(type)) return;

    } else {
      // Unknown meta type -> resync (drop stream until next recognizable magic)
      // Do nothing; next loop will try to read next magic
    }

  } else {
    // Bad sync: drop one byte and try again
    dropOne();
  }
}
