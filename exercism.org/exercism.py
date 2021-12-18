#!/usr/bin/python3

# Standard lib
import collections
import datetime
import json
import os
import pathlib
import tenacity
import time
from typing import Any, Callable, Iterable

# External libs
import dateparser
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
    def get_json_with_retries(self, *args, sleep=0.2, **kwargs) -> object:
        resp = self.session.get(*args, **kwargs)
        resp.raise_for_status()
        time.sleep(sleep)
        return resp.json()

    def post(self, *args, sleep=0.5, **kwargs) -> object:
        resp = self.session.post(*args, **kwargs)
        resp.raise_for_status()
        time.sleep(sleep)
        return resp

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
        """Return all mentoring requests for one track."""
        params = {"track_slug": track.lower()}
        all_requests = collections.defaultdict(list)
        page_count = self.get_json_with_retries(f"{self.API}/mentoring/requests", params=params)["meta"]["total_pages"]
        for page in range(1, page_count + 1):
            params["page"] = str(page)
            for result in self.get_json_with_retries(f"{self.API}/mentoring/requests", params=params)["results"]:
                all_requests[result["exercise_title"]].append(result)
        return all_requests

    def mentor_discussion_posts(self, uuid: str):
        """Return mentor discussion posts for one discussion."""
        return self.get_json_with_retries(f"{self.API}/mentoring/discussions/{uuid}/posts")["items"]

    def old_mentor_discussions(self, status: str, order: str = "oldest", age: int):
        """Get mentor discussions more than a certain age (days)."""
        assert order in ("oldest", "recent", "exercise", "student")
        assert status in ("awaiting_mentor", "awaiting_student", "finished")

        params = {"status": status, "order": order}
        resp = self.get_json_with_retries(f"{self.API}/mentoring/discussions", params=params)
        page_count = resp["meta"]["total_pages"]

        delta = datetime.timedelta(days=age)
        cutoff = datetime.datetime.now(tz=datetime.timezone.utc) - delta
        uuids = []
        for page in range(1, page_count + 1):
            params["page"] = page
            resp = self.get_json_with_retries(f"{self.API}/mentoring/discussions", params=params)
            for discussion in resp["results"]:
                updated = dateparser.parse(discussion["updated_at"])
                if updated > cutoff:
                    continue

                uuid = discussion["uuid"]
                posts = self.get_json_with_retries(f"{self.API}/mentoring/discussions/{uuid}/posts")["items"]
                post_dates = [dateparser.parse(c['updated_at']) for c in posts]
                most_recent_post = max(post_dates)
                if most_recent_post > cutoff:
                    continue

                uuids.append(uuid)
        return uuids

    def nudge(self, uuids: Iterable[str], msg: str = ""):
        """Nudge student discussions."""
        if not msg:
            msg = (
                "It's been a while! "
                "How is this exercise going? Are you planning on making more changes? "
                "If you are ready to move on, you can free up the mentoring slot by clicking "
                '"End discussion". '
                "If you are still working on this, that is great, too! "
                "If you have any questions or what any help or tips, just let me know!"
            )
        for uuid in uuids:
            self.post(f"{self.API}/mentoring/discussions/{uuid}/posts", data={"content": msg})


if __name__ == "__main__":
    Exercism().print_unread_notifications()
