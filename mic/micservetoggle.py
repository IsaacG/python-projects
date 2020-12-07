#!/bin/python

import http.server
import pulsectl
import socketserver
import time

from flask import Flask, request


COMMANDS = {
  'bt_on': 'Bluetooth On',
  'usb_on': 'USB On',
  'mute_on': 'Mute',
}
STYLE = 'style="font-size:6vw;"'


def get_one(l):
  assert len(l) == 1, f"Want one. Got {len(l)}."
  return l[0]


class PA:
  """PulseAudio mic mute toggler."""

  def __init__(self):
    self.pulse = pulsectl.Pulse()
    self.muted = False

  def bt_profile(self, profile):
    c = self.bt_card()
    p = get_one([i for i in c.profile_list if profile in i.name])
    self.pulse.card_profile_set(c, p)
    time.sleep(.2)

  def bt_card(self):
    bt = self.bt_sink()
    return get_one([i for i in self.pulse.card_list() if i.index == bt.card])

  def bt_src(self):
    s = [
      i for i in self.pulse.source_list()
      if (
        i.proplist['device.bus'] == "bluetooth"
        and not i.description.startswith('Monitor of')
      )
    ]
    return get_one(s)

  def bt_sink(self):
    s = [
      i for i in self.pulse.sink_list()
      if i.proplist['device.bus'] == "bluetooth"
    ]
    return get_one(s)

  def usb_mic_src(self):
    s = [
      i for i in self.pulse.source_list()
      if i.proplist.get('device.product.name') == "USB Audio Device"
    ]
    return get_one(s)

  def mute_str(self, s):
    if s.mute:
      return 'Muted'
    else:
      return 'Live'

  def status(self):
    r = f'USB: {self.mute_str(self.usb_mic_src())}. '
    if 'a2dp' in self.bt_card().profile_active.name:
      r += 'BT: Muted. '
    elif 'headset' in self.bt_card().profile_active.name:
      r += f'BT: {self.mute_str(self.bt_src())}. '
    else:
      r += 'BT: Unknown. '
    return r

  def usb_on(self):
    self.bt_profile('a2dp_sink')
    self.pulse.source_mute(self.usb_mic_src().index, mute=False)
    self.muted = False

  def bt_on(self):
    self.pulse.source_mute(self.usb_mic_src().index, mute=True)
    self.bt_profile('headset')
    self.pulse.source_mute(self.bt_src().index, mute=False)
    self.muted = False

  def mute(self):
    # self.bt_profile('a2dp_sink')
    self.pulse.source_mute(self.usb_mic_src().index, mute=True)
    try:
        self.pulse.source_mute(self.bt_src().index, mute=True)
    except AssertionError:
        pass
    self.muted = True

  def toggle(self, func):
    if pa.muted:
      func()
      return "Live"
    else:
      pa.mute()
      return "Muted"


app = Flask(__name__)
pa = PA()

def render():
  msg = ''
  msg += f'<p {STYLE}>'
  msg += pa.status()
  msg += f'\n<form method=GET><input type=submit value="Refresh" {STYLE}/></form>'
  for k, v in COMMANDS.items():
    msg += f'\n<form method=POST><input type=submit name="{k}" value="{v}" {STYLE}/></form>'
  msg += '\n</p>'
  return msg


@app.route('/toggle_usb', methods=['GET'])
def toggle_usb():
  return pa.toggle(pa.usb_on)


@app.route('/toggle_bt', methods=['GET'])
def toggle_bt():
  return pa.toggle(pa.bt_on)


@app.route('/', methods=['GET'])
def status():
  return render()


@app.route('/', methods=['POST'])
def set_pa():
  cmd = get_one(list(request.form.to_dict().keys()))
  {
    'bt_on': pa.bt_on,
    'usb_on': pa.usb_on,
    'mute_on': pa.mute,
  }[cmd]()
  return render()
