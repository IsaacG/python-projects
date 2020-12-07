#include <WiFi.h>
#include <M5StickC.h>
#include "wifi.h"

// wifi.h sets:
// char ssid[] = "";
// char pass[] = "";
// IPAddress server(192, 168, 1, 2);

char request[] = "GET /toggle_bt HTTP/1.1";
int status = WL_IDLE_STATUS;
WiFiClient client;


void printWifiStatus() {
  // print the SSID of the network you're attached to:
  Serial.print("SSID: ");
  Serial.println(WiFi.SSID());

  // print your WiFi shield's IP address:
  IPAddress ip = WiFi.localIP();
  Serial.print("IP Address: ");
  Serial.println(ip);
}


void wifiConnect () {
    Serial.println("Connect to wifi");

    // Attempt to connect to Wifi network.
    while (status != WL_CONNECTED) {
        Serial.print("Attempting to connect to SSID: ");
        Serial.println(ssid);

        // Connect to WPA/WPA2 network.
        status = WiFi.begin(ssid, pass);

        // Poll for 10s for connection before retrying.
        for (int i = 0; i < 20 && WiFi.status() != WL_CONNECTED; i++) {
            delay(500);
        }
    }

    Serial.println("Connected to WiFi.");
    printWifiStatus();
}

void toggle () {
    char buff[250];
    uint8_t i = 0;
    bool body = 0;

    if (! client.connect(server, port)) {
        Serial.println("Failed to connect.");
        return;
    }
    Serial.println("Socket connected.");
    client.println(request);
    client.println("");

    // Wait for the response to be made available. 
    for (i = 0; i < 50 && ! client.available(); i++) {
        delay(10);
    }

    for (i = 0; i < 245 && client.available(); i++) {
        buff[i] = client.read();
        if (! body && i > 5) {
            if (buff[i-3] == '\r' && buff[i-2] == '\n' && buff[i-1] == '\r' && buff[i-0]) {
                i = -1;
                body = 1;
            }
        }
    }
    buff[i] = 0;
    client.stop();

    Serial.println("Done reading response: ");
    Serial.println(buff);

    M5.Lcd.fillScreen(BLACK);
    M5.Lcd.drawCentreString(buff, 80, 15, 1);
    M5.Lcd.drawCentreString("btnA: Toggle", 80, 30, 1);
    M5.Lcd.drawCentreString("btnB: Power", 80, 40, 1);
}

void setup() {
    M5.begin();
    Serial.println("Event: Setup");

    M5.Lcd.setRotation(1);
    M5.Lcd.setTextColor(WHITE, BLACK);

    M5.Lcd.fillScreen(BLACK);
    M5.Lcd.drawCentreString("Connecting to WiFi...", 80, 30, 1);
    wifiConnect();

    M5.Lcd.fillScreen(BLACK);
    M5.Lcd.drawCentreString("Connected!", 80, 15, 1);
    M5.Lcd.drawCentreString("btnA: Toggle", 80, 30, 1);
    M5.Lcd.drawCentreString("btnB: Power", 80, 40, 1);
}

void loop() {
    M5.update();

    if(M5.BtnA.wasPressed())
    {
        Serial.println("Event: BtnA");
        M5.Lcd.fillScreen(BLACK);
        M5.Lcd.drawCentreString("BtnA. Toggling.", 80, 25, 1);
        delay(10);
        toggle();
    }

    if(M5.BtnB.wasPressed())
    {
        Serial.println("Event: BtnB");
        delay(10);
        M5.Axp.PowerOff();
    }

    delay(20);
}

// vim:expandtab:ts=4:sw=4
