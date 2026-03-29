// L298N Motor Control with ESP32-S3 Feather
// Motor A wiring:
//   IN1 -> GPIO 6  / D6 (direction)
//   IN2 -> GPIO 9  / D9 (direction)
//   ENA -> leave jumper ON (always full speed)

#define IN1 6
#define IN2 9

void setup() {
  Serial.begin(115200);

  pinMode(IN1, OUTPUT);
  pinMode(IN2, OUTPUT);

  stopMotor();
  Serial.println("Motor control ready.");
  Serial.println("Commands: f (forward), b (backward), s (stop)");
}

void loop() {
  if (Serial.available()) {
    char cmd = Serial.read();

    switch (cmd) {
      case 'f':
        forward();
        Serial.println("Forward");
        break;
      case 'b':
        backward();
        Serial.println("Backward");
        break;
      case 's':
        stopMotor();
        Serial.println("Stopped");
        break;
    }
  }
}

void forward() {
  digitalWrite(IN1, HIGH);
  digitalWrite(IN2, LOW);
}

void backward() {
  digitalWrite(IN1, LOW);
  digitalWrite(IN2, HIGH);
}

void stopMotor() {
  digitalWrite(IN1, LOW);
  digitalWrite(IN2, LOW);
}
