byte ledPin = 13;   // the onboard LED
int N_ANALOG = 16;
boolean started = false;
float FIRMWARE_VERSION = 0.1;

//===============

/* HEMT-to-Analog Pin map
 * HEMT 1 : A13-A15
 * HEMT 2 : A10-A12
 * HEMT 3 : A7-A9
 * HEMT 4 : A4-A6
 * HEMT 5 : A1-A3 
 */

/* Pin-to-measurement
 * A1 = Vg, HEMT 5 
 * A2 = Id, HEMT 5
 * A3 = Vd, HEMT 5
 * A4 = Vg, HEMT 4 
 * A5 = Id, HEMT 4
 * A6 = Vd, HEMT 4
 * A7 = Vg, HEMT 3 
 * A8 = Id, HEMT 3
 * A9 = Vd, HEMT 3
 * A10 = Vg, HEMT 2 
 * A11 = Id, HEMT 2
 * A12 = Vd, HEMT 2
 * A13 = Vg, HEMT 1 
 * A14 = Id, HEMT 1
 * A15 = Vd, HEMT 1
 */

 //===================

void setup() {
  Serial.begin(115200);
  pinMode(ledPin, OUTPUT);
  digitalWrite(ledPin, HIGH);
  digitalWrite(ledPin, LOW);
  digitalWrite(ledPin, HIGH);
}

void loop() {
  char confirm;
  if (Serial.available()>0) {
    while (Serial.available()) {
      char x = Serial.read();
      confirm = x;
    }
    if (String(confirm)=="?") {
      for(int i=1; i<N_ANALOG; i++){
        Serial.print(" ");
        Serial.print(analogRead(i));
      }
    }
    else if (String(confirm)=="v") {
      Serial.print(" ");
      Serial.print(FIRMWARE_VERSION);
    }
    Serial.print(" ");
    Serial.print(confirm);
    Serial.println();
  }
}
