#!/usr/bin/python3

import json
import requests
import os
import pathlib


class Exercism:

    API = "https://exercism.org/api/v2"

    def __init__(self):
        config = pathlib.Path(os.getenv("XDG_CONFIG_HOME")) / "exercism" / "user.json"
        token = json.loads(config.read_text())["token"]
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {token}"})

    def notifications(self):
        return self.session.get(f"{self.API}/notifications").json()

    def print_unread_notifications(self):
        notifications = self.notifications()
        print(f"Unread count: {notifications['meta']['unread_count']}")
        for result in notifications["results"]:
            if result["is_read"]:
              continue
            print(f"{result['url']} {result['text']}")


if __name__ == "__main__":
    Exercism().print_unread_notifications()
