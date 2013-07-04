#! /usr/bin/python

import time

def hookCode ( server, data, storage ):
	parts = data['Message'].split()
	if data['Type'] == 'PRIVMSG' and data['Message'] == 'ping':
		server.ctcp ( data['User']['Nick'], 'PING', str ( time.time() ) )
	if data['Type'] == 'NOTICE':
		message = data['Message']
		if message[0] == '\x01' and message[-1] == '\x01':
			message = message.lstrip ( '\x01' )
			message = message.rstrip ( '\x01' )
			parts = message.split()
			if len ( parts ) == 2 and parts[0] == 'PING':
				startTime = float( parts[1] )
				delay = time.time() - startTime
				server.msg ( data['User']['Nick'], "Your PING time is " + str ( delay ) )


name = 'Ping'

desc = 'Get Ping Values'

types = [ 'NOTICE', 'PRIVMSG' ]

# Debug code
if __name__ == '__main__':
	class dummy:
		def msg ( s, d, m ):
			print ( "{}: {}".format( d, m ) )

	s = dummy ()
	d = {}
	d['Channel'] = '#some_channel'
	d['Message'] = '.roll 10 100'
	d['User'] = {}
	d['User']['Nick'] = 'me'
	hookCode ( s, d )
