/*
 * ESP32 Smoke Sensor -> Firebase Realtime Database
 *
 * Hardware: ESP32 + MQ-2/MQ-135 smoke/gas sensor
 * Sends smoke level to Firebase RTDB every 10 seconds.
 * Firebase URL: https://sivakasi-fire-default-rtdb.asia-southeast1.firebasedatabase.app
 */

#include <WiFi.h>
#include <HTTPClient.h>

const char* WIFI_SSID = "YourWiFiSSID";
const char* WIFI_PASS = "YourWiFiPassword";

const char* FIREBASE_URL =
  "https://sivakasi-fire-default-rtdb.asia-southeast1.firebasedatabase.app";

// Which factory this ESP32 reports for (1-8, matches FACTORY_DATA in config.py)
const int FACTORY_ID = 1;

// Smoke sensor analog pin
const int SMOKE_PIN = 34;

void setup() {
  Serial.begin(115200);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected");
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    delay(5000);
    return;
  }

  int raw = analogRead(SMOKE_PIN);
  // Convert 0-4095 ADC to 0-100% smoke level (calibrate for your sensor)
  float smokePercent = (raw / 4095.0) * 100.0;
  smokePercent = constrain(smokePercent, 0, 100);

  Serial.printf("Factory %d - Smoke: %.1f%%\n", FACTORY_ID, smokePercent);

  HTTPClient http;
  String url = String(FIREBASE_URL) + "/esp32/factory_" + FACTORY_ID + "/smoke_level.json";
  http.begin(url);
  http.addHeader("Content-Type", "application/json");

  String payload = String(smokePercent, 1);
  int httpCode = http.PUT(payload);

  if (httpCode > 0) {
    Serial.printf("Firebase response code: %d\n", httpCode);
  } else {
    Serial.printf("Firebase error: %s\n", http.errorToString(httpCode).c_str());
  }
  http.end();

  delay(10000); // Send every 10 seconds
}
