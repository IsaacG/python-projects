#!/bin/python

from html.parser import HTMLParser
from urllib.request import Request
from urllib.request import urlopen
from urllib import error as urlErrors


def getTitle ( url ):
	class TitleParser ( HTMLParser ):
		inTitle = False
		title = ''

		def handle_starttag(self, tag, attrs):
			if tag.lower() == 'title':
				self.inTitle = True

		def handle_data(self, data):
			if self.inTitle:
				self.title = self.title + data

		def handle_endtag(self, tag):
			if tag.lower() == 'title':
				self.inTitle = False
		
	try:
		request = Request ( url, headers = { 'user-agent': 'firefox' }, method = 'GET' )
		response = urlopen ( request )
	except urlErrors.HTTPError as e:
		return "Failed to fetch url. {}: {}".format( e.code, e.reason )
	except urlErrors.URLError as e:
		return "Failed to fetch url. {}".format( e.reason )

	if response.getcode() == 200:
		content = ''

		if response.info().get_content_type() != 'text/html':
			return "Content type: " + response.info().get_content_type()

		try:
			if response.info().get_content_charset():
				content = response.read().decode ( response.info().get_content_charset() )
			else:
				content = response.read().decode ( 'iso-8859-1' )
		except Exception:
			return "Unable to parse the website"

		parser = TitleParser ( strict = False )
		parser.feed ( content )

		title = parser.title.strip().translate( { "\n": " " } )

		return ( title )
	else:
		return "Error. Got HTTP code " + str ( response.getcode() )

if __name__ == "__main__":
	print ( getTitle ( 'http://gooldfdfsdf.com' ) )
	print ( getTitle ( 'http://google.com' ) )
