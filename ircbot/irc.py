#! /usr/bin/python

import importlib
import os
import re
import socket
import sys
import time

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
		self.callbackData = {}
		self._nickMask = re.compile ( '.+!.+@.+' )
		self.lastSend = 0
		self.flowSpeed = 0.2
		self.channels = {}

		# This one hook is integral to the workings of IRC so it's seperate
		self.addHook ( 'PING', 'PING', ( lambda s, d, n: s.send ( 'PONG ' + d['Server'] ) ) )

	def connect ( self ):
		"""Connect to the IRC network and do the handshake then start spin reading input"""
		conn = socket.create_connection ( ( self.server, self.port ), self.timeout )
		self.conn = conn

		self.send ( 'NICK ' + self.nick )
		self.send ( 'USER {} * 0 :{}'.format( self.nick, self.nick ) )
		while True:
			try:
				self.readNetworkLoop ( )
			except Exception as e:
				self.conn = socket.create_connection ( ( self.server, self.port ), self.timeout )
			

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
		elif parts[0] == 'ERROR':
			raise Exception ( "IRC Error" )

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
			if len ( parts ) > 2:
				data['Channel'] = parts[2]
			else:
				data['Channel'] = message

		elif parts[1] == 'PART':
			data['User'] = parseUser( parts[0] )
			data['Channel'] = parts[2]
			data['Message'] = message
		
		elif parts[1] == 'QUIT':
			data['User'] = parseUser( parts[0] )
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
					try:
						print ( out.encode('ascii', 'replace') )
					except UnicodeDecodeError as e:
						print ( out.encode() )

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
		self.channels[ channel.lower() ] = 1

	def msg ( self, destination, message ):
		"""Send a PRIVMSG"""
		self.send ( 'PRIVMSG {} :{}'.format( destination, message ) )

	def part ( self, channel ):
		"""Part a channel"""
		self.send ( 'PART :' + channel )
		del ( self.channels[ channel.lower() ] )
	
	def send ( self, line ):
		"""Wrapper to send raw text"""
		if not self.conn:
			raise Exception ( 'Not connected to a server' )
			return

		now = time.time()
		if ( now - self.lastSend ) < self.flowSpeed:
			time.sleep ( self.flowSpeed )

		print ( "> " + line )
		line = line + '\r\n'
		self.lastSend = time.time()
		self.conn.sendall ( line.encode() )

# ------------------------------------------
# Extentability
# ------------------------------------------
	
	def addBasicCommands ( self ):
		# Define some basic commands to give the bot some behaviour
		def joinCommand ( server, data, storage ):
			parts = data['Message'].split()
			if len ( parts ) == 2 and parts[0] == "join" and (parts[1])[0] == "#":
				server.join ( parts[1] )

		def loadCommand ( server, data, storage ):
			parts = data['Message'].split()
			if len ( parts ) == 2 and parts[0] == "load":
				server.load ( parts[1] )
			elif len ( parts ) == 2 and parts[0] == "unload":
				server.unload ( parts[1] )

		def nickCommand ( server, data, storage ):
			parts = data['Message'].split()
			if len ( parts ) == 2 and parts[0] == "nick":
				server.send ( "NICK :{}".format ( parts[1] ) )

		def partCommand ( server, data, storage ):
			parts = data['Message'].split()
			if len ( parts ) == 2 and parts[0] == "part" and (parts[1])[0] == "#":
				server.part ( parts[1] )

		def quitCommand ( server, data, storage ):
			if data['Message'] == 'quiT':
				sys.exit()

		def sayCommand ( server, data, storage ):
			parts = data['Message'].split( maxsplit = 2 )
			if len ( parts ) == 3 and parts[0] == "say":
				server.msg ( parts[1], parts[2] )
			elif len ( parts ) == 3 and parts[0] == "act":
				server.act ( parts[1], parts[2] )

		# Associate commands with event types
		self.addHook ( '_Join', 'PRIVMSG', joinCommand )
		self.addHook ( '_Load', 'PRIVMSG', loadCommand )
		self.addHook ( '_Nick', 'PRIVMSG', nickCommand )
		self.addHook ( '_Part', 'PRIVMSG', partCommand )
		self.addHook ( '_Quit', 'PRIVMSG', quitCommand )
		self.addHook ( '_Say', 'PRIVMSG', sayCommand )

	def addHook ( self, cName, cType, cCode ):
		"""Set up a callback hook to specific code on a specific type of message"""
		if not cType in self.callbacks:
			self.callbacks[ cType ] = {}
		self.callbacks[ cType ][ cName ] = cCode

		# Add data storage for the callback
		if cName not in self.callbackData:
			self.callbackData[ cName ] = {}


	def delHook ( self, name ):
		for cType in self.callbacks:
			if name in self.callbacks[ cType ]:
				del ( self.callbacks[ cType ][ name ] )

	def dispatch ( self, data ):
		"""Send the data to a user defined function to act upon it"""
		mType = data['Type']
		if mType in self.callbacks:
			names = [ x for x in self.callbacks[ mType ] ]
			for name in names:
				try:
					self.callbacks[ mType ][ name ]( self, data, self.callbackData[ name ] )
				except Exception as e:
					print ( "W Callback fail for Type [{}] Module [{}]; {}".format ( mType, name, repr (e ) ) )
					print ( "I Now unloading module [{}]".format ( name ) )
					self.unload ( name )

	def load ( self, name ):
		# Unload the module if it is already loaded
		if name in sys.modules:
			print ( "I " + name + " already loaded. Unloading it first." )
			self.unload ( name )

		# Import the module
		try:
			module = importlib.import_module ( name )
		except ImportError as e:
			print( "W " + "Failed to load module {}: {} ".format( name, e.msg ) )
			return

		# Add callback hooks
		try:
			for cType in module.types:
				self.addHook ( module.name, cType, module.hookCode )
		except AttributeError as e:
			self.unload ( module.name )
			print ( "W " + "Failed to load {} because it is missing values: {}".format( name, e ) )

		print ( "I " + "Loaded module {} with {} hook(s) [{}]".format ( name, len ( module.types ), ", ".join ( module.types ) ) )

		# Run the init code
		try:
			module.init( self, self.callbackData[ name ] )
		except AttributeError as e:
			pass
		except Exception as e:
			print ( "W Init code failed; {}".format ( repr ( e ) ) )
			print ( "I Now unloading module [{}]".format ( name ) )
			self.unload ( name )

	def unload ( self, name ):
		# Don't unload marked (eg core) hooks
		if name[0] == '_':
			return
		if name in sys.modules:
			del ( sys.modules[name] )
		self.delHook ( name )

		if name in self.callbackData:
			del ( self.callbackData[ name ] )


def main ():
	"""Run the IRC bot"""
	# Create a Server object
	if len ( sys.argv ) == 4:
		local = Server ( sys.argv[1], int ( sys.argv[2] ), sys.argv[3] )
	elif len ( sys.argv ) == 2 and sys.argv[1] == "-t":
		local = Server ( 'localhost', 6668, 'bot' )
	else:
		print ( "Usage: " + sys.argv[0] + " host port nick" )
		sys.exit ( 1 )

	local.addBasicCommands()

	# Start running
	local.connect ()

if __name__ == "__main__":
	main ()

