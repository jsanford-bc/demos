# Sample S3 Watch Folder for DI

This is a simple S3 watch folder in python, using Dynamic Ingest and the CMS API

## Disclaimer

This is intended only as a sample, and should not be considered production ready

## Instructions
Clone this repo to a linux machine that has python installed and has all 
pre-requisite libraries installed as well. Using an Amazon EC2 AMI is a 
good start. Modify the parameters at the top of the file (S3 bucket location, 
AWS profile at minimum, others if desired). Ensure boto is installed, and 
either update the method to find the correct credentials, or set up credentials
under ~/.aws/credentials.

Set up a cron job on the machine for the following (runs the script once 
a minute every minute):

```
* * * * * python /home/ec2-user/watermarking.py >> /home/ec2-user/log.log 2>&1
```

There is a sample XML file provided with all fields that should be included 
for each video that is uploaded. To utilize the system, upload the file 
to the S3 bucket first, then upload the appropriate XML manifest. This 
supports multiple files in a given manifest (just create an Asset in the XML 
under IngestRequest for each one).

When a manifest is processed successfully (or an error occurs in the processing), 
an email is sent to the address listed in the manifest. This is _not_ an 
indication that the video is done processing, but only that the ingest is 
under way.

## Cleaning up
Ideally, this would come with a PHP script that serves as a notification endpoint, 
which will listen for the [Dynamic Ingest notifications](http://docs.brightcove.com/en/video-cloud/di-api/getting-started/overview-di.html#notifications), recognize the asset that 
finished processing, and clean up the S3 bucket. In the meantime, you might 
want to set a bucket policy so that files are cleaned up every day, 
or you can manually clean up the video files that are placed there.

In the end, the goal would be to modify [this PHP script](http://docs.brightcove.com/en/video-cloud/di-api/getting-started/overview-di.html#notifications) (look a little lower) 
and have it figure out how to delete the file, then send an email with the 
completion notification.