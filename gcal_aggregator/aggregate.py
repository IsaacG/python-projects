#!/bin/python

"""Google Calendar Aggregator.

Manage a public Google Calendar which reflects events from a list of shared calendars.
This allows multiple people to organize and update events and have them all published
to a shared calendar with their account info not shared.

To add events to the shared calendar:
* Visit http://calendar.google.com/ on a computer.
* Hit the + next to "Other calendars" on the left bar > Create new calendar.
* Name it something that has the SHARED_CAL_TAG somewhere in the title.
* Click "Create calendar" only once and wait a few seconds until it creates.
* On the left bar under Settings, click on that calendar name you just created.
* "Share with specific people" => the public account.
* Click "Get shareable link" and share that with the public account so it can add it.
"""

import datetime
import functools
import pathlib
import time

from typing import Optional
import dateutil.parser

from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

import config

# dict[str, dict[str, dict[str, str]]]
# Calendar ID => configs {"description_tags": {tag_name: tag_val}}
# Used to add metadata to events based on calendarId.
CALS = config.CALS
# Filename for credentials.json, used for API access.
# Downloaded from Google Cloud Console.
CREDS_FILE: str = config.CREDS_FILE
# Filename for token.json, stores the OAuth permissions.
# Auto-created.
TOKEN_FILE: str = config.TOKEN_FILE
# Calendar name for the published calendar.
AGG_CAL_NAME: str = config.AGG_CAL_NAME
# Tag, used to filter shared calendars.
SHARED_CAL_TAG: str = config.SHARED_CAL_TAG
# Poll interval, seconds, between sync attempts.
POLL_TIME: int = config.POLL_TIME


# API permissions.
SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar",
]


@functools.cache
def service():
    """Return a Google Calendar Service API."""
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if pathlib.Path(TOKEN_FILE).exists():
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())

    return build("calendar", "v3", credentials=creds)


class Event(dict):
    """Google Calendar Event wrapper."""

    # Keys used to check for eqality and reposting.
    KEYS = ("summary", "description", "location", "start_dt", "end_dt", "kind", "recurrence")

    def __init__(self, data: dict, addition: Optional[str] = None):
        """Initialize."""
        super().__init__(data)
        # Convert date strings to datetime objects for TZ-aware equality.
        for time_s in ("start", "end"):
            if self.get(time_s, {}).get("dateTime", None):
                self[f"{time_s}_dt"] = dateutil.parser.isoparse(self[time_s]["dateTime"])
        # Add calendar metadata.
        if addition:
            self.setdefault("description", "")
            self["description"] += "<hr /><span>" + addition + "</span>"

    def __eq__(self, other: object):
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

    def delete(self):
        """Delete this event from Google Calendar."""
        calendar_id = self["organizer"]["email"]
        service().events().delete(calendarId=calendar_id, eventId=self["id"]).execute()

    def add(self, dest_cal):
        """Add this event to a Google Calendar."""
        body = {key: self[key] for key in self.KEYS if key in self}
        # Convert datetime back to a string.
        for time_s in ("start", "end"):
            if f"{time_s}_dt" in body:
                body[time_s] = {"dateTime": body[f"{time_s}_dt"].isoformat()}
                del body[f"{time_s}_dt"]
        service().events().insert(calendarId=dest_cal["id"], body=body).execute()


class Calendar(dict):
    """Calendar wrapper."""

    @property
    def tags(self):
        """Return tag pairs."""
        tags = []
        for line in self.get("description", "").splitlines():
            if ":" not in line:
                continue
            key, val = line.strip().split(":", 1)
            tags.append((key.strip(), val.strip()))
        return tags

    def get_tags(self, tag) -> list[str]:
        """Return tag values for a tag name."""
        return [val for key, val in self.tags if key == tag]

    @property
    def destination(self) -> list[str]:
        """"Return where events from this calendar should be published."""
        return self.get_tags("Publish")

    @property
    def name(self) -> str:
        """"Return the calendar name."""
        return self["summary"]

    @property
    def id(self) -> str:
        """Return the calendar ID."""
        return self["id"]

    @property
    def is_owner(self) -> bool:
        """Return if we are the calendar owner."""
        return self["accessRole"] == "owner"

    def __hash__(self) -> int:
        return hash(self["id"])

    def future_events(self):
        """Return future events for this calendar."""
        if self.is_owner:
            addition = ""
        else:
            sources = self.get_tags("Source")
            if sources:
                source = sources[0]
            else:
                source = CALS[self.id].get("source", "MISSING")
            addition = f"Source: {source}"

        now = datetime.datetime.utcnow().isoformat() + "Z" # "Z" indicates UTC time
        response = service().events().list(calendarId=self.id, timeMin=now).execute()
        return [Event(event, addition) for event in response.get("items", [])]


class GCalAggregator:
    """Google Calendar Aggregator."""

    def __init__(self, default_dest: str, search: str):
        """Initialize an Aggregator."""
        self.default_dest = default_dest
        self.search = search
        self.delete_old = False

    def remove_past_events(self, calendar):
        """Delete events that are already over."""
        now = datetime.datetime.utcnow().isoformat() + "Z" # "Z" indicates UTC time
        response = service().events().list(calendarId=calendar.id, timeMax=now).execute()
        events = [Event(event) for event in response.get("items", [])]
        for event in events:
            event.delete()

    def get_cals(self) -> dict[Calendar, list[Calendar]]:
        """Return a mapping of destination calendar to all sources for it."""
        resp = service().calendarList().list(showHidden=True).execute()
        calendars = [Calendar(c) for c in resp["items"]]
        own_cals = [c for c in calendars if c.is_owner]
        other_cals = [c for c in calendars if not c.is_owner]
        # Calendars that are the source of events to publish.
        source_cals: set[Calendar] = set()
        source_cals.update(c for c in other_cals if self.search in c.name)
        source_cals.update(c for c in other_cals if c.destination)

        want_destinations = {self.default_dest}
        for src in source_cals:
            want_destinations.update(src.destination)
        have_destinations = {c.name for c in own_cals}
        if want_destinations - have_destinations:
            print("Wanted destination that do not exist:", want_destinations - have_destinations)

        # Map publication outputs to a list of their inputs.
        dst_src: dict[Calendar, list[Calendar]] = {}
        for dst in own_cals:
            if dst.name not in want_destinations:
                print("Skip own cal, not in use:", dst.name)
                continue
            dst_src[dst] = []
            for src in source_cals:
                if dst.name in src.destination or (
                    dst.name == self.default_dest and not src.destination
                ):
                    dst_src[dst].append(src)

        return dst_src

    def sync_calendars(self):
        """Sync events to public calendars."""
        dst_src = self.get_cals()

        all_cals = set(dst_src.keys())
        for srcs in dst_src.values():
            all_cals.update(srcs)
        events = {c: c.future_events() for c in all_cals}
        print("Fetched events for calendars:", ", ".join(e.name for e in events.keys()))

        for dst, srcs in dst_src.items():
            drop = [e for e in events[dst] if not any(e in events[src] for src in srcs)]
            add = [e for src in srcs for e in events[src] if e not in events[dst]]
            for event in drop:
                print("Drop:", event)
                event.delete()
            for event in add:
                print("Add:", event)
                event.add(dst)

    def daemon(self, poll_time):
        """Run in daemon/poll mode."""
        while True:
            self.sync_calendars()
            time.sleep(poll_time)


def main():
    """Entry point."""
    GCalAggregator(AGG_CAL_NAME, SHARED_CAL_TAG).daemon(POLL_TIME)


if __name__ == "__main__":
    main()

# vim:expandtab:sw=4:ts=4
