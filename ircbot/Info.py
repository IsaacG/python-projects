#! /usr/bin/python

import os
import psutil
import time

def hookCode ( server, data ):
	if not data['CTCP']:
		return
	if data['CTCP Command'] != 'INFO':
		return

	p = psutil.Process(os.getpid())
	info = []
	info.append ( "PID [{}] PPID [{}]".format ( p.pid, p.ppid ) )
	info.append ( "Name [{}] cmd [{}] ran by [{}]".format ( p.name, p.cmdline, p.username ) )
	info.append ( "Running since {}".format ( time.strftime ( "%Y-%m-%d %H:%M:%S", time.localtime ( p.create_time ) ) ) )
	( rss, vm ) = p.get_memory_info()
	info.append ( "Memory: RSS {} VM {}".format ( rss, vm ) )

	for line in info:
		server.msg ( data['User']['Nick'], line )

name = 'Info'

types = [ 'PRIVMSG' ]
