#!/usr/bin/python3

# Standard lib
import json
import os
import pathlib
import time
from typing import Any, Callable

# External libs
import requests


Notifications = dict[str, Any]


class Exercism:
    """Exercism API wrapper."""

    # exercism.org API endpoint.
    API = "https://exercism.org/api/v2"
    # Sleep 15 minutes between watch polling.
    WATCHER_SLEEP_SEC = 15 * 60

    def __init__(self):
        """Iniitialize the wrapper."""
        # Get the user token from the exercism cli config file.
        config = pathlib.Path(os.getenv("XDG_CONFIG_HOME")) / "exercism" / "user.json"
        token = json.loads(config.read_text())["token"]
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {token}"})

    def notifications(self) -> Notifications:
        """Return notifications."""
        return self.session.get(f"{self.API}/notifications").json()

    def print_unread_notifications(self):
        """Pretty print unread notifications."""
        notifications = self.notifications()
        print(f"Unread count: {notifications['meta']['unread_count']}")
        for result in notifications["results"]:
            if result["is_read"]:
                continue
            print(f"{result['url']} {result['text']}")

    def notification_pusher(self, callback: Callable[[dict[str, str]], None]) -> None:
        """Watch for new notifications and call `callback` with them."""
        # Ignore existing notifications.
        seen_notifications = set(r["uuid"] for r in self.notifications()["results"])
        while True:
            time.sleep(self.WATCHER_SLEEP_SEC)
            unread = [r for r in self.notifications()["results"] if not r["is_read"]]
            unseen = [r for r in unread if r["uuid"] not in seen_notifications]
            for result in unseen:
                callback(result)
            seen_notifications.update(r["uuid"] for r in unseen)


if __name__ == "__main__":
    Exercism().print_unread_notifications()
