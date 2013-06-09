#! /usr/bin/python
import time
import random

def init ( server, storage ):
	storage['Settings'] = { "file": "topics.txt", "channels": "" }
	
	# load topics
	storage['Topics'] = {}

	# read topics from file
	with open ( storage['Settings']['file'] ) as fh:
		for line in fh:
			( timestamp, nick, channel, topic ) = line.rstrip().split ( '\t', 4 )
			if channel not in storage['Topics']:
				storage['Topics'][ channel ] = []
			storage['Topics'][ channel ].append ( topic )


def hookCode ( server, data, storage ):
	channel = data['Channel'].lower()

	# channel filtering
	channels = storage['Settings']['channels'].split( "," )
	if len ( storage['Settings']['channels'] ) != 0 and channel not in channels:
		return ()

	if channel not in storage['Topics']:
		storage['Topics'][ channel ] = []

	class TopicBank:
		"""Store and retrieve topics"""

		def addtopic ( storage, nick, channel, topic ):
			"""Add a new topic"""
			storage['Topics'][ channel ].append ( topic )

			items = [ str ( int ( time.time() ) ), nick, channel, topic ]
			with open ( storage['Settings']['file'], 'a' ) as fh:
				print ( "\t".join ( items ), file=fh )

		def dump ( storage ):
			"""Dump some debug info"""
			print ( repr ( storage ) )

		def randomTopic ( storage, channel ):
			"""Fetch a random channel topic"""
			if len ( storage['Topics'][ channel ] ) > 0:
				return ( random.choice ( storage['Topics'][ channel ] ) )

	parts = data['Message'].split( maxsplit = 1 )
	
	if parts[0] == '!addtopic' and len ( parts ) > 1:
		TopicBank.addtopic (
			storage,
			data['User']['Nick'].lower(),
			channel,
			parts[1] )
	if parts[0] == '!topic':
		server.msg ( channel, TopicBank.randomTopic ( storage, channel ) )
	if parts[0] == '!topicdump':
		TopicBank.dump ( storage )

name = 'TopicBank'

types = [ 'PUBMSG' ]

# addtopic  -> print $FH join( "\t", time, $nick, $channel, join ( " ", @words ) ) . "\n";
# add to list
# on start, load from file
# topic - show rand topic

