import base64, requests, urllib, httplib, urllib3, ssl, json, sys, subprocess, time

####################
# ZENCODER CONFIGS #
####################
ZENCODER_API_KEY = 'ZENCODER_API_KEY'
ZENCODER_URL = 'https://app.zencoder.com/api/v2/jobs'
JOB_REQUEST = {
	'live_stream': 'true',
	'metadata_passthrough': 'true',
	'region':'us-n-california',
	'outputs': [
		{
			'label': 'hls_300',
			'size': '480x270',
			'video_bitrate': 300,
			'audio_bitrate': 64,
			'url': 's3://bc-jsanford/id3-test/hls_300.m3u8',
			'type': 'segmented',
			'live_stream': 'true',
			'metadata_passthrough': 'true',
			'headers': { 'x-amz-acl': 'public-read' }
		},
		{
			'label': 'hls_600',
			'size': '640x360',
			'video_bitrate': 600,
			'audio_bitrate': 64,
			'url': 's3://bc-jsanford/id3-test/hls_600.m3u8',
			'type': 'segmented',
			'live_stream': 'true',
			'metadata_passthrough': 'true',
			'headers': { 'x-amz-acl': 'public-read' }
		},
		{
			'label': 'hls_1200',
			'size': '1280x720',
			'video_bitrate': 1200,
			'audio_bitrate': 64,
			'url': 's3://bc-jsanford/id3-test/hls_1200.m3u8',
			'type': 'segmented',
			'live_stream': 'true',
			'metadata_passthrough': 'true',
			'headers': { 'x-amz-acl': 'public-read' }
		},
		{
			'url': 's3://bc-jsanford/id3-test/master.m3u8',
			'type': 'playlist',
			'streams': [
				{
					'bandwidth': 450,
					'path': 'hls_300.m3u8'
				},
				{
					'bandwidth': 800,
					'path': 'hls_600.m3u8'
				},
				{
					'bandwidth': 1500,
					'path': 'hls_1200.m3u8'
				}
			],
			'headers': { 'x-amz-acl': 'public-read' }
		}
	]
}

####################
# ID3 DATA CONFIGS #
####################
ID3_TEMPLATE = '{"name":"<REPLACE_NAME>","time":"<REPLACE_TIME>","type":"<REPLACE_TYPE>","parameters":<REPLACE_PARAMETERS>}'
PARAMS_AD_SHORT = '{"duration": "30"}'
PARAMS_AD_MED = '{"duration": "60"}'
PARAMS_AD_LONG = '{"duration": "120"}'
PARAMS_AD_XLONG = '{"duration": "240"}'
PARAMS_CUSTOM_SHORT = '{"key1":"value1","key2":"value2","key3":"value3"}'
PARAMS_CUSTOM_MED = '{"key1":"value1","key2":"value2","key3":"value3","key4":"value4","key5":"value5","key6":"value6"}'
PARAMS_CUSTOM_LONG = '{"key1":"value1","key2":"value2","key3":"value3","key4":"value4","key5":"value5","key6":"value6","key7":"value7","key8":"value8","key9":"value9","key0":"value0"}'
PARAMS_CUSTOM_XLONG = '{"key1":"value1","key2":"value2","key3":"value3","key4":"value4","key5":"value5","key6":"value6","key7":"value7","key8":"value8","key9":"value9","key0":"value0","newkey1":"newvalue1","newkey2":"newvalue2","newkey3":"newvalue3","newkey4":"newvalue4","newkey5":"newvalue5","newkey6":"newvalue6","newkey7":"newvalue7","newkey8":"newvalue8","newkey9":"newvalue9","newkey0":"newvalue0"}'

# creates a Zencoder job
def zencoder_create_job(api_key, api_request):
	headers_map = {
		'Zencoder-Api-Key': api_key,
		'Content-Type': 'application/json',
		'Accept': 'application/json',
		'Host': 'app.zencoder.com'
	}

	req = requests.post(ZENCODER_URL,
						data = json.dumps(api_request),
						headers = headers_map)
	if (req.status_code == 201):
		return req.json()
	else:
		print 'Error creating Zencoder job'
		print req.status_code
		print req.text
		sys.exit()

# injects a cue point in the live stream
def zencoder_inject_cue_point(api_key, job_id, cue_name='adCue', cue_time='30', cue_type='event', cue_parameters='{}'):
	headers_map = {
		'Zencoder-Api-Key': api_key,
		'Content-Type': 'application/json'
	}
	data = ID3_TEMPLATE
	data = data.replace('<REPLACE_NAME>', cue_name)
	data = data.replace('<REPLACE_TIME>', cue_time)
	data = data.replace('<REPLACE_TYPE>', cue_type)
	data = data.replace('<REPLACE_PARAMETERS>', cue_parameters)
	req = requests.post(ZENCODER_URL + '/' + str(job_id) + '/cue_point',
						data = data,
						headers = headers_map)
	return req.status_code

# main program
job = zencoder_create_job(ZENCODER_API_KEY, JOB_REQUEST)
job_id = job['id']
print job_id
stream_url = job['stream_url']
print stream_url
stream_name = job['stream_name']
print stream_name

#ffmpeg_args = '-re -y -i /Users/jsanford/Movies/BC/high_version.mp4 -vcodec copy -acodec copy -f flv '
ffmpeg_cmd = 'ffmpeg -re -y -i /Users/jsanford/Movies/BC/big_buck_bunny_1080p_h264.mov -vcodec copy -acodec copy -f flv '
ffmpeg_cmd += '"' + stream_url + '/' + stream_name + '"'
ffmpeg_cmd += ' > /dev/null 2>&1'

# now start our streaming
ffmpeg = subprocess.Popen(ffmpeg_cmd, shell=True)

params = [PARAMS_AD_SHORT, PARAMS_AD_MED, PARAMS_AD_LONG, PARAMS_AD_XLONG, PARAMS_CUSTOM_SHORT, PARAMS_CUSTOM_MED, PARAMS_CUSTOM_LONG, PARAMS_CUSTOM_XLONG]
i = 0

# wait for a bit before we start going...
time.sleep(15)

# loop and submit requests
while ffmpeg.poll() == None:
	print zencoder_inject_cue_point(ZENCODER_API_KEY, job_id, cue_parameters=params[i])
	i = (i + 1) % len(params)
	time.sleep(5)