"""Manage management bot.

This is a custom channel management bot. Features include:

* Bot ops, defined by hostmask.
* Member vetting. Vetted members can vet other members. Vetted members are not
  subject to auto bans and are eligible for a voice.
* Auto bans for bad behavior: nick patterns, user patterns, foul language,
  repetitive messages and mass highlighing.
* Voice on join (can be toggled).
* Lockdown (+mz and voice all).
"""

import functools
import more_itertools
import re
import sopel


PLUGIN = 'chan_manage'
REPEAT_RE = re.compile(r'(....+) \1 \1 \1')


# ===========
# = Classes =
# ===========


class NickManager:
  """Manage data and nicks and all that. Intended to be a singleton."""

  def __init__(self, bot):
    self.bot = bot
    self.reload()

  def re_join(self, patterns):
    """Join RE's with an OR."""
    patt = '|'.join('(%s)' % p for p in patterns)
    return re.compile(patt, re.IGNORECASE)

  def reload(self):
    """Load data from the DB."""
    self.vetted = set(s.lower() for s in self.bot.db.get_plugin_value(PLUGIN, 'vetted'))
    self.banned = set(s.lower() for s in self.bot.db.get_plugin_value(PLUGIN, 'banned'))
    self.ops = self.bot.db.get_plugin_value(PLUGIN, 'ops')
    self.bad_words = self.bot.db.get_plugin_value(PLUGIN, 'bad_words')
    self.bad_names = self.bot.db.get_plugin_value(PLUGIN, 'bad_names')
    self.channels = self.bot.db.get_plugin_value(PLUGIN, 'channels')

    # Nicks should be treated as string literals so escape them.
    self.vetted_re = self.re_join(re.escape(v) for v in self.vetted)
    # Ops and banned are hostmasks. Convert to hostmask RE.
    self.banned_re = self.re_join(sopel.tools.get_hostmask_regex(b).pattern for b in self.banned)
    self.ops_re = self.re_join(sopel.tools.get_hostmask_regex(o).pattern for o in self.ops.values())
    # Ban words are regexes. Just join them.
    self.bad_words_re = self.re_join(self.bad_words)
    self.bad_names_re = self.re_join(self.bad_names)

  def bad_user(self, trigger):
    """Return if the nick or user is offensive."""
    return self.bad_names_re.search(trigger.nick) or self.bad_names_re.search(trigger.user)

  def is_op(self, hostmask):
    """Return if the hostmask matches the ops hostmasks."""
    return bool(self.ops_re.match(hostmask))

  def is_banned(self, trigger):
    """Return if the user matches a hostmask on the ban list."""
    return bool(self.banned_re.fullmatch(trigger.hostmask.lower()))

  def is_vetted_user(self, nick):
    """Return if the user is on the vetted list."""
    return bool(self.vetted_re.fullmatch(nick.lower()))

  def is_vetted(self, trigger):
    """Return if the user is on the vetted list."""
    return self.is_vetted_user(trigger.nick)

  def add_vetted(self, nick):
    """Add a nick to the vetted list."""
    nick = nick.lower()
    if nick in self.vetted:
      return

    self.vetted.add(nick)
    bot.db.set_plugin_value(PLUGIN, 'vetted', list(self.vetted))
    self.vetted_re = self.re_join(re.escape(v) for v in self.vetted)

  def drop_vetted(self, nick):
    """Remove a nick from the vetted list."""
    nick = nick.lower()
    if nick not in self.vetted:
      return

    self.vetted.remove(nick)
    bot.db.set_plugin_value(PLUGIN, 'vetted', list(self.vetted))
    self.vetted_re = self.re_join(re.escape(v) for v in self.vetted)

  def add_ban(self, mask):
    """Add a mask to the ban list."""
    mask = mask.lower()
    if mask in self.banned:
      return

    self.banned.add(mask)
    bot.db.set_plugin_value(PLUGIN, 'banned', list(self.banned))
    self.banned_re = self.re_join(sopel.tools.get_hostmask_regex(b).pattern for b in self.banned)

  def drop_ban(self, mask):
    """Remove a mask from the ban list."""
    mask = mask.lower()
    if mask not in self.banned:
      return

    self.banned.remove(b)
    bot.db.set_plugin_value(PLUGIN, 'banned', list(self.banned))
    self.banned_re = self.re_join(sopel.tools.get_hostmask_regex(b).pattern for b in self.banned)

  def bad_message(self, message):
    """Return if the message got bad words."""
    return bool(self.bad_words_re.search(message))

  def log(self, trigger, message):
    """Log to the associated log channel."""
    destination = self.channels[trigger.sender.lower()]
    self.bot.say(message, destination)


# ====================
# = Helper Functions =
# ====================


def setup(bot):
  """Setup the bot memory."""
  bot.memory['banned'] = {}
  bot.memory['autovoice'] = {}
  for c in manager(bot).channels:
    bot.memory['autovoice'][c] = bot.db.get_channel_value(c, 'autovoice', False)


def kickban(bot, channel, nick, mask):
  """Kick then ban a user."""
  nick = nick.lower()
  bot.memory['banned'][nick] = (channel, mask)
  bot.write(('MODE', channel, '+b', mask))
  bot.kick(nick, channel)
  manager(bot).add_ban(f'{nick}!*@*')


@functools.cache
def manager(bot):
  return NickManager(bot)
    

def get_channels(bot, trigger):
  m_chans = manager(bot).channels
  parts = trigger.args[-1].lower().split()
  if parts:
    channels = [p for p in parts if p in m_chans]
    if channels:
      return channels
  return m_chans.keys()


# ======================
# = Require Decorators =
# ======================


def require_vetted(is_vetted):
  """Decorator that requires the user be a vetted user."""
  def actual_decorator(function):
    @functools.wraps(function)
    def guarded(bot, trigger, *args, **kwargs):
      if is_vetted == (trigger.admin or manager(bot).is_vetted(trigger)):
        return function(bot, trigger, *args, **kwargs)
    return guarded
  return actual_decorator


def require_op():
  """Decorator that requires the user be an op."""
  def actual_decorator(function):
    @functools.wraps(function)
    def guarded(bot, trigger, *args, **kwargs):
      if manager(bot).is_op(trigger.hostmask):
        return function(bot, trigger, *args, **kwargs)
    return guarded
  return actual_decorator


def require_word_count(minimum, maximum=None):
  """Decorator that requires the message contain a number of words."""
  def actual_decorator(function):
    @functools.wraps(function)
    def guarded(bot, trigger, *args, **kwargs):
      parts = trigger.args[-1].split()
      words = len(parts) - 1
      if words < minimum:
        return
      if maximum and words > maximum:
        return
      return function(bot, trigger, *args, **kwargs)
    return guarded
  return actual_decorator


# ====================
# = Voicing Commands =
# ====================

def voice_users(bot, channel):
  """Voice all eligible users."""
  channel = channel.lower()
  if channel not in bot.channels:
    print(f'Did not find {channel}.')
    return
  chan = bot.channels[channel]
  users = chan.users
  privileges = chan.privileges
  give_voice = []

  for nick, user in users.items():
    if privileges[nick] & sopel.module.VOICE:
      continue
    if not manager(bot).is_vetted_user(nick):
      continue
    give_voice.append(str(nick))
  for nicks in more_itertools.chunked(give_voice, 4):
    mode = 'v' * len(nicks)
    bot.write(['MODE', channel, f'+{mode}'] + nicks)

@sopel.module.rule('lockdown')
@sopel.module.require_privmsg()
@require_vetted(True)
def lockdown(bot, trigger):
  """Lock down a channel. +mz, voiceall and turn on autovoice."""
  for c in get_channels(bot, trigger):
    bot.memory['autovoice'][c] = True
    bot.db.set_channel_value(c, 'autovoice', True)
    voice_users(bot, c)
    bot.write(('MODE', c, '+mz'))


@sopel.module.rule('unlock')
@sopel.module.require_privmsg()
@require_vetted(True)
def unlock(bot, trigger):
  """Remove the lockdown +mz."""
  for c in get_channels(bot, trigger):
    bot.write(('MODE', c, '-mz'))


@sopel.module.rule('voicing')
@sopel.module.require_privmsg()
@require_op()
def voicing(bot, trigger):
  """Toggle auto voice on join."""
  for c in get_channels(bot, trigger):
    val = not bot.memory['autovoice'][c]
    bot.memory['autovoice'][c] = val
    bot.db.set_channel_value(c, 'autovoice', val)
    bot.say(f'Auto voicing for {c} set to {val}')


@sopel.module.rule('voiceall')
@sopel.module.require_privmsg()
@require_op()
def voiceall(bot, trigger):
  """Voice all vetted users."""
  for c in get_channels(bot, trigger):
    bot.memory['autovoice'][c] = True
    bot.db.set_channel_value(c, 'autovoice', True)
    voice_users(bot, c)


# =======================
# = Banning and Kicking =
# =======================


@sopel.module.rule(r'.*')
@sopel.module.require_chanmsg()
@require_vetted(False)
def bad_message(bot, trigger):
  """Ban unvetted users for poor behavior."""
  m = manager(bot)
  msg = None

  # Check for bad words.
  if not msg and m.bad_message(trigger.args[-1]):
    msg = f'Banning {trigger.nick} for using bad words. Said: {trigger.args[-1]}'

  # Check for a repeat pattern.
  if not msg and REPEAT_RE.search(trigger.args[-1].lower()):
    msg = f'Banning {trigger.nick} for being repetitive.'

  # Check for excessive highlighting.
  if not msg:
    words = trigger.args[-1].lower().split()
    users = [u.lower() for u in bot.channels[trigger.sender].users]
    highlight_count = sum(w in users for w in words)
    if highlight_count > len(words) // 2 or highlight_count > 4:
      msg = f'Banning {trigger.nick} for hilighting {highlight_count} times'

  if msg:
    m.log(trigger, msg)
    for c in manager(bot).channels:
      kickban(bot, c, trigger.nick, f'*!*@{trigger.host}')


@sopel.module.event('NOTICE')
@require_vetted(False)
def on_notice(bot, trigger):
  """Ban unvetted users for using NOTICE."""
  for c in manager(bot).channels:
    kickban(bot, c, trigger.nick, f'*!*@{trigger.host}')
  manager(bot).log(trigger, msg)


# ========================
# = User Role Management =
# ========================


@sopel.module.rule(r'\+v ')
@sopel.module.require_privmsg()
@require_word_count(1)
@require_vetted(True)
def add_vetted(bot, trigger):
  """Add a user to the vetted list."""
  nick = trigger.args[-1].split()[1]
  manager(bot).add_vetted(nick)
  for c in manager(bot).channels:
    bot.write(('MODE', c, '+v', nick))


@sopel.module.rule(r'-v ')
@sopel.module.require_privmsg()
@require_word_count(1)
@require_op()
def drop_vetted(bot, trigger):
  """Remove a user from the vetted list."""
  nick = trigger.args[-1].split()[1]
  bot.say(f'Drop +v for {nick}')
  manager(bot).drop_vetted(nick)


@sopel.module.rule('kick')
@sopel.module.require_privmsg()
@require_word_count(1)
@require_op()
def kick(bot, trigger):
  """Kick someone from a channel."""
  nick = trigger.args[-1].split()[1]
  for c in get_channels(bot, trigger):
    bot.kick(nick, c)


@sopel.module.rule(r'\+b ')
@sopel.module.require_privmsg()
@require_word_count(1)
@require_op()
def add_ban(bot, trigger):
  """Ban someone. Trigger a kickban and save the mask."""
  nick = trigger.args[-1].split()[1]
  print(f'Banning {nick}')
  if '!' in nick and '@' in nick:
    mask = nick
  elif '!' not in nick and '@' not in nick:
    mask = f'{nick}!*@*'
  else:
    bot.say('Invalid nick/mask')
    return
  print(f'Banning m {mask}')
  manager(bot).add_ban(mask)
  
  # Apply the mask to all users and kick anyone that matches.
  re = sopel.tools.get_hostmask_regex(mask)
  for c in get_channels(bot, trigger):
    for user in bot.channels[c].users.values():
      if re.match(user.hostmask):
        kickban(bot, c, user.nick, f'*!*@{user.host}')
        msg = f'Kick ban {user.nick} from {c}. New ban: {mask}'
        manager(bot).log(trigger, msg)


@sopel.module.rule(r'-b ')
@sopel.module.require_privmsg()
@require_word_count(1)
@require_op()
def unban(bot, trigger):
  """Remove a ban."""
  nick = trigger.args[-1].lower().split()[1]
  if '!' in nick and '@' in nick:
    ban_mask = nick
  elif '!' not in nick and '@' not in nick:
    ban_mask = f'{nick}!*@*'
  else:
    bot.say('Invalid nick/mask')
    return

  # Drop the ban from the ban list.
  manager(bot).drop_ban(ban_mask)

  # If we recently placed a channel ban, remove it.
  if nick in bot.memory['banned']:
    channel, mask = bot.memory['banned'][nick]
    bot.write(('MODE', channel, '-b', mask))
  for channel, mask in bot.memory['banned'].values():
    if ban_mask.lower() == mask.lower():
      bot.write(('MODE', channel, '-b', mask))


# =================
# = Miscellaneous =
# =================


@sopel.module.event('JOIN')
def on_join(bot, trigger):
  """Voice or ban users on join."""
  if trigger.sender not in manager(bot).channels:
    return

  m = manager(bot)

  if m.is_banned(trigger):
    kickban(bot, trigger.sender, trigger.nick, f'*!*@{trigger.host}')
    msg = f'Kick ban {trigger.hostmask}. They are on the ban list.'
    m.log(trigger, msg)
  elif m.is_vetted(trigger):
      if bot.memory['autovoice'][trigger.sender.lower()]:
        bot.write(('MODE', trigger.sender, '+v', trigger.nick))
  elif m.bad_user(trigger):
    kickban(bot, trigger.sender, trigger.nick, f'*!*@{trigger.host}')
    msg = f'Banning {trigger.nick} based on offensive hostmask {trigger.hostmask}.'
    m.log(trigger, msg)


@sopel.module.rule('help')
@sopel.module.require_privmsg()
def help(bot, trigger):
  """List bot help."""
  commands = [
    'ops                 - channel only; anyone; list/hilight ops',
    'help                - PM only; anyone; list this help',
    'lockdown [#channel] - PM only; vetted users; enable voicing and mode +mz',
    'unlock [#channel]   - PM only; vetted users; drop mode +mz',
    '+v <nick>           - PM only; vetted users; vet/voice <nick>',
    '-v <nick>           - PM only; ops only; unvet/unvoice <nick>',
    '+b <nick>           - PM only; ops only; ban <nick>',
    '-b <nick>           - PM only; ops only; unban <nick>',
    'kick <nick>         - PM only; ops only; kick <nick>',
    'voicing [#channel]  - PM only; ops only; toggle auto +v on join',
    'voiceall [#channel] - PM only; ops only; +v all vetted users',
  ]
  for c in commands:
    bot.say(c)


@sopel.module.rule('ops')
@sopel.module.require_chanmsg()
def ops(bot, trigger):
  """List ops."""
  chan_users = bot.channels[trigger.sender].users.values()
  ignore = {'not_yitz', 'chanslave', 'chanslave_v2'}
  ops = [u.nick for u in chan_users if manager(bot).is_op(u.hostmask) and u.nick not in ignore]

  bot.say(f'Ops: {", ".join(sorted(ops))}')

@sopel.module.event(sopel.tools.events.RPL_ENDOFNAMES)
def on_conn(bot, trigger):
  """Try to op-up on connecting to a channel."""
  print('RPL_ENDOFNAMES:', trigger.sender, trigger)
  if trigger.sender not in manager(bot).channels:
    return
  print('Connected. Try to op up.')
  bot.say(f'op {trigger.sender}', 'chanserv')


@sopel.module.rule(r'.*')
@sopel.module.require_privmsg()
def forward_pms(bot, trigger):
  """Forward all PMs sent to the bot to the bot owner."""
  owner = bot.config.get('core', 'owner')
  bot.say('%s: %s ' % (trigger.nick, trigger.args[-1]), destination=owner)


@sopel.module.commands('a')
@sopel.module.require_privmsg()
@sopel.module.require_owner()
def a(bot, trigger):
  """Test."""
  bot.say('Hello')
