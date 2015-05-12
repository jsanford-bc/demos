import boto
from boto.s3.key import Key
from boto.exception import S3ResponseError
import fcntl
import sys
import errno
import os
import base64
import json
import requests
import time
import xml.etree.ElementTree as ET

# configuration parameters
LOCK_FILE_NAME = './s3_lock'
INPUT_BUCKET_NAME = 'bc-jsanford-di'
EMAIL_NOTIFICATION_FROM = 's3watchprocess@customer.com'
AWS_PROFILE_NAME = 'bc'

# API configuration parameters
OAUTH_BASE = 'https://oauth.brightcove.com'
OAUTH_PATH = '/v3/access_token'
CMS_BASE = 'https://cms.api.brightcove.com'
DI_BASE = 'https://ingest.api.brightcove.com'

# constants for manifest parsing
EMAIL_XML_PATH = 'Email'
ASSET_XML_PATH = 'Asset'
FILE_NAME_XML_PATH = 'FileName'
CLIENT_ID_XML_PATH = 'Credentials/ClientID'
CLIENT_SECRET_XML_PATH = 'Credentials/ClientSecret'
ACCOUNT_ID_XML_PATH = 'Credentials/AccountID'
VIDEO_TITLE_XML_PATH = 'VideoCloudAsset/Title'
VIDEO_DESCRIPTION_XML_PATH = 'VideoCloudAsset/ShortDescription'
VIDEO_REFERENCE_ID_XML_PATH = 'VideoCloudAsset/ReferenceID'
PROFILE_XML_PATH = 'Profile'
NOTIFICATION_ENDPOINT_XML_PATH = 'NotificationEndpoint'

# returns the correct DI URL
def get_di_url(video_id, account_id):
	return DI_BASE + '/v1/accounts/' + account_id + '/videos/' + video_id + '/ingest-requests'

# returns the correct CMS URL
def get_cms_url(account_id, video_id=None):
	url = CMS_BASE + '/v1/accounts/' + account_id + '/videos'
	if (video_id == None):
		return url
	else:
		return (url + '/' + video_id)

# retrieves an auth token via OAuth API - returns None if no token available
def get_auth_token(client_id, client_secret):
	auth_string = base64.encodestring('%s:%s' % (client_id, client_secret)).replace('\n', '')
	headers_map = {
		'Content-Type': 'application/x-www-form-urlencoded',
		'Authorization': 'Basic ' + auth_string
	};  
	params_map = {
		'grant_type': 'client_credentials'
	}

	req = requests.post(OAUTH_BASE + OAUTH_PATH, 
						params = params_map, 
						headers = headers_map)

	if (req.status_code == 200 or req.status_code == 201):
		return req.json()['access_token']
	else:
		return None

# using the CMS API, creates a video asset (retries as long as retry = True)
# returns the ID if successful, None if unsuccessful
def create_video(asset, retry):
	# prepare the video
	video_data = {}
	video_data['name'] = asset['video_title']
	
	token = get_auth_token(asset['client_id'], asset['client_secret'])
	if (token == None):
		return None

	headers_map = {
		'Authorization': 'Bearer ' + token,
		'Content-Type': 'application/json'
	}

	req = requests.post(get_cms_url(asset['account_id']),
						data = json.dumps(video_data),
						headers = headers_map)

	if (req.status_code == 200 or req.status_code == 201):
		return req.json()['id']
	else:
		if (retry):
			return create_video(asset, False)
		else:
			return None

# using DI, ingests a video to the ID
# returns the ingest ID if successful, None if unsuccessful
def ingest_video(asset, retry):
	ingest_data = {
		'profile' : asset['profile']
	}
	if (asset['notification_endpoint'] != ''):
		ingest_data['callbacks'] = [asset['notification_endpoint']]
	ingest_data['master'] = {'url': 's3://' + INPUT_BUCKET_NAME + '/' + asset['file']}
	
	token = get_auth_token(asset['client_id'], asset['client_secret'])
	if (token == None):
		return None

	headers_map = {
		'Authorization': 'Bearer ' + token,
		'Content-Type': 'application/json'
	}

	req = requests.post(get_di_url(asset['video_id'], asset['account_id']),
		data = json.dumps(ingest_data),
		headers = headers_map)

	if (req.status_code == 200 or req.status_code == 201):
		return req.json()['id']
	else:
		if retry:
			return ingest_video(asset, False)
		else:
			return None

# using DI, update the video if needed
# returns the video ID again if successful, None otherwise
def update_video(asset):
	# prepare the video
	video_data = {}
	video_data['name'] = asset['video_title']
	if (asset['video_description'] != ''):
		video_data['description'] = asset['video_description']
	if (asset['video_reference_id'] != ''):
		video_data['reference_id'] = asset['video_reference_id']

	token = get_auth_token(asset['client_id'], asset['client_secret'])
	if (token == None):
		return None

	headers_map = {
		'Authorization': 'Bearer ' + token,
		'Content-Type': 'application/json'
	}

	req = requests.patch(get_cms_url(asset['account_id'], asset['video_id']),
		data = json.dumps(video_data),
		headers = headers_map)

	if (req.status_code == 200):
		return req.json()['id']
	else:
		return None

# tries to lock a lock file, so that only one process can run at a time
def check_lock():
	# who knows why, but had to open the file in this odd way
	lock = os.open(LOCK_FILE_NAME, os.O_CREAT | os.O_TRUNC | os.O_WRONLY)
	try:
		fcntl.lockf(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
	except IOError, e:
		if e.errno == errno.EAGAIN:
			sys.stderr.write('[%s] Already processing a job, exiting.\n' % time.strftime('%c'))
			sys.exit(-1)

# checks to make sure the file is *.xml
def is_manifest(filename):
	return filename.endswith('.xml')

# general purpose method to send an email
def send_email(subject, from_addr, to_addr, message):
	if (to_addr == ''):
		sys.stderr.write('No email address to send email to...')
	else:
		import smtplib
		from email.mime.text import MIMEText
		msg = MIMEText(message)
		msg['Subject'] = subject
		msg['From'] = from_addr
		msg['To'] = to_addr
		smtpObj = smtplib.SMTP('localhost')
		smtpObj.sendmail(from_addr, to_addr, msg.as_string())

# clear out any None values, and make sure we have the required info
def validate_asset(asset_obj):
	for key in asset_obj.keys():
		if asset_obj[key] == None:
			asset_obj[key] = ''

	# make sure we have all that we need
	if (asset_obj['file'] == '' or 
	  	asset_obj['client_id'] == '' or 
	  	asset_obj['client_secret'] == '' or
	  	asset_obj['account_id'] == '' or
	  	asset_obj['profile'] == ''):
		return False

	# make sure things are as they should be
	if asset_obj['video_title'] == '':
		asset_obj['video_title'] = asset_obj['file']
	if asset_obj['video_description'] == '':
		asset_obj['video_description'] = asset_obj['video_title']
	return True

# parses a given manifest, and ingests the videos mentioned in the manifest
def parse_manifest(manifest_name, manifest_string):
	root = ET.fromstring(manifest_string)
	# try to find the notification email
	try:
		notification_email_address = root.find(EMAIL_XML_PATH).text
	except AttributeError, e:
		notification_email_address = ''

	# go through each and every asset
	for asset in root.findall(ASSET_XML_PATH):
		# parse out all of the information
		try:
			file_name = asset.find(FILE_NAME_XML_PATH).text
		except AttributeError, e:
			file_name = ''
		try:
			client_id = asset.find(CLIENT_ID_XML_PATH).text
		except AttributeError, e:
			client_id = ''
		try:
			client_secret = asset.find(CLIENT_SECRET_XML_PATH).text
		except AttributeError, e:
			client_secret = ''
		try:
			account_id = asset.find(ACCOUNT_ID_XML_PATH).text
		except AttributeError, e:
			account_id = ''
		try:
			video_title = asset.find(VIDEO_TITLE_XML_PATH).text
		except AttributeError, e:
			video_title = ''
		try:
			video_description = asset.find(VIDEO_DESCRIPTION_XML_PATH).text
		except AttributeError, e:
			video_description = ''
		try:
			video_reference_id = asset.find(VIDEO_REFERENCE_ID_XML_PATH).text
		except AttributeError, e:
			video_reference_id = ''
		try:
			profile = asset.find(PROFILE_XML_PATH).text
		except AttributeError, e:
			profile = ''
		try:
			notification_endpoint = asset.find(NOTIFICATION_ENDPOINT_XML_PATH).text
		except AttributeError, e:
			notification_endpoint = ''

		# here's our object to pass on
		asset_obj = {'file': file_name,
					 'client_id': client_id,
					 'client_secret': client_secret,
					 'account_id': account_id,
					 'video_title': video_title,
					 'video_description': video_description,
					 'video_reference_id': video_reference_id,
					 'profile': profile,
					 'notification_endpoint': notification_endpoint,
					 'notification_email_address': notification_email_address}
		
		# validate asset information, and clean it up
		if validate_asset(asset_obj):
			ingest_asset(asset_obj, manifest_name, manifest_string)
		
		# otherwise, log it out in email
		else:
			send_email('S3 Watch - Invalid Asset Found',
					   EMAIL_NOTIFICATION_FROM,
					   notification_email_address,
					   'Invalid asset found - file, client_id, client_secret, account_id, ' + 
					   'and profile are all reqired\n\n' + str(asset_obj) + '\n\n Manifest: ' +
					   manifest_name + '\n\n' + manifest_string)

# ingests a single asset
# input - asset object with all information
def ingest_asset(asset, manifest_name, manifest_string):
	# step 1 - create video
	video_id = create_video(asset, True)
	if (video_id == None):
		send_email('S3 Watch - Error creating video',
			EMAIL_NOTIFICATION_FROM,
			asset['notification_email_address'],
			'Error creating video for asset:\n\n' + str(asset) + '\n\n Manifest: ' + 
			manifest_name + '\n\n' + manifest_string)
	else:
		# step 2 - issue ingest request
		asset['video_id'] = video_id
		ingest_request_id = ingest_video(asset, True)
		if (ingest_request_id == None):
			send_email('S3 Watch - Error ingesting video',
				EMAIL_NOTIFICATION_FROM,
				asset['notification_email_address'],
				'Error issuing ingest request for video:\n\n' + str(asset) + '\n\n Manifest: ' + 
				manifest_name + '\n\n' + manifest_string)
		else:
			# step 3 - update the video for short description and ref ID
			asset['ingest_request_id'] = ingest_request_id
			updated_video_id = update_video(asset)
			if (updated_video_id == None):
				send_email('S3 Watch - Warning - problem updating video',
					EMAIL_NOTIFICATION_FROM,
					asset['notification_email_address'],
					'Error updating the video for asset - Video will still process:\n\n' + 
					str(asset) + '\n\n Manifest: ' + manifest_name + '\n\n' + manifest_string)
			else:
				send_email('S3 Watch - Success!',
					EMAIL_NOTIFICATION_FROM,
					asset['notification_email_address'],
					'Successfully completed ingest request for asset:\n\n' + str(asset))

def run():
	# Try to lock the file so we're the only one
	check_lock()
	# check S3 to see if we have something
	s3_conn = boto.connect_s3(profile_name=AWS_PROFILE_NAME)
	input_bucket = s3_conn.get_bucket(INPUT_BUCKET_NAME)
	keys = input_bucket.list()
	for key in keys:
		if is_manifest(key.name):
			parse_manifest(key.name, key.get_contents_as_string())
			# clean up the manifest
			key.delete()
		# else: ignore the file

if __name__ == "__main__":  
  run();