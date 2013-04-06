#! /usr/bin/python

import sys
import importlib
import time

#
# I want to test a loader/unloader
# It needs to read load and unload commands
# On load, import a specified module which will contain a function
# On unload, remove the module's function from the list, tagged by name
# On run, run the functions
#

functions = {}

def load( name ):
	importlib.import_module( name )
	functions[ name ] = sys.modules[name].myFunction

def unload( name ):
	del( sys.modules[name] )
	del( functions[ name ] )

def run():
	print( "Starting run" )
	for ( name, func ) in functions.items():
		print( "Now running {}.myFunction".format( name ) )
		func()

def main():
	load( "a" )
	run()
	load( "b" )
	run()
	unload( "a" )
	run()
	print( "Change the a.py code" )
	time.sleep( 5 )
	load( "a" )
	run()
	
if __name__ == "__main__":
	main()
