# Remote Mic Control

During the COVID-19 pandemic, I've found myself on many social calls that last a long while.
I often find myself using a Bluetooth headset and doing things around the house while listneing in.
Occasionally, I'll want to unmute myself and jump in.

I put together some tooling that makes remote mic control easier.

There is a Flask service which displays four buttons, letting you (1) display current status,
(2) mute all mics, (3) enable just the BT mic or (4) enable just the USB mic. The service
makes use of Pulse Audio controls and has my sound device info embedded.

I also got myself a M5Stack StickC. This small embedded Arduino system has three buttons on it.
I wrote a small system that allows me to turn it on, connect to the WiFi, send a "toggle"
HTTP request to the Flask service and go back to sleep.
