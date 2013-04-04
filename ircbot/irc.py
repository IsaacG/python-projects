#! /usr/bin/python

import os
import socket
import logging

class Server:
	"""IRC Server Object. Connects to a server and does the IO"""
	
	def __init__ ( self, server = 'localhost' , port = 6667, nick = 'your_nick' ):
		self.server = server
		self.port = port
		self.timeout = 600
		self.nick = nick
		self.callbacks = []

		self.addHook ( 'PING', ( lambda s, d: s.send ( 'PONG ' + d['Server'] ) ) )

	def connect ( self ):
		"""Connect to the IRC network and do the handshake then start spin reading input"""
		conn = socket.create_connection ( ( self.server, self.port ), self.timeout )
		self.conn = conn

		self.send ( 'NICK ' + self.nick )
		self.send ( 'USER {} * 0 :{}'.format( self.nick, self.nick ) )
		self.readNetworkLoop()
	
	def send ( self, line ):
		"""Wrapper to send raw text"""
		if not self.conn:
			raise Exception ( 'Not connected to a server' )
			return
		line = line + '\r\n'
		self.conn.sendall ( line.encode() )

	def dMsg ( self, destination, message ):
		"""Send a PRIVMSG"""
		self.send ( 'PRIVMSG {} :{}'.format( destination, message ) )
	
	def dJoin ( self, channel ):
		"""Join a channel"""
		self.send ( 'JOIN :' + channel )

	def parseLine ( self, line ):
		"""The IRC input parser; turn a raw IRC line into a dict of data"""

		def parseUser ( fullMask ):
			"""Split the user mask into components"""
			nick, mask = fullMask.split ( '!', 1 )
			if mask[0] == '~':
				isIdentified = True
				mask = mask.lstrip( "~" )
			else:
				isIdentified = False
			ident, host = mask.split ( "@", 1 )
			return { 'Nick': nick, 'Identified': isIdentified, 'Ident': ident, 'Host': host }

		line = line.lstrip ( ":" )
		mComponents = line.split ( maxsplit = 3 )
		mType = mComponents[1]
		data = { 'Type': mType }

		# The dictionary is different for every message type
		if mComponents[0] == 'PING':
			data = { 'Type': 'PING', 'Server': mComponents[1] }

		elif mComponents[1] == 'PRIVMSG':

			user = parseUser ( mComponents[0] )
			mComponents[3] = mComponents[3].lstrip ( ":" )

			if mComponents[2][0] == "#":
				mType = "PUBMSG"
			else:
				mType = "PRIVMSG"
			data = { 'Type': mType, 'Channel': mComponents[2], 'Message': mComponents[3], 'User': user }

		elif mComponents[1] == 'JOIN':
			data = { 'Type': 'JOIN', 'Channel': mComponents[2].lstrip( ":" ), 'User': parseUser( mComponents[0] ) }

		elif mComponents[1] == 'PART':
			data = { 'Type': 'PART', 'Channel': mComponents[2].lstrip( ":" ), 'User': parseUser( mComponents[0] ), 'Message': mComponents[3].lstrip( ":" ) }
		
		return data

	def dispatch ( self, data ):
		"""Send the data to a user defined function to act upon it"""
		[ callback['code']( self, data ) for callback in self.callbacks if callback['type'] == data['Type'] ]

	def addHook ( self, cType, cCode ):
		"""Set up a callback hook to specific code on a specific type of message"""
		self.callbacks.append( { 'type': cType, 'code': cCode } )

	def readNetworkLoop ( self ):
		"""The network read-and-dispatch loop"""

		# Sometimes messages are cut off mid-line by read(); store the leftover
		leftover = ''
		self.conn.settimeout( 1.0 )

		while True:
			# Try reading data
			try:
				networkIn = self.conn.recv ( 1024 ).decode()
			except socket.timeout as timeout:
				continue
			
			# Data may contain many lines; each line is processed seperately
			for line in networkIn.splitlines( True ):

				if line[-2:] == '\r\n':
					# strip trailing newlines, prepend leftover line, and dispatch the event
					line = line.rstrip( '\r\n' )
					line = leftover + line
					leftover = ''
					data = self.parseLine ( line )

					print ( line )
					self.dispatch ( data )

				else:
					leftover = line

def main ():
	"""Run the IRC bot"""
	logging.basicConfig( level = logging.DEBUG )

	# Create a Server object
	local = Server ( 'localhost', 6668, 'mypybot' )

	# Define some commands to give the bot some behaviour
	def sayCommand ( server, data ):
		parts = data['Message'].split( maxsplit = 2 )
		if len ( parts ) == 3 and parts[0] == "say":
			server.dMsg( parts[1], parts[2] )

	def joinCommand ( server, data ):
		parts = data['Message'].split()
		if len ( parts ) == 2 and parts[0] == "join" and (parts[1])[0] == "#":
			server.dJoin ( parts[1] )

	def greetOnJoin ( server, data ):
		server.dMsg ( data['Channel'], "Hello " + data['User']['Nick'] )

	# Associate commands with event types
	local.addHook ( 'PRIVMSG', joinCommand )
	local.addHook ( 'PRIVMSG', sayCommand )
	local.addHook ( 'JOIN', greetOnJoin )

	# Start running
	local.connect ()

if __name__ == "__main__":
	main ()

