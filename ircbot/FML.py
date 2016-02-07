#! /usr/bin/python

import feedparser

name = 'FML'
desc = 'Display FML entries'
types = ['PUBMSG']
fml_url = 'http://feedpress.me/fmylife'

def FetchFreshEntries():
  feed = feedparser.parse(fml_url)
  entries = feed.entries
  entries.reverse()
  return entries

def init(server, storage):
  storage[name] = {'entries': FetchFreshEntries(), 'shown_entries': set()}

def PopNewEntry(storage):
  while storage[name]['entries']:
    entry = storage[name]['entries'].pop()
    if entry.id in storage[name]['shown_entries']:
      continue
    storage[name]['shown_entries'].add(entry.id)
    content = entry.content[0].value[3:-4]
    return content
  return None

def GetFML(storage):
  entry = PopNewEntry(storage)
  if entry is None:
    # print('Ran out of FML entries; fetching new entries.')
    storage[name]['entries'] = FetchFreshEntries()
    entry = PopNewEntry(storage)
  if entry is None:
    entry = 'We are clean out of fresh FMLs. Try again later.'
  entry = entry.encode('ascii', 'replace')
  return entry.decode('ascii')

def hookCode(server, data, storage):
  if data['Message'] != '.fml':
    return
  server.msg(data['Channel'], GetFML(storage))

# Debug code
if __name__ == '__main__':
  class dummy:
    def msg ( s, d, m ):
      print ( "{}: {}".format( d, m ) )

  s = dummy ()
  d = {}
  d['Channel'] = '#some_channel'
  d['Message'] = '.fml'
  d['User'] = {}
  d['User']['Nick'] = 'me'
  storage = {}
  init(s, storage)
  for i in range(5):
    hookCode(s, d, storage)
