#include <SPI.h>
#include <MFRC522.h>

#define SS_PIN 4
#define RST_PIN 5

MFRC522 rfid(SS_PIN, RST_PIN);
MFRC522::MIFARE_Key key;

char receivedData[17]; // 16 target characters + null string terminator
bool dataReady = false;

void setup() {
  Serial.begin(115200);
  SPI.begin();
  rfid.PCD_Init();

  Serial.println("=========================================");
  Serial.println("RFID Writer Initialized.");
  Serial.println("Waiting for encrypted 16-char block...");
  Serial.println("=========================================");

  // Initialize the Auth keys
  for (byte i = 0; i < 6; i++) {
    key.keyByte[i] = 0xFF;
  }
}

void loop() {
  
  // 1. Wait for Serial Data from MedTrace (The Python Flask Backend payload)
  if (Serial.available() > 0) {
    String incoming = Serial.readStringUntil('\n');
    incoming.trim();
    
    // Safety check strictly allowing 16 characters only.
    if (incoming.length() == 16) {
      incoming.toCharArray(receivedData, 17);
      dataReady = true;
      Serial.println("\n[+] SUCCESS: Data block received from Flask API!");
      Serial.print("Block ID Staged: ");
      Serial.println(receivedData);
      Serial.println("\n--> PLEASE PLACE RFID CARD TO WRITE <--");
    } else {
      Serial.print("[-] IGNORED INCORRECT DATA LENGTH: ");
      Serial.println(incoming);
    }
  }

  // 2. If data is staged and securely queued, wait for the physical RFID Tag
  if (dataReady) {
    
    if (!rfid.PICC_IsNewCardPresent()) return;
    if (!rfid.PICC_ReadCardSerial()) return;

    Serial.println(">>> RFID Card Detected. Linking Block...");

    byte block = 4;
    byte dataBlock[16];
    
    // Map dynamically received string array to byte array
    for (int i = 0; i < 16; i++) {
      dataBlock[i] = (byte)receivedData[i];
    }

    MFRC522::StatusCode status;

    // Secure auth access protocol execution
    status = rfid.PCD_Authenticate(
              MFRC522::PICC_CMD_MF_AUTH_KEY_A,
              block, &key, &(rfid.uid));

    if (status != MFRC522::STATUS_OK) {
      Serial.print("Auth failed: ");
      Serial.println(rfid.GetStatusCodeName(status));
      // Release RFID logic slightly so it's not permanently gridlocked
      delay(1000);
      return; 
    }

    // Push the 16 byte block
    status = rfid.MIFARE_Write(block, dataBlock, 16);

    if (status != MFRC522::STATUS_OK) {
      Serial.print("Write failed: ");
      Serial.println(rfid.GetStatusCodeName(status));
    } else {
      Serial.println("=========================================");
      Serial.println("✅ WRITE SUCCESSFUL! 16-Char Block stored.");
      Serial.println("=========================================");
      
      // Stop continuous loop executing by clearing the ready flag!
      // This forces the Arduino to eagerly await the next serial block from Python
      dataReady = false; 
    }

    rfid.PICC_HaltA();
    rfid.PCD_StopCrypto1();

    delay(2000); 
  }
}
