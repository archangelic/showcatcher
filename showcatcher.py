#!/usr/bin/python
import requests, os, feedparser, sys, subprocess, shlex, validate
import os.path as path
from datetime import datetime
from feedparser import parse
from urllib2 import urlopen
from urllib import urlretrieve
from bs4 import BeautifulSoup as soup
from configobj import ConfigObj as configobj

args = sys.argv

appPath = path.dirname(path.abspath(__file__))
if appPath == '':
	appPath = "."
dataPath = path.join(appPath, '.showcatcher')
	
keys = {
	'archive' : path.join(dataPath, 'archive'),
	'cache' : path.join(dataPath, 'cache'),
	'feeds' : path.join(dataPath, 'feeds'),
	'log' : path.join(dataPath, 'showcatcher.log')}

if path.isdir(dataPath) == False:
	os.mkdir(dataPath)

if path.isdir(keys['cache']) == False:
	os.mkdir(keys['cache'])
	
if path.isdir(keys['archive']) == False:
	os.mkdir(keys['archive'])
	
if path.isfile(keys['feeds']) == False:
	open(keys['feeds'], 'a').close()
	
class Feeder():
	def __init__(self, keys):
		self.archive = keys['archive']
		self.cache = keys['cache']
		self.feedfile = keys['feeds']
		self.log = keys['log']
		self.arcdict = {}
		self.cachedict = {}
		self.arclist = os.listdir(self.archive)
		self.cachelist = os.listdir(self.cache)
		self.cachelist.sort()
		for self.i in self.arclist:
			self.arcdict[self.i] = '1'
		for self.i in self.cachelist:
			self.cachedict[self.i] = '1'
				
	def write(self):
		self.feeds = []
		self.entries = []
		self.count = {'arc' : 0, 'cache' : 0, 'write' : 0}
		with open(self.feedfile, 'r') as self.myfile:
			self.feeddata = self.myfile.read().split('\n')
		for self.i in self.feeddata:
			if (self.i != '')&(self.i.startswith('#') == False):
				self.feeds.append(self.i)
		if self.feeds == []:
			self.logger("[ERROR] No feeds found in feeds file! Use '-f' or '--add-feed' options to add episode feeds")
			return 0
		for self.i in self.feeds:
			self.feeddat = parse(self.i)
			for self.i in self.feeddat.entries:
				self.entries.append(self.i)
		for self.i in self.entries:
			self.title = self.i['title'].replace(' ', '.')
			self.link = self.i['link']
			try:
				if self.arcdict[self.title]:
					self.count['arc'] += 1
			except:
				try:
					if self.cachedict[self.title]:
						self.count['cache'] += 1
				except:
					with open(path.join(self.cache, self.title), 'w') as self.myfile:
						self.myfile.write(self.link)
					self.count['write'] += 1
					self.logger('[QUEUED] ' + self.title + ' was added to queue')
		self.total = self.count['arc'] + self.count['cache'] + self.count['write']
		if (self.total) != 0:
			self.logger('[QUEUE COMPLETE] New Episodes: ' + str(self.count['write']))
			self.logger('[QUEUE COMPLETE] Already Queued: ' + str(self.count['cache']))
			self.logger('[QUEUE COMPLETE] Already Archived: ' + str(self.count['arc']))
		else:
			self.logger('[ERROR] No feed information found. Something is probably wrong.')
						
	def move(self, title):
		self.title = title
		os.rename(path.join(self.cache, self.title), path.join(self.archive, self.title))
		self.logger('[ARCHIVED] ' + self.title + ' was moved to archive.')
		
	def lister(self):
		if self.cachelist != []:
			self.cachelist.sort()
			print 'Episodes queued for download:'
			for self.each in self.cachelist:
				print self.each
		else:
			print 'No episodes queued for download.'
			
	def logger(self, message):
		self.message = message
		print self.message
		with open(self.log, 'a') as self.myfile:
			self.myfile.write(str(datetime.now().strftime('[%a %m/%d/%y %H:%M:%S]')) + self.message + '\n')

myFeeder = Feeder(keys)

def configreader():
	configfile = path.join(dataPath, 'config')
	cfg = """hostname = string(default='localhost')
		port = string(default='9091')
		require_auth = boolean(default=False)
		username = string(default='')
		password = string(default='')
		download_directory = string(default='')"""
	spec = cfg.split("\n")
	config = configobj(configfile, configspec=spec)
	validator = validate.Validator()
	config.validate(validator, copy=True)
	config.filename = configfile
	config.write()
	return config

def transmission(title, host, port, auth, authopt, downdir):
	myFeeder.logger('[TRANSMISSION] Starting download for ' + title)
	with open(path.join(cache, title), 'r') as myfile:
		url = myfile.read()
	if auth == False:
		command = 'transmission-remote ' + host + ':' + port + ' -a "' + url + '"'
	else:
		command = 'transmission-remote  ' + host + ':' + port + ' -a "' + url + '" -n ' + authopt
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

def addfeed(url):
	with open(keys['feeds'], 'a') as myfile:
		myfile.write(url + '\n')
	myFeeder.logger('[FEEDS] Feed ' + url + ' added successfully.')

def printhelp():
	options = [
		'                                                                                ',
		'Available options for Showcatcher:',
		' -a   --archive                            Moves all currently queued episodes',
		'                                           to the archive',
		' -d   --download                           Sends all queued episodes to Trans-',
		'                                           mission',
		' -f   --add-feed               <url>       Appends the given URL to the list of',
		'                                           feeds',
		' -h   --help                               Displays this help page',
		' -l   --list                               Lists all queued episodes',
		' -L   --log                                Shows log from most recent full run',
		' -q   --queue                              Checks all feeds for new episodes to',
		'                                           add to the queue. DOES NOT SEND TO ',
		'                                           TRANSMISSION.']
	for each in options:
		print each
	
def logreader():
	logcmd = "sed -n '/\[SHOWCATCHER\]/=' " + keys['log']
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
	
if __name__ == '__main__':
	cache = keys['cache']
	cachelist = os.listdir(cache)
	cachelist.sort()
	config = configreader()
	host = config['hostname']
	port = config['port']
	auth = config['require_auth']
	authopt = config['username'] + ':' + config['password']
	downdir = config['download_directory']
	try:
		if (args[1] == '-a') | (args[1] == '--archive'):
			myFeeder.logger('[ARCHIVE ONLY] Moving all episodes in queue to the archive')
			if cachelist == []:
				myFeeder.logger('[ARCHIVE COMPLETE] No episodes to archive')
			else:
				for each in cachelist:
					myFeeder.move(each)
				myFeeder.logger('[ARCHIVE COMPLETE] All episodes archived successfully')		
		elif (args[1] == '-d') | (args[1] == '--download'):
			myFeeder.logger('[DOWNLOAD ONLY] Starting download of already queued episodes')
			if cachelist == []:
				myFeeder.logger('[DOWNLOAD COMPLETE] No episodes to download')
			else:
				errors = 0
				for each in cachelist:
					test = transmission(each, host, port, auth, authopt, downdir)
					errors += test
				if errors > 0:
					myFeeder.logger('[DOWNLOAD COMPLETE] There were errors adding episodes to Transmission')
				else:
					myFeeder.logger('[DOWNLOAD COMPLETE] Initiated all downloads successfully')
		elif (args[1] == '-f') | (args[1] == '--add-feed'):
			try:
				addfeed(args[2])
			except:
				print "Please enter the feed url with the '" + args[1] + "' option."
		elif (args[1] == '-h') | (args[1] == '--help'):
			printhelp()				
		elif (args[1] == '-l') | (args[1] == '--list'):
			myFeeder.lister()
		elif (args[1] == '-L') | (args[1] == '--log'):
			logreader()
		elif (args[1] == '-q') | (args[0] == '--queue'):
			myFeeder.logger('[QUEUE ONLY] Checking feeds for new episodes to queue')
			myFeeder.write()
		else:
			print "Invalid option '" + args[1] + "'"
			print "Try using '-h' or '--help' for a list of valid options"
	except:
		myFeeder.logger('[SHOWCATCHER] Starting Showcatcher')
		myFeeder.write()
		cachelist = os.listdir(cache)
		cachelist.sort()
		if cachelist == []:
			myFeeder.logger('[SHOWCATCHER COMPLETE] No episodes to download')
		else:
			errors = 0
			for each in cachelist:
				test = transmission(each, host, port, auth, authopt, downdir)
				errors += test
			if errors > 0:
				myFeeder.logger('[SHOWCATCHER COMPLETE] There were errors adding episodes to Transmission')
			else:
				myFeeder.logger('[SHOWCATCHER COMPLETE] Initiated all downloads successfully')
