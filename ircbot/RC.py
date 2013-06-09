#! /usr/bin/python

def hookCode ( server, data, storage ):
	if data['Message'] == "RC":
		for channel in server.channels:
			server.msg ( data['User']['Nick'], "join " + channel )
		for module in server.callbackData:
			if module[0] != '_':
				server.msg ( data['User']['Nick'], "load " + module )

name = 'RC'

types = [ 'PRIVMSG' ]
