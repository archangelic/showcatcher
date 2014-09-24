#!/usr/bin/python
# Modules from standard Python
import os, subprocess, shlex, sys
import os.path as path
from datetime import datetime
import sqlite3 as lite

# Finds the location of torrentcatcher
appPath = path.dirname(path.abspath(__file__))
if appPath == '':
	appPath = "."
dataPath = path.join(appPath, 'data')

# Imports modules from lib directory
libPath = path.join(appPath, 'lib')
modules = [path.join(libPath, 'validate'), path.join(libPath, 'argparse'), path.join(libPath, 'feedparser'), path.join(libPath, 'configobj'), path.join(libPath, 'tabulate')]
sys.path.append(libPath)
for each in modules:
	sys.path.append(each)
import validate, argparse
from feedparser import parse
from tabulate import tabulate
from configobj import ConfigObj as configobj
	
# Dictionary of values several functions use
keys = {
	'log' : path.join(dataPath, 'torrentcatcher.log'),
	'config' : path.join(dataPath, 'config'),
	'database' : path.join(dataPath, 'torcatch.db')}

if __name__ == '__main__':
	# Creates data directory for config file, database, and log file
	if path.isdir(dataPath) == False:
		os.mkdir(dataPath)
	# Creates database if it does not exist:
	con = lite.connect(keys['database'])
	cur = con.cursor()
	cur.execute('CREATE TABLE IF NOT EXISTS torrents(id INTEGER PRIMARY KEY, name TEXT, url TEXT, source TEXT, downStatus BOOLEAN);')
	con.commit()

class Feeder():
	def __init__(self, keys):
		self.configfile = keys['config']
		self.log = keys['log']
		self.con = lite.connect(keys['database'])
		self.cur = self.con.cursor()
		self.cur.execute("SELECT * FROM torrents WHERE downStatus=0")
		self.cachelist = self.cur.fetchall()
				
	# Function to write entries from the feed to the database
	def write(self):
		entries = []
		count = {'arc' : 0, 'cache' : 0, 'write' : 0}
		config = configobj(self.configfile)
		feeds = config['feeds']
		if feeds == {}:
			self.logger("[ERROR] No feeds found in feeds file! Use '-f' or '--add-feed' options to add torrent feeds")
			return 0
		for i in feeds:
			self.logger('[FEEDS] Reading entries for feed "' + i + '"')
			feeddat = parse(feeds[i])
			entries = feeddat.entries
			feedname = i
			for i in entries:
				title = i['title']
				link = i['link']
				self.cur.execute("SELECT EXISTS(SELECT * FROM torrents WHERE name=?);", (title,))
				test = self.cur.fetchall()
				if test[0][0] != 1:
					self.cur.execute("INSERT INTO torrents(name, url, source, downStatus) VALUES (?, ?, ?, 0);", (title, link, feedname))
					count['write'] += 1
					self.logger('[QUEUED] ' + title + ' was added to queue')
				else:
					self.cur.execute("SELECT * FROM torrents WHERE name=?", (title,))
					status = self.cur.fetchall()
					if status[0][4] == 1:
						count['arc'] += 1
					elif status[0][4] == 0:
						count['cache'] += 1
				self.con.commit()
		total = count['arc'] + count['cache'] + count['write']
		if total != 0:
			self.logger('[QUEUE COMPLETE] New Torrents: ' + str(count['write']))
			self.logger('[QUEUE COMPLETE] Already Queued: ' + str(count['cache']))
			self.logger('[QUEUE COMPLETE] Already Archived: ' + str(count['arc']))
		else:
			self.logger('[ERROR] No feed information found. Something is probably wrong.')
					
	# Function updates given entries to show they have been sent to the Archive
	def move(self, title):
		self.cur.execute("UPDATE torrents SET downStatus=1 WHERE name=?", (title,))
		self.con.commit()
		self.logger('[ARCHIVED] ' + title + ' was moved to archive.')
		
	# Function calls for every entry with downStatus of 0 and lists the ID # and name
	def lister(self):
		if self.cachelist != []:
			print 'Torrents queued for download:'
			for each in self.cachelist:
				print '[ID %s]' % (each[0]), each[1]
		else:
			print 'No torrents queued for download.'
			
	# Homebrewed logging solution. Any passed messages are outputted to the console as well as appended to the log
	def logger(self, message):
		print message
		with open(self.log, 'a') as myfile:
			myfile.write(str(datetime.now().strftime('[%a %m/%d/%y %H:%M:%S]')) + message + '\n')

myFeeder = Feeder(keys)

# Function to parse the config file and return the dictionary of values. Also creates a config file if one does not exist.
def configreader():
	configfile = keys['config']
	cfg = """[transmission]
		hostname = string(default='localhost')
		port = string(default='9091')
		require_auth = boolean(default=False)
		username = string(default='')
		password = string(default='')
		download_directory = string(default='')
		
		[feeds]"""
	spec = cfg.split("\n")
	config = configobj(configfile, configspec=spec)
	validator = validate.Validator()
	config.validate(validator, copy=True)
	config.filename = configfile
	config.write()
	return config

# Function to add files to Transmission over transmission-remote
def transmission(title, url, trconfig):
	host = trconfig['hostname']
	port = trconfig['port']
	auth = trconfig['require_auth']
	authopt = trconfig['username'] + ':' + trconfig['password']
	downdir = trconfig['download_directory']
	myFeeder.logger('[TRANSMISSION] Starting download for ' + title)
	if not auth:
		command = 'transmission-remote ' + host + ':' + port + ' -a "' + url + '"'
	else:
		command = 'transmission-remote  ' + host + ':' + port + ' -n ' + authopt + ' -a "' + url + '"'
	if downdir != '':
		command = command + ' -w ' + downdir
	transcmd = subprocess.Popen(shlex.split(command), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	output,error = transcmd.communicate()
	if error == "":
		myFeeder.move(title)
		myFeeder.logger('[TRANSMISSION] ' + output.strip('\n'))
		return 0
	else:
		myFeeder.logger('[ERROR] ' + error.strip('\n'))
		return 1

# Add Feed utility. Takes the name and URL and appends it to the config file
def addfeed(name, url):
	config = configreader()
	config['feeds'][name] = url
	config.write()
	myFeeder.logger('[FEEDS] Feed "' + name + '" added successfully.')
	
# Parses out the log for the most recent run of torrentcatcher. Shows the entire log since the last time the command sans arguments ran.
def logreader():
	logcmd = "sed -n '/\[TORRENTCATCHER\]/=' " + keys['log']
	logproc = subprocess.Popen(shlex.split(logcmd), stdout=subprocess.PIPE)
	output = logproc.communicate()
	lines = output[0].split('\n')
	linelist = []
	for each in lines:
		if each != '':
			linelist.append(int(each))
	linelist.sort()
	startline = lines[len(linelist)-1]
	logproc = subprocess.Popen(shlex.split('tail -n +' + str(startline) + ' ' + keys['log']), stdout=subprocess.PIPE)
	rawout = logproc.communicate()
	output = rawout[0].split('\n')
	for each in output:
		if each != '':
			print each
			
# Searches the database for a given query
def torsearch(category):
	query = raw_input('Enter query: ')
	resultlist = []
	if category == 'id':
		try:
			qtest = int(query)
			cur.execute("SELECT * FROM torrents WHERE id LIKE ?", (query,))
			results = cur.fetchall()
			if results == []:
				print "No results found in '{0}' for '{1}".format(category, query)
			else:
				for each in results:
					if each[4] == 0:
						status = 'Queue'
					elif each[4] == 1:
						status = 'Archive'
					resultlist.append([each[0], each[1], each[3], status])
				print tabulate(resultlist, ['ID', 'Name', 'Source', 'Status'])
		except:
			print "Please enter a valid ID number for ID searches."
	else:
		lquery = '%' + query + '%'
		cur.execute("SELECT * FROM torrents WHERE ? LIKE ?", (category, lquery))
		results = cur.fetchall()
		if results == []:
			print "No results found in '{0}' for '{1}'".format(category, query)
		else:
			for each in results:
				if each[4] == 0:
					status = 'Queue'
				elif each[4] == 1:
					status = 'Archive'
				resultlist.append([each[0], each[1], each[3], status])
			print tabulate(resultlist, ['ID', 'Name', 'Source', 'Status'])
	
if __name__ == '__main__':
	config = configreader()
	trconfig = config['transmission']
	parser = argparse.ArgumentParser()
	parser.add_argument('-a', '--archive', nargs='+', metavar='all|ID', help="Moves selected torrents to the archive. Using the argument 'all' will move all currently queued torrents to the archive. Use the '--list' option to see IDs.")
	parser.add_argument('-d', '--download', nargs='+', metavar='all|ID', help="Moves selected torrents to Transmission.Using the argument 'all' will move all currently queued torrents to Transmission. Use the '--list' option to see IDs.")
	parser.add_argument('-f', '--add-feed', help="Starts the add feed utility.", action="store_true")
	parser.add_argument('-l', '--list', help="Lists all queued torrents and their IDs.", action="store_true")
	parser.add_argument('-L', '--log', help="Shows log from most recent full run.", action="store_true")
	parser.add_argument('-q', '--queue', help="Checks all feeds for new torrents to add to the queue. DOES NOT SEND TO TRANSMISSION.", action="store_true")
	parser.add_argument('--search', nargs=1, choices=['name', 'source', 'id'], help="Searches archive and queue for given query. Can search by name, source, or ID number.")
	args = parser.parse_args()
	if args.archive != None:
		myFeeder.logger('[ARCHIVE ONLY] Moving selected torrents in queue to the archive')
		if args.archive[0] == 'all':
			cur.execute("SELECT * FROM torrents WHERE downStatus=0")
			cachelist = cur.fetchall()
			if cachelist == []:
				myFeeder.logger('[ARCHIVE COMPLETE] No torrents to archive')
			else: 
				for each in cachelist:
					myFeeder.move(each[1])
				myFeeder.logger('[ARCHIVE COMPLETE] Archive process completed successfully')
		else:
			for each in args.archive:
				if each != 'all':
					cur.execute("SELECT * FROM torrents WHERE id=?", (each,))
					selection = cur.fetchall()
					seltor = selection[0]
					if seltor[4] == 0:
						myFeeder.move(seltor[1])
					elif seltor[4] == 1:
						myFeeder.logger('[ARCHIVE] %s is already in the archive.' % (seltor[1]))
			myFeeder.logger('[ARCHIVE COMPLETE] Archive process completed successfully')
	if args.download != None:
		myFeeder.logger('[DOWNLOAD ONLY] Starting download of already queued torrents')
		if args.download[0] == 'all':
			cur.execute("SELECT * FROM torrents WHERE downStatus=0")
			cachelist = cur.fetchall()
			if cachelist == []:
				myFeeder.logger('[DOWNLOAD COMPLETE] No torrents to download')
			else:
				errors = 0
				for each in cachelist:
					test = transmission(each[1], each[2], trconfig)
					errors += test
				if errors > 0:
					myFeeder.logger('[DOWNLOAD COMPLETE] There were errors adding torrents to Transmission')
				else:
					myFeeder.logger('[DOWNLOAD COMPLETE] Initiated all downloads successfully')
		else:
			errors = 0
			for each in args.archive:
				if each != 'all':
					cur.execute("SELECT * FROM torrents WHERE id=?", (each,))
					selection = cur.fetchall()
					seltor = selction[0]
					test = transmission(seltor[1], seltor[2], trconfig)
					errors +=test
			if errors > 0:
				myFeeder.logger('[DOWNLOAD COMPLETE] There were errors adding torrents to Transmission')
			else:
				myFeeder.logger('[DOWNLOAD COMPLETE] Initiated all downloads successfully')					
	if args.add_feed:
		name = raw_input('Enter name for feed: ')
		url = raw_input('Enter URL for feed: ')
		addfeed(name, url)
	if args.list:
		myFeeder.lister()
	if args.log:
		logreader()
	if args.queue:
		myFeeder.logger('[QUEUE ONLY] Checking feeds for new torrents to queue')
		myFeeder.write()
	if args.search != None:
		torsearch(args.search[0])
	if (args.archive==None) and (args.download==None) and (not args.add_feed) and (not args.list) and (not args.log) and (not args.queue) and (args.search==None):
		myFeeder.logger('[TORRENTCATCHER] Starting Torrentcatcher')
		myFeeder.write()
		cur.execute("SELECT * FROM torrents WHERE downStatus=0")
		cachelist = cur.fetchall()
		if cachelist == []:
			myFeeder.logger('[TORRENTCATCHER COMPLETE] No torrents to download')
		else:
			errors = 0
			for each in cachelist:
				test = transmission(each[1], each[2], trconfig)
				errors += test
			if errors > 0:
				myFeeder.logger('[TORRENTCATCHER COMPLETE] There were errors adding torrents to Transmission')
			else:
				myFeeder.logger('[TORRENTCATCHER COMPLETE] Initiated all downloads successfully')
