//Modbus ESP32 Code side 19

#include <ModbusMaster.h>
#define RXD2 36
#define TXD2 4

#define MAX485_DE 5
#define MAX485_RE_NEG 14

String password = "abs";
uint8_t i = 0;
unsigned long last_time = 0;

// instantiate ModbusMaster object
ModbusMaster node;

void preTransmission() {
  digitalWrite(MAX485_RE_NEG, 1);
  digitalWrite(MAX485_DE, 1);
}

void postTransmission() {
  digitalWrite(MAX485_RE_NEG, 0);
  digitalWrite(MAX485_DE, 0);
}

void setup() {
  pinMode(MAX485_RE_NEG, OUTPUT);
  pinMode(MAX485_DE, OUTPUT);

  // Init in receive mode
  digitalWrite(MAX485_RE_NEG, 0);
  digitalWrite(MAX485_DE, 0);

  // Modbus communication runs at 115200 baud
  Serial.begin(115200);
  Serial2.begin(9600, SERIAL_8N1, RXD2, TXD2);

  // Modbus slave ID 1
  node.begin(1, Serial2);
  // Callbacks allow us to configure the RS485 transceiver correctly
  node.preTransmission(preTransmission);
  node.postTransmission(postTransmission);
}



void loop() {
  /**
  Serial.println("Please enter your password: ");

  while (Serial.available() == 0) {
  }

  String input = Serial.readString();

  if (input == password) {
    Serial.println("Password correct");
  } else
    Serial.println("Password incorrect");

  */


  uint8_t result = 0 ; 
  uint8_t responses = 0 ; 
  uint16_t data[ 10 ]; 
 
  i++;
  delay(5000);
  if(i == 1) {
  
    //Skriver 0 til register "368" (367) i systemet for at slukke
    //Ændre 0 til 3 for at tænde automatisk
    result = node.writeSingleRegister(367, 0);  // Turn off the device
    
    //Kommer med feedback om den har kunne skrive eller ej
    if (result == node.ku8MBSuccess) {
        Serial.println("Successfully wrote 0 to register 367");
    } else {
        Serial.print("Modbus error: ");
        Serial.println(result);
    }
  }

  delay(2000);
}

bool getResultMsg(ModbusMaster *node, uint8_t result) {
  String tmpstr2 = "\r\n";
  switch (result) {
    case node->ku8MBSuccess:
      return true;
      break;
    case node->ku8MBIllegalFunction:
      tmpstr2 += "Illegal Function";
      break;
    case node->ku8MBIllegalDataAddress:
      tmpstr2 += "Illegal Data Address";
      break;
    case node->ku8MBIllegalDataValue:
      tmpstr2 += "Illegal Data Value";
      break;
    case node->ku8MBSlaveDeviceFailure:
      tmpstr2 += "Slave Device Failure";
      break;
    case node->ku8MBInvalidSlaveID:
      tmpstr2 += "Invalid Slave ID";
      break;
    case node->ku8MBInvalidFunction:
      tmpstr2 += "Invalid Function";
      break;
    case node->ku8MBResponseTimedOut:
      tmpstr2 += "Response Timed Out";
      break;
    case node->ku8MBInvalidCRC:
      tmpstr2 += "Invalid CRC";
      break;
    default:
      tmpstr2 += "Unknown error: " + String(result);
      break;
  }
  Serial.println(tmpstr2);
  return false;
}
