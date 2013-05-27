#! /usr/bin/python
import time

def hookCode ( server, data, storage ):
	#if data['Channel'].lower() != '#justshmoozing':
	#	return()

	if "initialized" not in storage:
		storage['initialized'] = True
		storage['Messages'] = {}
		storage['Parts'] = {}
		storage['Settings'] = { "length": 100, "channels": "" }
	
	channel = data['Channel'].lower()
	channels = storage['Settings']['channels'].lower().split( "," )
	if len ( storage['Settings']['channels'] ) != 0 and channel not in channels:
		return ()

	if channel not in storage['Messages']:
		storage['Messages'][ channel ] = []

	if channel not in storage['Parts']:
		storage['Parts'][ channel ] = {}

	class HistoryData:
		"""Deal with history storage and retrieval"""

		def pubmsg ( storage, data ):
			"""Store a channel message"""

			channel = data['Channel'].lower()

			if channel not in storage['Messages']:
				storage['Messages'][ channel ] = []

			storage['Messages'][ channel ].append ( { 
				'Time': time.time(),
				'Nick': data['User']['Nick'],
				'Body': data['Message'],
				'Action': data['Action']
			} )
			while len ( storage['Messages'][ channel ] ) > storage['Settings']['length']:
				del ( storage['Messages'][ channel ][ 0 ] )

		def part ( storage, channel, nick ):
			"""Record a part or quit"""
			if channel not in storage['Parts']:
				storage['Parts'][ channel ] = {}

			storage['Parts'][ channel ][ nick.lower() ] = time.time();


		def join ( storage, channel, nick ):
			"""React to a join"""

			partTime = 0
			if nick.lower() in storage['Parts'][ channel ]:
				partTime = storage['Parts'][ channel ][ nick.lower() ]

			messages = [ m for m in storage['Messages'][ channel ] if m['Time'] >= partTime ]

			server.msg ( 
				nick, 
				"Welcome to {}, {}. I saw you part {} minutes ago and have {} lines of new channel history for you.".format (
					channel, nick, int ( ( time.time() - partTime ) / 60 ), len ( messages )
				)
			)
			for message in messages:
				formatString = ""
				if message['Action']:
					formatString = "{} * {}"
				else:
					formatString = "<{}> {}"
				server.msg ( nick, formatString.format ( message['Nick'], message['Body'] ) )

		def dump ( storage, channel ):
			"""Dump some data"""
			server.msg ( channel, "There are {} stored messages.".format( len ( storage['Messages'][ channel ] ) ) )
			server.msg ( channel, "I have {} parts on file.".format( len ( storage['Parts'][ channel ] ) ) )
			

	if data['Type'] == 'PUBMSG':
		if data['Message'] == 'sharedump':
			HistoryData.dump ( storage, data['Channel'] )
		else:
			HistoryData.pubmsg ( storage, data )
	elif data['Type'] == 'PART' or data['Type'] == 'QUIT':
		HistoryData.part ( storage, data['Channel'], data['User']['Nick'] )
	elif data['Type'] == 'JOIN':
		HistoryData.join ( storage, data['Channel'], data['User']['Nick'] )

name = 'ShareHistory'

types = [ 'JOIN', 'QUIT', 'PART', 'PUBMSG' ]

