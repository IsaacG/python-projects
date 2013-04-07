#! /usr/bin/python

import importlib
import os
import re
import socket
import sys

class Server:
	"""IRC Server Object. Connects to a server and does the IO"""
	
# ------------------------------------------
# Basic functionality
# ------------------------------------------

	def __init__ ( self, server = 'localhost' , port = 6667, nick = 'your_nick' ):
		self.server = server
		self.port = port
		self.timeout = 600
		self.nick = nick
		self.callbacks = {}
		self._nickMask = re.compile ( '.+!.+@.+' )

		# This one hook is integral to the workings of IRC so it's seperate
		self.addHook ( 'PING', 'PING', ( lambda s, d: s.send ( 'PONG ' + d['Server'] ) ) )

	def connect ( self ):
		"""Connect to the IRC network and do the handshake then start spin reading input"""
		conn = socket.create_connection ( ( self.server, self.port ), self.timeout )
		self.conn = conn

		self.send ( 'NICK ' + self.nick )
		self.send ( 'USER {} * 0 :{}'.format( self.nick, self.nick ) )
		self.readNetworkLoop ( )

	def parseLine ( self, line ):
		"""The IRC input parser; turn a raw IRC line into a dict of data"""

		def parseUser ( fullMask ):
			"""Split the user mask into components"""
			if self._nickMask.match ( fullMask ):
				nick, mask = fullMask.split ( '!', 1 )
				if mask[0] == '~':
					isIdentified = True
					mask = mask.lstrip( "~" )
				else:
					isIdentified = False
				ident, host = mask.split ( "@", 1 )
				return { 'Nick': nick, 'Identified': isIdentified, 'Ident': ident, 'Host': host }
			else:
				return { 'Nick': fullMask, 'Identified': False, 'Ident': "", 'Host': "" }

		line = line.lstrip ( ":" )

		# Split on " :" with the part after being an optional message component
		lineParts = line.split ( " :", 1 )
		# The part before the split has info about the input
		parts = lineParts[0].split ( )
		if len ( lineParts ) == 2:
			message = lineParts[1]
		else:
			message = ""

		# If unsure, use the second part as the message type
		if len ( parts ) > 1:
			mType = parts[1]
		else:
			mType = ""
		data = { 'Type': mType }

		# The dictionary is different for every message type
		if parts[0] == 'PING':
			data = { 'Type': 'PING', 'Server': message }

		# PRIVMSG is used for a lot of things; this gets a lot of parsing and details in the data structure
		elif parts[1] == 'PRIVMSG':

			# PRIVMSG sent to a channel is a public message; otherwise it is a private message
			if parts[2][0] == "#":
				mType = "PUBMSG"
				data['Channel'] = parts[2]
			else:
				mType = "PRIVMSG"

			# PRIVMSG with the message wrapped in \x01 is a CTCP message
			if message[0] == '\x01' and message[-1] == '\x01':
				message = message.lstrip ( '\x01' )
				message = message.rstrip ( '\x01' )
				data['CTCP'] = True
				# CTCP messages got a CTCP command
				ctcp = message.split( maxsplit = 1 )
				data['CTCP Command'] = ctcp[0]
				message = message.lstrip ( data['CTCP Command'] )
				message = message.lstrip ( " " )

				# CTCP ACTION commands get treated specially since they are common
				if data['CTCP Command'] == 'ACTION':
					data['Action'] = True
				else:
					data['Action'] = False
			else:
				data['CTCP'] = False
				data['Action'] = False

			data['User'] = parseUser ( parts[0] )
			data['Type'] = mType
			data['Message'] = message

		elif parts[1] == 'NOTICE':
			data['User'] = parseUser( parts[0] )
			data['Message'] = message

		elif parts[1] == 'JOIN':
			data['User'] = parseUser( parts[0] )
			data['Channel'] = message

		elif parts[1] == 'PART':
			data['User'] = parseUser( parts[0] )
			data['Channel'] = parts[2]
			data['Message'] = message
		
		return data

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
					out = "< " + line
					print ( out.encode('ascii', 'replace') )

					data = self.parseLine ( line )

					self.dispatch ( data )

				else:
					leftover = line

# ------------------------------------------
# IRC wrappers and helpers
# ------------------------------------------

	def act ( self, destination, message ):
		"""Do an action"""
		self.ctcp ( destination, 'ACTION', message )

	def ctcp ( self, destination, command, message = None):
		"""Send a CTCP command"""
		command = command.upper()
		if message == None:
			self.send ( 'PRIVMSG {} :\x01{}\x01'.format( destination, command ) )
		else:
			self.send ( 'PRIVMSG {} :\x01{} {}\x01'.format( destination, command, message ) )

	def join ( self, channel ):
		"""Join a channel"""
		self.send ( 'JOIN :' + channel )

	def msg ( self, destination, message ):
		"""Send a PRIVMSG"""
		self.send ( 'PRIVMSG {} :{}'.format( destination, message ) )
	
	def send ( self, line ):
		"""Wrapper to send raw text"""
		if not self.conn:
			raise Exception ( 'Not connected to a server' )
			return
		print ( "> " + line )
		line = line + '\r\n'
		self.conn.sendall ( line.encode() )

# ------------------------------------------
# Extentability
# ------------------------------------------
	
	def addBasicCommands ( self ):
		# Define some basic commands to give the bot some behaviour
		def sayCommand ( server, data ):
			parts = data['Message'].split( maxsplit = 2 )
			if len ( parts ) == 3 and parts[0] == "say":
				server.msg ( parts[1], parts[2] )
			elif len ( parts ) == 3 and parts[0] == "act":
				server.act ( parts[1], parts[2] )

		def loadCommand ( server, data ):
			parts = data['Message'].split()
			if len ( parts ) == 2 and parts[0] == "load":
				server.load ( parts[1] )
			elif len ( parts ) == 2 and parts[0] == "unload":
				server.unload ( parts[1] )

		def joinCommand ( server, data ):
			parts = data['Message'].split()
			if len ( parts ) == 2 and parts[0] == "join" and (parts[1])[0] == "#":
				server.join ( parts[1] )

		def quitCommand ( server, data ):
			if data['Message'] == 'quiT':
				sys.exit()

		# Associate commands with event types
		self.addHook ( 'Join', 'PRIVMSG', joinCommand )
		self.addHook ( 'Say', 'PRIVMSG', sayCommand )
		self.addHook ( 'Load', 'PRIVMSG', loadCommand )
		self.addHook ( 'Quit', 'PRIVMSG', quitCommand )

	def addHook ( self, cName, cType, cCode ):
		"""Set up a callback hook to specific code on a specific type of message"""
		if not cType in self.callbacks:
			self.callbacks[ cType ] = {}
		self.callbacks[ cType ][ cName ] = cCode

	def delHook ( self, name ):
		for cType in self.callbacks:
			if name in self.callbacks[ cType ]:
				del ( self.callbacks[ cType ][ name ] )

	def dispatch ( self, data ):
		"""Send the data to a user defined function to act upon it"""
		mType = data['Type']
		if mType in self.callbacks:
			names = [ x for x in self.callbacks[ mType ].keys() ]
			for name in names:
				try:
					self.callbacks[ mType ][ name ]( self, data )
				except Exception as e:
					print ( "W Callback fail for Type [{}] Module [{}]; {}".format ( mType, name, e ) )
					print ( "I Now unloading module [{}]".format ( name ) )
					self.unload ( name )

	def load ( self, name ):
		if name in sys.modules:
			print ( "I " + name + " already loaded. Unloading it first." )
			self.unload ( name )

		try:
			module = importlib.import_module ( name )
		except ImportError as e:
			print( "W " + "Failed to load module {}: {} ".format( name, e.msg ) )
			return

		try:
			for cType in module.types:
				self.addHook ( module.name, cType, module.hookCode )
		except AttributeError as e:
			self.unload ( module.name )
			print ( "W " + "Failed to load {} because it is missing values: {}".format( name, e ) )

		print ( "I " + "Loaded module {} with {} hook(s) [{}]".format ( name, len ( module.types ), ", ".join ( module.types ) ) )

	def unload ( self, name ):
		if name in sys.modules:
			del ( sys.modules[name] )
		self.delHook ( name )


def main ():
	"""Run the IRC bot"""
	# Create a Server object
	if len ( sys.argv ) == 4:
		local = Server ( sys.argv[1], int ( sys.argv[2] ), sys.argv[3] )
	else:
		local = Server ( 'localhost', 6668, 'bot' )

	local.addBasicCommands()

	# Start running
	local.connect ()

if __name__ == "__main__":
	main ()

