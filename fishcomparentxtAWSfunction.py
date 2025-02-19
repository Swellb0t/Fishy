import os
import hashlib
import requests
from twilio.rest import Client
import logging

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Lambda handler function
def lambda_handler(event, context):
    # Twilio credentials from environment variables
    account_sid = os.getenv('TWILIO_ACCOUNT_SID')  # Store in Lambda environment variables
    auth_token = os.getenv('TWILIO_AUTH_TOKEN')    # Store in Lambda environment variables
    twilio_number = os.getenv('TWILIO_PHONE_NUMBER')  # Store in Lambda environment variables

    # Recipient phone number
    to_number = os.getenv('TO_PHONE_NUMBER')  # Store in Lambda environment variables

    # File URL and S3 URL for the expected hash file
    file_url = 'https://www.maine.gov/ifw/docs/current_stocking_report.pdf'
    s3_hash_file_url = 'https://fishstock.s3.us-east-2.amazonaws.com/fishstockhash.txt'

    # Fetch the expected hash from the S3 URL
    try:
        response = requests.get(s3_hash_file_url)
        response.raise_for_status()  # Raise an error for bad HTTP status codes
        expected_hash = response.text.strip().upper()  # Read hash from file and strip any extra whitespace
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching expected hash from S3: {e}")
        return

    # Download the file from the URL
    response = requests.get(file_url)
    if response.status_code == 200:
        file_content = response.content

        # Calculate the SHA256 hash of the file
        file_hash = hashlib.sha256(file_content).hexdigest().upper()

        # Check if the file hash matches the expected hash
        if file_hash != expected_hash:
            # Create Twilio client
            client = Client(account_sid, auth_token)

            # Send SMS
            try:
                message = client.messages.create(
                    body="Hello, this is the Fish Stalker letting you know that a new body of water has been stocked",
                    from_=twilio_number,
                    to=to_number
                )

                # Log message SID to confirm message sent
                logger.info(f"Message SID: {message.sid}")
            except Exception as e:
                logger.error(f"Error sending SMS: {e}")
        else:
            logger.info("No file change detected.")
    else:
        logger.error("Failed to download the file")

    return {
        'statusCode': 200,
        'body': 'Lambda function completed.'
    }
