#! /usr/bin/python

def hookCode ( server, data ):
	server.dMsg ( data['Channel'], "Hello " + data['User']['Nick'] )

name = 'Greet'

types = [ 'JOIN' ]
