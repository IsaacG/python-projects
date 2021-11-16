#!/bin/python

"""Google Calendar Aggregator.

Manage a public Google Calendar which reflects events from a list of shared calendars.
This allows multiple people to organize and update events and have them all published
to a shared calendar with their account info not shared.

To add events to the shared calendar:
* Visit http://calendar.google.com/ on a computer.
* Hit the + next to "Other calendars" on the left bar > Create new calendar.
* Click "Create calendar" only once and wait a few seconds until it creates.
* On the left bar under Settings, click on that calendar name you just created.
* "Share with specific people" => the public account.
* Click "Get shareable link" and share that with the public account so it can add it.
"""


# TODO: Periodic full refresh and sync

import asyncio
import datetime
import json
import logging
import pathlib
import time
import uuid

from typing import Optional

import aiohttp
import click
import dateutil.parser
import dateutil.tz
import pytz
import tenacity

from google.auth.exceptions import RefreshError
from googleapiclient.discovery import build, Resource
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials


# API permissions.
SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar",
]


def tz_name(timeobj: datetime.datetime) -> str:
    """Map a datetime object to a common TZ name."""
    common = ["America/Los_Angeles", "America/New_York"] + pytz.common_timezones
    offset = timeobj.utcoffset()
    now = datetime.datetime.now()
    for timezone in common:
        if pytz.timezone(timezone).utcoffset(now) == offset:
            return timezone
    if timeobj.tzinfo == dateutil.tz.tzoffset(None, -28800):
        return "America/Los_Angeles"
    if timeobj.tzinfo == dateutil.tz.tzoffset(None, -25200):
        return "America/Los_Angeles"
    raise RuntimeError("TZ not found for", timeobj)


class Event(dict):
    """Google Calendar Event wrapper."""

    # Keys used to check for eqality and reposting.
    KEYS = ("summary", "description", "location", "start_dt", "end_dt", "kind", "recurrence")

    def __init__(self, data: dict, service, addition: Optional[str] = None) -> None:
        """Initialize."""
        super().__init__(data)
        self.service = service
        # Convert date strings to datetime objects for TZ-aware equality.
        for time_s in ("start", "end"):
            if self.get(time_s, {}).get("dateTime", None):
                self[f"{time_s}_dt"] = dateutil.parser.isoparse(self[time_s]["dateTime"])
        # Add calendar metadata.
        if addition:
            self.setdefault("description", "")
            self["description"] += "<hr /><span>" + addition + "</span>"

    def __eq__(self, other: object) -> bool:
        """Return if events are equal, considering only public information."""
        msg = f"Cannot compare types {type(self)} to type {type(other)}"
        assert isinstance(other, type(self)), msg
        diff_contains = [key for key in self.KEYS if (key in self) != (key in other)]
        if diff_contains:
            return False
        diff_vals = [key for key in self.KEYS if self.get(key, None) != other.get(key, None)]
        if diff_vals:
            return False
        return True

    def __hash__(self):
        return hash(((k, self[k]) for k in self.KEYS))

    @tenacity.retry(stop=tenacity.stop_after_attempt(3), wait=tenacity.wait_fixed(5))
    def delete(self) -> None:
        """Delete this event from Google Calendar."""
        calendar_id = self["organizer"]["email"]
        self.service().events().delete(calendarId=calendar_id, eventId=self["id"]).execute()

    def add(self, dest_cal: "Calendar") -> bool:
        """Add this event to a Google Calendar."""
        # Check for existance first to avoid creating duplicates.
        if self in dest_cal.future_events():
            print("Skipping add; event is already in the calendar.")
            return False
        now = datetime.datetime.now(datetime.timezone.utc)
        if "recurrence" not in self and "end_dt" in self and self["end_dt"] < now:
            print("Skipping add; event already ended.")
            return False
        body = {key: self[key] for key in self.KEYS if key in self}
        # Convert datetime back to a string.
        for time_s in ("start", "end"):
            if f"{time_s}_dt" in body:
                timeobj = body[f"{time_s}_dt"]
                body[time_s] = {
                    "dateTime": timeobj.isoformat(),
                    "timeZone": tz_name(timeobj)
                }
                del body[f"{time_s}_dt"]
            else:
                # All day events.
                body[time_s] = self[time_s]
        self.service().events().insert(calendarId=dest_cal.cid, body=body).execute()
        return True


class Calendar:
    """Calendar wrapper."""

    def __init__(self, calendar, service, config) -> None:
        self.calendar = calendar
        self.config = config
        self.service = service
        self.watch_token = None

    @property
    def destinations(self) -> list[str]:
        """"Return where events from this calendar should be published."""
        dest_names = self.config["sources"][self.cid]["destinations"]
        dest_ids = [k for k, v in self.config["destinations"].items() if v["name"] in dest_names]
        return dest_ids

    @property
    def name(self) -> str:
        """"Return the calendar name."""
        return self.calendar.get("summary", "")

    @property
    def cid(self) -> str:
        """Return the calendar ID."""
        return self.calendar["id"]

    @property
    def is_owner(self) -> bool:
        """Return if we are the calendar owner."""
        return self.calendar["accessRole"] == "owner"

    def __hash__(self) -> int:
        return hash(self.calendar["id"])

    def future_events(self) -> list[Event]:
        """Return future events for this calendar."""
        if self.is_owner:
            addition = ""
            max_results = 250
        else:
            source_tag = self.config["sources"][self.cid]["tag"]
            addition = f"Source: {source_tag}"
            max_results = self.config["max_results"]

        now = datetime.datetime.utcnow().isoformat() + "Z" # "Z" indicates UTC time
        end = (datetime.datetime.utcnow() + datetime.timedelta(days=60)).isoformat() + "Z"
        response = self.service().events().list(
            calendarId=self.cid,
            timeMin=now,
            timeMax=end,
            maxResults=max_results,
        ).execute()
        # Dedupe events if needed.
        return list({Event(event, self.service, addition) for event in response.get("items", [])})

    def watch(self) -> None:
        """Add a webhook callback to watch a calendar for changes."""
        body = {
            "type": "webhook",
            "address": self.config["watch_url"],
            "token": self.cid,
            "id": str(uuid.uuid4()),
        }
        self.watch_token = self.service().events().watch(calendarId=self.cid, body=body).execute()
        nick = self.config["sources"][self.cid]["name"]
        print(f"Requested watch for {nick} ({self.cid} {body['id']})")
        # print(f"{self.watch_token=}")

    def watch_stop(self) -> None:
        """Remove a calendar watch."""
        if self.watch_token is None:
            print("Not watching")
            return
        self.service().channels().stop(body=self.watch_token).execute()
        nick = self.config["sources"][self.cid]["name"]
        print(f"Requested stop for {nick} ({self.cid} {self.watch_token['id']})")
        self.watch_token = None


class GCalAggregator:
    """Google Calendar Aggregator."""

    def __init__(self, service, config) -> None:
        """Initialize an Aggregator."""
        self.delete_old = False
        self.service = service
        self.config = config
        self.validate_config()

        self.events: dict[Calendar, list[Event]] = {}
        self.dst_src: dict[Calendar, list[Calendar]] = {}
        self.src_cals: set[Calendar] = set()
        self.dst_cals: set[Calendar] = set()

        self.lock = asyncio.Lock()

    def validate_config(self) -> None:
        """Validate the calendar names in the config."""
        want_destinations: set[str] = set()
        for src in self.config["sources"].values():
            want_destinations.update(src["destinations"])
        have_destinations = set(dst["name"] for dst in self.config["destinations"].values())
        if missing_destinations := want_destinations - have_destinations:
            raise ValueError(f"validate_config: {missing_destinations=}")
        if unused_destinations := have_destinations - want_destinations:
            raise ValueError(f"validate_config: {unused_destinations=}")

    def load_calendars(self) -> None:
        """Load calendar lists and managed calendar events."""
        self.dst_src = self.get_cals()
        self.dst_cals = set(self.dst_src.keys())
        for cal in self.dst_cals:
            events = cal.future_events()
            if cal in self.events and sorted(events) != sorted(self.events[cal]):
                print("Found discrepancies in events for", cal)
            self.events[cal] = events
        src_cals = set()
        for srcs in self.dst_src.values():
            src_cals.update(srcs)
        self.src_cals = src_cals

        for cal in self.src_cals:
            self.events[cal] = cal.future_events()

    def get_cals(self) -> dict[Calendar, list[Calendar]]:
        """Return a mapping of destination calendar to all sources for it."""
        resp = self.service().calendarList().list(showHidden=True).execute()
        calendars = [Calendar(c, self.service, self.config) for c in resp["items"]]

        own_cals = [c for c in calendars if c.is_owner]
        dst_cals = [c for c in own_cals if c.cid in self.config["destinations"]]

        found_dsts = [c.cid for c in dst_cals]
        if (missing_dsts := [cid for cid in self.config["destinations"] if cid not in found_dsts]):
            print(f"get_cals: {missing_dsts=}")

        # other_cals = [c for c in calendars if not c.is_owner]
        src_cals = [c for c in calendars if c.cid in self.config["sources"]]

        found_srcs = [c.cid for c in src_cals]
        if (missing_srcs := [cid for cid in self.config["sources"] if cid not in found_srcs]):
            print(f"get_cals: {missing_srcs=}")

        # Map destination calendars to their source calendars.
        dst_src = {
            dst: [src for src in src_cals if dst.cid in src.destinations]
            for dst in dst_cals
        }

        return dst_src

    async def sync_calendar(self, cal: Calendar) -> None:
        """Sync one calendar, refreshing its event data."""
        self.events[cal] = cal.future_events()
        async with self.lock:
            self.sync_calendars()

    def sync_calendars(self) -> None:
        """Sync events to public calendars."""
        events = self.events

        now = datetime.datetime.now(datetime.timezone.utc)
        for dst in self.dst_src:
            for event in events[dst]:
                if "recurrence" not in event and event["end_dt"] < now:
                    print(f'Soft drop {event["summary"]} from {dst.name}')
                    self.events[dst].remove(event)

        for dst, srcs in self.dst_src.items():
            drop = [e for e in events[dst] if not any(e in events[src] for src in srcs)]
            add = [e for src in srcs for e in events[src] if e not in events[dst]]
            for event in drop:
                print("Drop:", event["summary"])
                self.events[dst].remove(event)
                event.delete()
            for event in add:
                print("Add:", event["summary"])
                if event.add(dst):
                    self.events[dst].append(event)


class AggApp:
    """Application to manage calendars with callbacks."""

    def __init__(self, config_file: str) -> None:
        """Initialize."""
        self.config = json.loads(pathlib.Path(config_file).read_text())

        self._credentials = None
        self._resource = None
        self.refresh_count = 0

        self.service()

    async def webhook(self, request: aiohttp.web.Request) -> aiohttp.web.Response:
        """Handle HTTP requests."""
        expected_headers = (
            "X-Goog-Channel-ID", "X-Goog-Resource-ID",
            "X-Goog-Resource-State", "X-Goog-Channel-Token",
        )
        has_headers = all(h in request.headers for h in expected_headers)
        msg = f"Income request: {request.scheme.upper()} {request.method} {request.host}. "
        msg += f"{has_headers=}"
        print(msg)
        if not has_headers:
            return aiohttp.web.Response(text="NACK")

        cid = request.headers["X-Goog-Channel-Token"]
        name = self.config["sources"][cid]["name"]
        gca = request.app["gca"]

        if request.headers["X-Goog-Resource-State"] == "sync":
            print(f"=> SYNC: watching events {name=}")
            c = [c for c in gca.src_cals if c.cid == cid][0]
            if c.watch_token['id'] != request.headers["X-Goog-Channel-ID"]:
                print("==> Uncontrolled watch channel! Unsubscribing.")
                body = {
                    "id": request.headers["X-Goog-Channel-ID"],
                    "resourceId": request.headers["X-Goog-Resource-ID"],
                }
                print(request.headers)
                print(body)
                self.service().channels().stop(body=body).execute()
        elif request.headers["X-Goog-Resource-State"] == "exists":
            cals = [c for c in gca.src_cals if c.cid == cid]
            if len(cals) != 1:
                print("No calendar with CID", cid)
                return aiohttp.web.Response(text="NACK")
            cal = cals[0]
            print(f"=> EXISTS: event updated {name=}; sync calendar.")
            await gca.sync_calendar(cal)
        return aiohttp.web.Response(text="ACK")

    async def watch_calendars(self, app: aiohttp.web.Application) -> None:
        """Watch calendars, renewing as needed."""
        gca = app["gca"]
        for cal in gca.src_cals:
            cal.watch()
        while True:
            next_expire = min(int(cal.watch_token["expiration"]) for cal in gca.src_cals)
            delay = int(next_expire / 1000 - time.time())
            # Wake up a bit before the watch expires.
            delay = max(0, delay - 10)
            await asyncio.sleep(delay)
            for cal in gca.src_cals:
                # Renew watches that expired or are about to expire.
                if int(cal.watch_token["expiration"]) < time.time() + 60:
                    cal.watch()

    async def load_and_sync(self, app: aiohttp.web.Application) -> None:
        """Load calendar data and do a sync."""
        gca = app["gca"]
        gca.load_calendars()
        gca.sync_calendars()

    async def start_watches(self, app: aiohttp.web.Application) -> None:
        """Create a watch task."""
        app["watcher"] = asyncio.create_task(self.watch_calendars(app))

    async def stop_watches(self, app: aiohttp.web.Application) -> None:
        """Stop all calendar watches."""
        for cal in app["gca"].src_cals:
            cal.watch_stop()
        app["watcher"].cancel()

    def run(self) -> None:
        """Run the aplication."""
        app = aiohttp.web.Application()
        app.add_routes([
            aiohttp.web.get("/gca", self.webhook),
            aiohttp.web.post("/gca", self.webhook),
        ])

        app["gca"] = GCalAggregator(self.service, self.config)
        app.on_startup.append(self.load_and_sync)
        app.on_startup.append(self.start_watches)
        app.on_cleanup.append(self.stop_watches)

        aiohttp.web.run_app(app, host=self.config["address"], port=self.config["port"])

    def service(self) -> Resource:
        """Return a valid calendar Resource."""
        file = self.config["service_file"]
        if self._credentials is None:
            self._credentials = service_account.Credentials.from_service_account_file(
                file, scopes=SCOPES
            )
            self._resource = build("calendar", "v3", credentials=self._credentials)

        if self._credentials.valid:
            assert not self._credentials.expired
            return self._resource

        if self._credentials.expired:
            self.refresh_count += 1
            logging.info(f"Refresh count {self.refresh_count}")
            try:
                self._credentials.refresh(Request())
            except RefreshError:
                self._credentials = service_account.Credentials.from_service_account_file(
                    file, scopes=SCOPES
                )

        if "delegation" in self.config:
            self._credentials = self._credentials.with_subject(self.config["delegation"])
        self._resource = build("calendar", "v3", credentials=self._credentials)
        return self._resource


@click.command()
@click.argument("config", envvar="CONFIG", type=click.Path(exists=True))
def main(config):
    """Entry point."""
    AggApp(config).run()


if __name__ == "__main__":
    main()

# vim:expandtab:sw=4:ts=4
