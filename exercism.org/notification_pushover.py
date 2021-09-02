#!/usr/bin/python3

import os
import pathlib

import exercism
import requests


class Notifier:

    def __init__(self):
        self.pipe = pathlib.Path(os.getenv("XDG_RUNTIME_DIR")) / "ii" / "localhost" / "#notifications" / "in"
        self.pushover = pathlib.Path(os.getenv("XDG_CONFIG_HOME")) / "pushover" / "user.json"

    def notify(self, notification):
        msg = result["text"]
        # Write to ii pipe.
        self.pipe.write_text(msg)
        # Write to pushover.
        data = self.pushover.copy()
        data["message"] = msg
        url = 'https://api.pushover.net/1/messages.json'
        requests.post(url, data=data, json=False)


if __name__ == "__main__":
    exercism.Exercism().notification_pusher(Notifier().notify)
