#!/usr/bin/python3

import json
import os
import pathlib

import exercism
import requests


class Notifier:

    def __init__(self):
        self.pipe = pathlib.Path(os.getenv("XDG_RUNTIME_DIR")) / "ii" / "localhost" / "#notifications" / "in"
        config = pathlib.Path(os.getenv("XDG_CONFIG_HOME")) / "pushover" / "user.json"
        self.pushover = json.loads(config.read_text())

    def notify(self, notification):
        msg = notification["text"]
        # Write to ii pipe.
        self.pipe.write_text(msg + "\n")
        # Write to pushover.
        data = self.pushover.copy()
        data["message"] = msg
        url = "https://api.pushover.net/1/messages.json"
        requests.post(url, data=data, json=False)


if __name__ == "__main__":
    e = exercism.Exercism()
    e.WATCHER_SLEEP_SEC = 200
    e.notification_pusher(Notifier().notify)
