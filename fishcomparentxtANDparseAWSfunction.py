import os
import hashlib
import requests
from twilio.rest import Client
import logging
import time
import boto3
import pdfplumber

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize S3 client
s3_client = boto3.client('s3')

# Proxy configuration function
def get_pdf_with_proxy(url, proxies=None):
    """
    Fetch a PDF from a URL using an optional proxy.
    :param url: The URL to fetch the PDF from.
    :param proxies: Dictionary of proxies to use (if any).
    :return: response object
    """
    try:
        response = requests.get(url, proxies=proxies)
        response.raise_for_status()  # Raise an error for bad HTTP status codes
        return response
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching PDF through proxy: {e}")
        return None

# Extract relevant information from the PDF
def parse_pdf(file_content):
    """
    Parse the PDF content to extract the relevant data.
    :param file_content: PDF content as bytes.
    :return: List of extracted data (Date, Water, City/Town, Species, QTY, Size)
    """
    extracted_data = []
    try:
        with pdfplumber.open(file_content) as pdf:
            # Loop through each page and extract text
            for page in pdf.pages:
                # Extract table data
                table = page.extract_tables()
                for row in table:
                    if len(row) >= 6:  # Make sure we have all expected columns
                        # Example row structure: [Date, Water, City/Town, Species, QTY, Size]
                        extracted_data.append({
                            "Date": row[0],
                            "Water": row[1],
                            "City/Town": row[2],
                            "Species": row[3],
                            "QTY": row[4],
                            "Size": row[5]
                        })
    except Exception as e:
        logger.error(f"Error parsing PDF: {e}")
    return extracted_data

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
    s3_bucket = 'fishstock'  # S3 bucket name
    s3_hash_file_key = 'fishstockhash.txt'  # S3 key for the hash file

    # List of proxy URLs (set as environment variables)
    proxy_urls = os.getenv('PROXY_URLS').split(',')  # Assuming a comma-separated list of proxies

    # Fetch the expected hash from the S3 URL
    try:
        response = requests.get(s3_hash_file_url)
        response.raise_for_status()  # Raise an error for bad HTTP status codes
        expected_hash = response.text.strip().upper()  # Read hash from file and strip any extra whitespace
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching expected hash from S3: {e}")
        return

    # Iterate over the proxies in the list
    for proxy_url in proxy_urls:
        proxies = {
            "http": proxy_url,
            "https": proxy_url
        }

        # Retry 5 times with each proxy
        for attempt in range(5):
            logger.info(f"Attempt {attempt + 1} of 5 with proxy: {proxy_url}")
            response = get_pdf_with_proxy(file_url, proxies)
            if response and response.status_code == 200:
                file_content = response.content

                # Calculate the SHA256 hash of the file
                file_hash = hashlib.sha256(file_content).hexdigest().upper()

                # Check if the file hash matches the expected hash
                if file_hash != expected_hash:
                    logger.info(f"Hash mismatch detected. Current hash: {file_hash}, Expected hash: {expected_hash}")

                    # Upload new hash to S3
                    try:
                        # Delete the old hash file from S3
                        s3_client.delete_object(Bucket=s3_bucket, Key=s3_hash_file_key)
                        logger.info("Deleted old hash file from S3.")

                        # Create new hash file content
                        new_hash_content = file_hash + "\n"  # Write the new hash to the file

                        # Upload the new hash file to S3
                        s3_client.put_object(Bucket=s3_bucket, Key=s3_hash_file_key, Body=new_hash_content)
                        logger.info(f"Uploaded new hash file to S3 with hash: {file_hash}")
                    except Exception as e:
                        logger.error(f"Error updating hash file in S3: {e}")
                        return  # Exit function if updating the hash file fails

                    # Extract data from PDF
                    extracted_data = parse_pdf(file_content)

                    # Create Twilio client
                    client = Client(account_sid, auth_token)

                    # Send SMS for each entry in the extracted data
                    for entry in extracted_data:
                        # Format the message body
                        message_body = (
                            f"Hello, Fish stalker letting you know that on {entry['Date']}, "
                            f"the Water in {entry['City/Town']} was stalked with {entry['QTY']} "
                            f"{entry['Size']} inch of {entry['Species']}. Good luck and tight lines!"
                        )

                        # Send SMS
                        try:
                            message = client.messages.create(
                                body=message_body,
                                from_=twilio_number,
                                to=to_number
                            )

                            # Log message SID to confirm message sent
                            logger.info(f"Message SID: {message.sid}")
                        except Exception as e:
                            logger.error(f"Error sending SMS: {e}")

                    return  # Exit function after sending the SMS

                else:
                    logger.info("No file change detected.")
                    return  # Exit function since no change was detected

            # If the request fails, log the failure and retry after a brief wait
            logger.error(f"Attempt {attempt + 1} failed with proxy: {proxy_url}")
            time.sleep(5)  # Wait for 5 seconds before retrying

        # If all retries failed for this proxy, try the next proxy
        logger.error(f"All retries failed for proxy: {proxy_url}")

    # If all proxies fail, log and return
    logger.error("All proxies have failed after 5 attempts each. No successful file fetch.")
    return {
        'statusCode': 500,
        'body': 'Lambda function completed with failure.'
    }
