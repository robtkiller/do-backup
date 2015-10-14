#!/usr/bin/env python

import sys
import os
import digitalocean
from operator import attrgetter
import time
import logging
import datetime as dt
import paramiko
import ConfigParser

os.chdir(os.path.dirname(sys.argv[0]))

'''Load Configs'''
config = ConfigParser.RawConfigParser()
config.read('do_backup.config')

loglevel = logging.getLevelName(config.get('settings','loglevel'))
host = config.get('security','host')
user = config.get('security','username')
port = config.get('security','port')
ignore= config.get('settings','ignore')
my_token = config.get('security','token')
snapshot_name = config.get('settings','snapshot_name')

logging.basicConfig(
		format = '%(asctime)s %(levelname)s:%(message)s',
		datefmt = '%m/%d/%Y %I:%M:%S %p',
		filename = 'do_backup.log',
		level = loglevel
		)

try:
	logging.info('Connecting to Remote Server')
	ssh = paramiko.SSHClient()
	ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
	ssh.load_system_host_keys()
	ssh.connect(host, username=user, port=int(port))

except Exception as e:
	logging.error('Could not connect to server: ', e)

logging.info('Shutting down server')
ssh.exec_command("shutdown now")
ssh.close()

'''wait for server to shutdown'''
time.sleep(30)

logging.info('Starting Backup Procedure')
manager = digitalocean.Manager(token=my_token)

my_droplets = manager.get_all_droplets()

'''Find debox droplet'''
for droplet in my_droplets:
	if droplet.name == 'devbox':
		devdrop = droplet

'''Take a snapshot of devbox'''
logging.info('Taking Snapshot')
today = dt.datetime.today().strftime("%m-%d-%Y")

count = 0
while count < 6:
	try:
		devdrop.take_snapshot(snapshot_name +'_' +today)
	except Exception as e:
		logging.error('Snapshot failed, trying again:  ' + str(e))
		count += 1	
		if count == 5:
			logging.error('Max Snapshot Retries, Aborting Backing')
			quit()
		continue
	break

'''Wait a few seconds for snapshot to process'''
time.sleep(10)
actions = devdrop.get_actions()
status = max(actions, key=attrgetter('started_at')).status

while status != 'completed':
	logging.debug('Status: ' + str(status))
	if status == 'errored':
		logging.warning('Snapshot Action Error!')
	else:
		time.sleep(10)
		actions = devdrop.get_actions()
		status = max(actions, key=attrgetter('started_at')).status

'''Clean up old snapshot'''
logging.info('Deleting Old Snapshot')
snaps = devdrop.get_snapshots()
devimgs = []
for snap in snaps:
	img = manager.get_image(snap.id)
	if img.name != ignore:
		devimgs.append(img)

oldimg = min(devimgs, key=attrgetter('created_at'))
oldimg.destroy()

logging.info('Backup Procedure Complete')


