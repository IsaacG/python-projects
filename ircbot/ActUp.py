#! /usr/bin/python

def hookCode ( server, data ):
	if not data['Action']:
		return
	server.act ( data['User']['Nick'], data['Message'] + " right back" )

name = 'ActUp'

types = [ 'PRIVMSG' ]
