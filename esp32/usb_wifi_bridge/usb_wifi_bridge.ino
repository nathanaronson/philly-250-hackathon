#include <WiFi.h>
#include <HTTPClient.h>

// -----------------------------
// User configuration
// -----------------------------
static const char* WIFI_SSID = "Max’s iPhone";
static const char* WIFI_PASS = "maxhotspot";

// Example: "http://192.168.1.50:5000/ingest"
static const char* SERVER_URL = "http://192.168.1.100:5000/ingest";
static const char* DEVICE_ID = "esp32s3-feather";

// Tune these if needed.
static const uint32_t WIFI_RETRY_MS = 5000;
static const size_t LINE_BUFFER_MAX = 512;
static const uint32_t HTTP_TIMEOUT_MS = 4000;

// -----------------------------
// Internal state
// -----------------------------
String lineBuffer;
uint32_t lastWifiAttemptMs = 0;

void ensureWiFiConnected() {
  if (WiFi.status() == WL_CONNECTED) {
    return;
  }

  uint32_t now = millis();
  if (now - lastWifiAttemptMs < WIFI_RETRY_MS) {
    return;
  }

  lastWifiAttemptMs = now;
  Serial.println("[WIFI] Connecting...");

  WiFi.disconnect(true);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
}

String jsonEscape(const String& input) {
  String out;
  out.reserve(input.length() + 8);

  for (size_t i = 0; i < input.length(); ++i) {
    char c = input[i];

    if (c == '\\' || c == '"') {
      out += '\\';
      out += c;
    } else if (c == '\n') {
      out += "\\n";
    } else if (c == '\r') {
      out += "\\r";
    } else if (static_cast<uint8_t>(c) < 0x20) {
      out += ' ';
    } else {
      out += c;
    }
  }

  return out;
}

void sendAckToUsb(bool ok, int httpCode) {
  Serial.printf("ACK|%d|%d\n", ok ? 1 : 0, httpCode);
}

void forwardLineToServer(const String& rawLine) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[HTTP] WiFi not connected, dropping line.");
    sendAckToUsb(false, -2);
    return;
  }

  String line = jsonEscape(rawLine);
  String payload;
  payload.reserve(line.length() + 96);
  payload = "{\"device\":\"";
  payload += DEVICE_ID;
  payload += "\",\"source\":\"usb\",\"millis\":";
  payload += String(millis());
  payload += ",\"line\":\"";
  payload += line;
  payload += "\"}";

  HTTPClient http;
  http.setTimeout(HTTP_TIMEOUT_MS);
  http.begin(SERVER_URL);
  http.addHeader("Content-Type", "application/json");

  int code = http.POST(payload);
  if (code > 0) {
    Serial.printf("[HTTP] POST %d\n", code);
    sendAckToUsb(code >= 200 && code < 300, code);
  } else {
    Serial.printf("[HTTP] POST failed: %s\n", http.errorToString(code).c_str());
    sendAckToUsb(false, code);
  }

  http.end();
}

void setup() {
  // USB CDC serial on ESP32-S3 Feather.
  Serial.begin(115200);

  // Allow time for host serial monitor to attach after reset.
  delay(1200);

  Serial.println();
  Serial.println("USB -> WiFi (HTTP) bridge starting");

  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);

  lineBuffer.reserve(LINE_BUFFER_MAX);
}

void loop() {
  ensureWiFiConnected();

  // Read USB serial bytes and frame on newline.
  while (Serial.available() > 0) {
    char c = static_cast<char>(Serial.read());

    if (c == '\r') {
      continue;
    }

    if (c == '\n') {
      if (lineBuffer.length() > 0) {
        forwardLineToServer(lineBuffer);
        Serial.printf("[USB] %s\n", lineBuffer.c_str());
        lineBuffer = "";
      }
      continue;
    }

    // Drop overly long lines to avoid unbounded memory growth.
    if (lineBuffer.length() >= LINE_BUFFER_MAX) {
      Serial.println("[WARN] Input line too long, clearing buffer.");
      lineBuffer = "";
      continue;
    }

    lineBuffer += c;
  }

  delay(2);
}
