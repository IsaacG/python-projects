#! /usr/bin/python

# tweak settings for modules
# access the storage[module]['settings] dict

def hookCode ( server, data, storage ):
	parts = data['Message'].split()
	if len ( parts ) == 0 or parts[0] != 'set':
		return()

	callbackData = server.callbackData
	nick =  data['User']['Nick']

	if len ( parts ) == 1:
		# list modules
		server.msg ( nick, ", ".join ( [ m for m in callbackData if 'Settings' in callbackData[ m ] ] ) )
	elif len ( parts ) == 2:
		# list settings for the module
		if parts[1] in callbackData:
			if 'Settings' in callbackData[ parts[1] ]:
				server.msg ( nick, ", ".join ( callbackData[ parts[1] ]['Settings'].keys() ) )
			else:
				server.msg ( nick, "That modules doesn't have settings" )
		else:
			server.msg ( nick, "No such module loaded." )
	elif len ( parts ) == 3:
		# show value
		server.msg ( nick, callbackData[ parts[1] ]['Settings'][ parts[2] ] )
	elif len ( parts ) == 4:
		# set value
		callbackData[ parts[1] ]['Settings'][ parts[2] ] = parts[3]
	else:
		server.msg ( nick, "Usage: set <Module> [<key> [<value>]]" )

name = 'Set'

desc = 'Tweak settings'

types = [ 'PRIVMSG' ]

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
