#! /usr/bin/python

def hookCode ( server, data ):
	if data['Message'] == 'loaded':
		for cType in server.callbacks:
			print ( "{}: {}".format ( cType, ", ".join( server.callbacks[ cType ].keys() ) ) )

name = 'Raw'

desc = 'Show what hooks are loaded'

types = [ 'PRIVMSG' ]

