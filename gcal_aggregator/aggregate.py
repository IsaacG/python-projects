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

import config
import datetime
import dateutil.parser
import functools
import json
import pathlib
import time
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# dict[str, dict[str, dict[str, str]]]
# Calendar ID => configs {'description_tags': {tag_name: tag_val}}
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


class Event(dict):
  """Google Calendar Event wrapper."""

  # Keys used to check for eqality and reposting.
  KEYS = ('summary', 'description', 'location', 'start_dt', 'end_dt', 'kind', 'recurrence')

  def __init__(self, data):
    """Initialize."""
    super().__init__(data)
    # Convert date strings to datetime objects for TZ-aware equality.
    for time in ('start', 'end'):
      if time in self and 'dateTime' in self[time]:
        self[f'{time}_dt'] = dateutil.parser.isoparse(self[time]['dateTime'])
    # Add calendar metadata.
    if self['organizer']['email'] in CALS:
      tags = CALS[self['organizer']['email']].get('description_tags', [])
      addition = '<br>'.join(f'{k}: {v}' for k, v in tags.items())
      if addition:
        self['description'] += '<hr /><span>' + addition + '</span>'

  def __eq__(self, other: "Event"):
    """Return if events are equal, considering only public information."""
    assert type(self) == type(other), f'Cannot compare types {type(self)} to type {type(other)}'
    diff_contains = [key for key in self.KEYS if (key in self) != (key in other)]
    if diff_contains:
      return False
    diff_vals = [key for key in self.KEYS if self.get(key, None) != other.get(key, None)]
    if diff_vals:
      return False
    return True

  def delete(self, service):
    """Delete this event from Google Calendar."""
    calendarId = self['organizer']['email']
    service.events().delete(calendarId=calendarId, eventId=self['id']).execute()

  def add(self, service, dest_cal):
    """Add this event to a Google Calendar."""
    body = {key: self[key] for key in self.KEYS if key in self}
    # Convert datetime back to a string.
    for time in ('start', 'end'):
      if f'{time}_dt' in body:
        body[time] = {'dateTime': body[f'{time}_dt'].isoformat()}
        del body[f'{time}_dt']
    service.events().insert(calendarId=dest_cal['id'], body=body).execute()


class GCalAggregator:
  """Google Calendar Aggregator."""

  # API permissions.
  SCOPES = ['https://www.googleapis.com/auth/calendar.events', 'https://www.googleapis.com/auth/calendar']

  def __init__(self, name: str, search: str):
    """Initialize an Aggregator."""
    self.name = name
    self.search = search
    self.REMOVE_PAST_EVENTS = False

  @functools.cached_property
  def calendars(self):
    """Return all calendars."""
    return self.service.calendarList().list(showHidden=True).execute()['items']

  @functools.cached_property
  def service(self):
    """Return a Google Calendar Service API."""
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if pathlib.Path(TOKEN_FILE).exists():
      creds = Credentials.from_authorized_user_file(TOKEN_FILE, self.SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
      if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
      else:
        flow = InstalledAppFlow.from_client_secrets_file(CREDS_FILE, self.SCOPES)
        creds = flow.run_local_server(port=0)
      # Save the credentials for the next run
      with open(TOKEN_FILE, 'w') as token:
        token.write(creds.to_json())

    return build('calendar', 'v3', credentials=creds)

  def remove_past_events(self):
    """Delete events that are already over."""
    calendar = self.agg_cal
    now = datetime.datetime.utcnow().isoformat() + 'Z' # 'Z' indicates UTC time
    r = self.service.events().list(calendarId=self.agg_cal['id'], timeMax=now).execute()
    events = [Event(event) for event in r.get('items', [])]
    for event in events:
      event.delete(self.service)

  def future_events(self, calendar):
    """Return future events for a Google Calendar."""
    now = datetime.datetime.utcnow().isoformat() + 'Z' # 'Z' indicates UTC time
    r = self.service.events().list(calendarId=calendar['id'], timeMin=now).execute()
    return [Event(event) for event in r.get('items', [])]

  def get_calendars(self):
    """Return a list of shared calendars that match the search term."""
    cals = [c for c in self.calendars if c['accessRole'] != 'owner' and any(d in c and self.search in c[d] for d in ('summary', 'description'))]
    for c in cals:
      print('Calendar:', c['summary'], c['id'])
    return cals

  @property
  def agg_cal(self):
    """"Return the published aggregate calendar."""
    cals = [c for c in self.calendars if c['summary'] == self.name and c['accessRole'] == 'owner']
    assert len(cals) == 1
    return cals[0]

  def load_events(self):
    """Return published and shared events."""
    agg_events = self.future_events(self.agg_cal)
    shared = {c['summary']: self.future_events(c) for c in self.get_calendars()}
    return agg_events, shared

  def sync_cals(self):
    """Sync calendars."""
    if self.REMOVE_PAST_EVENTS:
      self.remove_past_events()
    agg_events, shared_events = self.load_events()
    drop = [e for e in agg_events if not any(e in events for events in shared_events.values())]
    add = [e for events in shared_events.values() for e in events if e not in agg_events]
    for event in drop:
      print('Drop:', event)
      event.delete(self.service)
    for event in add:
      print('Add:', event)
      event.add(self.service, self.agg_cal)

  def daemon(self, poll_time):
    """Run in daemon/poll mode."""
    while True:
      self.sync_cals()
      time.sleep(poll_time)


def main():
  """Entry point."""
  GCalAggregator(AGG_CAL_NAME, SHARED_CAL_TAG).daemon(POLL_TIME)


if __name__ == '__main__':
  main()

# vim:expandtab:sw=2:ts=2
