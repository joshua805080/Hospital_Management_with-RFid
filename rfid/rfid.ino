#include <SPI.h>
#include <MFRC522.h>
#include <WiFi.h>
#include <HTTPClient.h>

#define SS_PIN 21      // ESP32 pin connected to SDA
#define RST_PIN 22     // ESP32 pin connected to RST

const char* ssid = "CAMPUS-WiFi";
const char* password = "Admin1@knsit";
const char* serverIP = "http://192.168.101.5:5000/rfid_scan"; // Ensure this matches your server's IP

MFRC522 mfrc522(SS_PIN, RST_PIN);  // Create MFRC522 instance

void setup() {
  Serial.begin(115200);
  SPI.begin();           // Initialize SPI bus
  mfrc522.PCD_Init();    // Initialize RFID module
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(1000);
    Serial.println("Connecting to WiFi...");
  }
  Serial.println("Connected to WiFi");
}

void loop() {
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
    decimalUID = (decimalUID << 8) | mfrc522.uid.uidByte[i];  // Shift left by 8 bits then OR with current byte
  }
  
  Serial.print("Card UID (Decimal): ");
  Serial.println(decimalUID);

  // Send the decimal UID to the server
  if(WiFi.status() == WL_CONNECTED){
    HTTPClient http;
    String serverPath = String(serverIP);

    http.begin(serverPath);
    http.addHeader("Content-Type", "application/x-www-form-urlencoded");

    // Ensure we're sending the correct decimal number
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
      Serial.println(http.errorToString(httpCode).c_str());
      Serial.println("Failed to send data.");
    }
    http.end();
  } else {
    Serial.println("WiFi Disconnected");
  }

  mfrc522.PICC_HaltA();
  delay(1000); // Small delay to avoid spamming the server
}