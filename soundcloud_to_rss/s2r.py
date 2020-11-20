#!/bin/python

import datetime
import os
import re
import requests
import sclib
import sys

from feedgen import feed
from lxml import etree


def main():
  if len(sys.argv) != 3 or not sys.argv[1].startswith('https://soundcloud.com/'):
    print(f'Usage: {sys.argv[0]} https://soundcloud.com/... $HOSTNAME')
    return 1

  url = sys.argv[1]
  if not url.endswith('/'):
    url += '/'

  resp = requests.get(url)
  resp.raise_for_status()
  tree = etree.HTML(resp.content)

  pattern = re.compile(resp.request.path_url + '[0-9]+-')
  hrefs = tree.xpath('//a/@href')
  track_urls = [f'https://soundcloud.com{i}' for i in hrefs if pattern.match(i)]
  
  fg = feed.FeedGenerator()
  fg.load_extension('podcast')
  fg.id(url)
  fg.description(resp.request.path_url)
  fg.title(resp.request.path_url)
  fg.link(href=url, rel='self')
  fg.lastBuildDate(datetime.datetime.now().astimezone(datetime.timezone.utc))
  fg.updated(datetime.datetime.now().astimezone(datetime.timezone.utc))
  api = sclib.SoundcloudAPI()

  for url in track_urls:
    track = api.resolve(url)
    filename = f'{track.artist} - {track.title}.mp3'
    filename = re.sub('[^a-zA-Z0-9.]', '_', filename)
    fe = fg.add_entry()
    fe.id(track.permalink)
    fe.title(track.title)
    fe.description(track.description)
    fe.enclosure(os.path.join(sys.argv[2], filename), 0, 'audio/mpeg')
    fe.published(track.display_date)

    if os.path.exists(filename):
      print(f'{filename!r} exists. Skip.')
      continue
    with open(filename, 'wb+') as fp:
      track.write_mp3_to(fp)

  fg.rss_file('rss.xml')



if __name__ == '__main__':
  main()
