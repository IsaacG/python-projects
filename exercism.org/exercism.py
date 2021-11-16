#!/usr/bin/python3

# Standard lib
import collections
import json
import os
import pathlib
import tenacity
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

    @tenacity.retry(
        stop=tenacity.stop_after_attempt(3),
        wait=tenacity.wait_exponential(multiplier=2, min=15, max=60),
        retry=tenacity.retry_if_exception_type((requests.HTTPError, requests.exceptions.ConnectionError)),
    )
    def get_json_with_retries(self, *args, **kwargs) -> object:
        resp = self.session.get(*args, **kwargs)
        resp.raise_for_status()
        return resp.json()

    def notifications(self) -> Notifications:
        """Return notifications."""
        return self.get_json_with_retries(f"{self.API}/notifications")

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
            try:
                unread = [r for r in self.notifications()["results"] if not r["is_read"]]
            except requests.exceptions.HTTPError:
                continue
            unseen = [r for r in unread if r["uuid"] not in seen_notifications]
            for result in unseen:
                callback(result)
            seen_notifications.update(r["uuid"] for r in unseen)

    def mentor_requests(self, track: str):
        params = {"track_slug": track.lower()}
        all_requests = collections.defaultdict(list)
        page_count = self.get_json_with_retries(f"{self.API}/mentoring/requests", params=params)["meta"]["total_pages"]
        for page in range(1, page_count + 1):
            params["page"] = str(page)
            for result in self.get_json_with_retries(f"{self.API}/mentoring/requests", params=params)["results"]:
                all_requests[result["exercise_title"]].append(result)
        return all_requests


if __name__ == "__main__":
    Exercism().print_unread_notifications()
