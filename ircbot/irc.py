#! /usr/bin/python

import os
import socket
import logging
import urllib.request

class Server:
	"""IRC Server Object. Connects to a server and does the IO"""
	
	def __init__ ( self, server = 'localhost' , port = 6667, nick = 'your_nick' ):
		self.server = server
		self.port = port
		self.timeout = 600
		self.nick = nick
		self.callbacks = {}

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

		# Split on " :" with the part after being an optional message component
		lineParts = line.split ( " :", 1 )
		# The part before the split has info about the input
		parts = lineParts[0].split ( )
		if len ( lineParts ) == 2:
			message = lineParts[1]

		# If unsure, use the second part as the message type
		mType = parts[1]
		data = { 'Type': mType }

		# The dictionary is different for every message type
		if parts[0] == 'PING':
			data = { 'Type': 'PING', 'Server': message }

		elif parts[1] == 'PRIVMSG':

			if parts[2][0] == "#":
				mType = "PUBMSG"
			else:
				mType = "PRIVMSG"
			data['User'] = parseUser( parts[0] )
			data['Type'] = mType
			data['Channel'] = parts[2]
			data['Message'] = message

		elif parts[1] == 'JOIN':
			data['User'] = parseUser( parts[0] )
			data['Channel'] = message

		elif parts[1] == 'PART':
			data['User'] = parseUser( parts[0] )
			data['Channel'] = parts[2]
			data['Message'] = message
		
		return data

	def dispatch ( self, data ):
		"""Send the data to a user defined function to act upon it"""
		if data['Type'] in self.callbacks:
			for callback in self.callbacks[ data['Type'] ]:
				callback( self, data )

	def addHook ( self, cType, cCode ):
		"""Set up a callback hook to specific code on a specific type of message"""
		if not cType in self.callbacks:
			self.callbacks[cType] = []
		self.callbacks[cType].append( cCode )

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

def getHttpTitle ( url ):
	urllib.request.urlopen(url, timeout = 10 )
	# Fetch the page
	# Check HTTP code
	# Parse the HTML and get a title

if __name__ == "__main__":
	main ()

