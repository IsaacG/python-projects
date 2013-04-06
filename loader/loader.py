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
	if name in functions:
		unload ( name )

	try:
		importlib.import_module( name )
	except ImportError as e:
		print( "Failed to load module {}: {} ".format( name, e.msg ) )
		return

	try:
		functions[ name ] = sys.modules[name].myFunction
	except AttributeError as e:
		unload( name )
		print( "Failed to load {} because it is missing values: {}".format( name, e ) )
		repr( e )

def unload( name ):
	if name in sys.modules:
		del( sys.modules[name] )
	if name in functions:
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
	load( "c" )
	run()
	
if __name__ == "__main__":
	main()
