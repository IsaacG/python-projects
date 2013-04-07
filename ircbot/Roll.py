#! /usr/bin/python

import random

random.seed()

def hookCode ( server, data ):
	if data['Channel'].lower() in [ '#some_channel', '#other_channel' ]:
		parts = data['Message'].split()
		if parts[0] == '.roll':
			if len ( parts ) == 1:
				server.msg ( data['Channel'], "{}: you rolled a {}".format ( data['User']['Nick'], str ( random.randint ( 1, 6 ) ) ) )
			elif len ( parts ) == 2:
				server.msg ( data['Channel'], "{}: you rolled a {}".format ( data['User']['Nick'], random.randint ( 1, int ( parts[1] ) ) ) )
			elif len ( parts ) == 3:
				sum = 0
				for x in range ( int ( parts[1] ) ):
					sum += random.randint ( 1, int ( parts[2] ) )
				server.msg ( data['Channel'], "{}: you rolled a {}".format ( data['User']['Nick'], sum ) )

name = 'Roll'

desc = 'Dice rolling'

types = [ 'PUBMSG' ]

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
