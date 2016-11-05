#! /usr/bin/python
#
# This module is used to publish announcements.
# It works through PMs.
# Users can send "start" or "stop" to be added to/removed from a list of "registered" nicks.
# The "owner" can PM a "SEND foo" command and the bot will send "foo" to all registered nicks.

def init(server, storage):
  # Set up the storage only if it's not yet defined.
  # Otherwise, don't override existing settings.
  if name not in storage:
    storage[name] = {'owner': 'yitz', 'nicks': set()}

def hookCode(server, data, storage):
  # Pull out the details we need.
  user = data['User']['Nick']
  identified = data['User']['Identified']
  message = data['Message']
  nicks = storage[name]['nicks']
  owner = storage[name]['owner']

  if message == 'start':
    # Register nicks on "start"
    if user in nicks:
      server.msg(user, 'You are already registered')
    else:
      nicks.add(user)
      server.msg(user, 'You have been added')
  elif message == 'stop':
    # Remove nicks on "stop"
    if user in nicks:
      nicks.remove(user)
      server.msg(user, 'You have been removed')
    else:
      server.msg(user, 'You were not registered')
  elif message[0:4] == 'SEND':
    # Announce info on "SEND" but only from the owner
    if identified and user == owner:
      for n in nicks:
        server.msg(n, message[5:])
    else:
      server.msg(user, 'You cannot use that command')

name = 'Announce'
types = ['PRIVMSG']

# vim:expandtab:sw=2:ts=2
