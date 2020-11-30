#!/bin/python

from astral import sun as astral_sun
from datetime import datetime, timedelta
from typing import Iterable, Optional, Tuple
from urllib.parse import urljoin
import astral
import logging
import os
import pathlib
import requests
import time

FILE = pathlib.Path(os.environ['HOME']) / '.xdg/config/tokens/smartthings'
TZ = 'America/Los_Angeles'

class Sun:
  """Information about the sun and desired bulb color and level."""
  
  COLOR = {
    'daylight': 5900,
    'nightlight': 2700,
  }

  def __init__(self, location: astral.LocationInfo):
    self.location = location
    self.refresh()

  def refresh(self):
    """Update the sun data for today."""
    # Fade from nightlight to daylight
    self.fade_day = astral_sun.golden_hour(self.location.observer, tzinfo=TZ)
    # Fade from daylight to nightlight, sunset to dusk
    s = astral_sun.sun(self.location.observer, tzinfo=TZ)
    self.fade_night = (s['sunset'], s['dusk'])
    logging.info('Color change times: %s', ', '.join(str(s.time()) for s in self.fade_day + self.fade_night))

  def now(self) -> datetime:
    return datetime.now(tz=self.fade_day[0].tzinfo)

  def between(
    self, now: datetime, times: Tuple[datetime, datetime],
    colors: Tuple[int, int]
  ) -> int:
    """Map the current time on a time spectrum to a number on a number spectrum."""
    # Progress through the time range.
    t_delta = times[1] - times[0]
    progress = (now - times[0]) / t_delta
    # Map time progress to progress through the colors.
    c_delta = colors[1] - colors[0]
    c = progress * c_delta + colors[0]
    return int(c)

  def level(self) -> int:
    """Current desired level."""
    n = self.now()
    if n.hour < 2:
      return 15
    if n < self.fade_day[0]:
      return 25
    if n < self.fade_day[1]:
      return self.between(n, self.fade_day, (25, 100))
    if n.hour < 22:
      return 100
    fade = (
      n.replace(hour=22, minute=0, second=0, microsecond=0),
      n.replace(hour=23, minute=59, second=0, microsecond=0)
    )
    return self.between(n, fade, (100, 25))
    
  def color(self) -> int:
    """Current desired color."""
    n = self.now()
    if n.date() > self.fade_day[0].date():
      self.refresh()
    if n < self.fade_day[0]:
      return self.COLOR['nightlight']
    if n < self.fade_day[1]:
      return self.between(n, self.fade_day, (self.COLOR['nightlight'], self.COLOR['daylight']))
    if n < self.fade_night[0]:
      return self.COLOR['daylight']
    if n < self.fade_night[1]:
      return self.between(n, self.fade_night, (self.COLOR['daylight'], self.COLOR['nightlight']))
    return self.COLOR['nightlight']


class SmartThings:
  """SmartThings API."""

  API = 'https://api.smartthings.com/'

  def __init__(self, token: str):
    self.s = requests.Session()
    self.s.headers.update({'Authorization': f'Bearer {token}'})

  def get(self, path: str):
    r = self.s.get(urljoin(self.API, path))
    r.raise_for_status()
    return r.json()

  def post(self, path: str, data: dict):
    url = urljoin(self.API, path)
    logging.info(data)
    return self.s.post(url, json=data).json()

    
class Device:
  """SmartDevice API."""

  # How often to refresh data.
  # Make sure this is less than the INTERVAL.
  MAX_STALE = timedelta(seconds=30)
  CAPS = {
    'colorTemperature': 'setColorTemperature',
    'switchLevel': 'setLevel',
  }

  def __init__(self, st, device_id, caps: Optional[Iterable[str]] = None):
    self.st = st
    self.device_id = device_id
    self.caps = caps or []
    self.refresh()
    for cap in self.caps:
      if cap not in self.CAPS:
        raise ValueError(f'Unknown capability {cap}')
      if cap not in self.component:
        raise ValueError(f'Capability {cap} not found in device {self.component}')

  def get(self, parts: Iterable[str]) -> dict:
    """Perform a REST API GET."""
    return self.st.get('/'.join(['devices', self.device_id] + parts))

  def set_cap(self, cap: str, val: int):
    """Set a capability value."""
    if self.value(cap) == val:
      return
    self.command(cap, self.CAPS[cap], [val])

  def command(self, capability: str, command: str, args: Iterable[str]):
    """Perform a device command API call."""
    data = {'commands': [{
      'component': self.component_name,
      'capability': capability,
      'command': command,
      'arguments': args
    }]}
    return self.st.post('/'.join(['devices', self.device_id, 'commands']), data)

  def refresh(self):
    """Refresh device status."""
    self.status = self.get(['status'])
    assert len(self.status['components']) == 1
    self.component_name = list(self.status['components'])[0]
    self.component = self.status['components'][self.component_name]
    self._updated = datetime.now()

  def maybe_refresh(self):
    """Refresh status if stale."""
    if datetime.now() > self._updated + self.MAX_STALE:
      self.refresh()

  def value(self, capability: str):
    """Return a capability's value."""
    self.maybe_refresh()
    cap = self.component[capability]
    assert len(cap) == 1
    return list(cap.values())[0]['value']

  @classmethod
  def from_label(
    cls, st: SmartThings, label: str, caps: Optional[Iterable[str]] = None
  ) -> 'Device':
    """Return a Device, selected by label."""
    j = st.get('devices')
    l = [i['deviceId'] for i in j['items'] if i['label'] == label]
    assert len(l) == 1
    return cls(st, l[0], caps)


class Light(Device):
  """Light bulb device."""
  
  def set_cap(self, cap, val):
    """Set light capability, only if the light is not off."""
    if self.value('light') == 'off':
      return
    super().set_cap(cap, val)


class SunTracking:
  """Track the sun, updating a light bulb accordingly."""

  INTERVAL = 70  # Bigger than the MAX_STALE
  RETRY_INTERVAL = 60

  def __init__(self, st: SmartThings, label: str, location: astral.LocationInfo):
    self.device = Light.from_label(st, label, ('colorTemperature', 'switchLevel'))
    self.sun = Sun(location)

  def track(self):
    """Track in a loop."""
    while True:
      try:
      	self.update()
      	time.sleep(self.INTERVAL)
      except requests.exceptions.ConnectionError:
      	time.sleep(self.RETRY_INTERVAL)

  def update(self):
    self.device.set_cap('colorTemperature', self.sun.color())
    self.device.set_cap('switchLevel', self.sun.level())


def main():
  logging.basicConfig(level=logging.INFO)
  token = FILE.read_text().strip()
  st = SmartThings(token)
  house = astral.LocationInfo('location', 'region', TZ, 37.2522887, -121.8967216)
  SunTracking(st, 'Office light', house).track()


if __name__ == '__main__':
  main()
