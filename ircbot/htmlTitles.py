#! /usr/bin/python

from htmlTitleParse import getTitle
import re

def hookCode ( server, data, storage ):
	for urlGroup in storage['re'].findall ( data['Message'] ):
		url = urlGroup[0]
		if url[0:3] == "www":
			url = "http://" + url
		server.msg ( data['Channel'], "{} [{}]".format ( getTitle ( url ), url ) )

def init ( server, storage ):
	storage['re'] = re.compile ( r'\b((http://|www\.)[-~=\/a-zA-Z0-9.:_?&%,#+]+)\b' )

name = 'htmlTitles'
desc = 'Get HTML titles'
types = [ 'PUBMSG' ]


if __name__ == "__main__":
	class Dummy:
		def msg ( d, m ):
			print ( "{}: {}".format( d, m ) )

	storage = {}

	server = Dummy
	init ( server, storage )

	data = {}
	data['Channel'] = '#test'
	for line in [ 
			'www.cooks.com http://img.cooks.com/i/icons/bbq.gif'
			# 'http://en.wikipedia.org/wiki/Ford_Mustang',
			# 'http://www.google.com www.abc.com', 
			# 'http://www.google.com something else www.abdfsfsddfsc.com. also',
			# 'http://en.wikipedia.org'
	]:
		data['Message'] = line
		hookCode ( server, data, storage )
