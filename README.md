2/19/2025 A python script to check for any change in a document (ME state fishing stock report) and send a text message to alert if anychange is detected. Have leveraged script within an AWS Lambda function, with API for manual trigger and eventbridge for cron invokes.

To do? Update value of hash. Change in hash triggers re-parse / diff. Store fishinfo in a database instead of excel Add NH info? Figure out how to message what exactly has changed when sending out the message. Figure out how to add a web skin for the app? So people can enter their email/phone number and select the water(s) they want to monitor.

Pipe dream: Include info on fishing conditions (based off weather, moon etc) info how best bait for the fish that is stocked. Info on fishing laws..
