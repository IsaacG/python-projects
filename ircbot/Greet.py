#! /usr/bin/python

def hookCode ( server, data, storage ):
	server.msg ( data['Channel'], "Hello " + data['User']['Nick'] )

name = 'Greet'

types = [ 'JOIN' ]
