#include <SPI.h>
#include <MFRC522.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ESPmDNS.h>  // Added for mDNS

#define SS_PIN 21      // ESP32 pin connected to SDA
#define RST_PIN 22     // ESP32 pin connected to RST

const char* ssid = "iQOO_Z3_5G";
const char* password = "nethaksko";
String serverIP = "";  // Will be set dynamically via mDNS

MFRC522 mfrc522(SS_PIN, RST_PIN);  // Create MFRC522 instance

void setup() {
  Serial.begin(115200);
  SPI.begin();           // Initialize SPI bus
  mfrc522.PCD_Init();    // Initialize RFID module
  Serial.println("RFID reader initialized");

  // Connect to WiFi
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(1000);
    Serial.println("Connecting to WiFi...");
  }
  Serial.println("Connected to WiFi");

  // Initialize mDNS
  if (!MDNS.begin("esp32")) {
    Serial.println("Error starting mDNS");
    while (1) delay(1000);  // Halt if mDNS fails
  }
  Serial.println("mDNS responder started");
}

void loop() {
  // Discover the server if not already found
  if (serverIP == "") {
    int n = MDNS.queryService("http", "tcp");  // Query HTTP services
    if (n > 0) {
      for (int i = 0; i < n; ++i) {
        if (MDNS.hostname(i) == "HospitalServer") {
          serverIP = MDNS.address(i).toString();  // Corrected: Use address(i)
          Serial.println("Found server at: " + serverIP);
          break;
        }
      }
    } else {
      Serial.println("Server not found, retrying...");
      delay(5000);
      return;
    }
  }

  if (!mfrc522.PICC_IsNewCardPresent()) {
    return;
  }

  if (!mfrc522.PICC_ReadCardSerial()) {
    return;
  }

  // Print card UID in Hex
  Serial.print("Card UID (Hex): ");
  for (byte i = 0; i < mfrc522.uid.size; i++) {
    Serial.print(mfrc522.uid.uidByte[i] < 0x10 ? "0" : "");
    Serial.print(mfrc522.uid.uidByte[i], HEX);
    Serial.print(" ");
  }
  Serial.println();

  // Convert hex to decimal
  unsigned long decimalUID = 0;
  for (byte i = 0; i < mfrc522.uid.size; i++) {
    decimalUID = (decimalUID << 8) | mfrc522.uid.uidByte[i];
  }
  
  Serial.print("Card UID (Decimal): ");
  Serial.println(decimalUID);

  // Send the decimal UID to the server
  if (WiFi.status() == WL_CONNECTED && serverIP != "") {
    HTTPClient http;
    String serverPath = "http://" + serverIP + ":5000/rfid_scan";

    http.begin(serverPath);
    http.addHeader("Content-Type", "application/x-www-form-urlencoded");

    String postData = "rfid=" + String(decimalUID);
    
    Serial.println("Sending RFID to server: " + String(decimalUID));
    int httpCode = http.POST(postData);

    if (httpCode > 0) {
      String payload = http.getString();
      Serial.println("HTTP Response Code: " + String(httpCode));
      Serial.println("Response: " + payload);
      Serial.println("Data sent successfully.");
    } else {
      Serial.println("HTTP Error: " + String(httpCode));
      Serial.println(http.errorToString(httpCode));
      Serial.println("Failed to send data.");
    }
    http.end();
  } else {
    Serial.println("WiFi Disconnected or server IP not found");
  }

  mfrc522.PICC_HaltA();
  delay(1000); // Small delay to avoid spamming the server
}