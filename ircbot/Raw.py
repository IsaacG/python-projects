#! /usr/bin/python

def hookCode ( server, data ):
	parts = data['Message'].split()
	if len ( parts ) > 1 and parts[0] == "raW":
		server.send ( data['Message'].lstrip ( "raW" ).lstrip( " " ) )

name = 'Raw'

desc = 'Send a raw message'

types = [ 'PRIVMSG' ]

