import requests
import pdfplumber
import pandas as pd
from io import BytesIO
import re

# Fetch the PDF from the provided URL
pdf_url = "https://www.maine.gov/ifw/docs/2024%20Annual%20Fish%20Stocking%20Report.pdf"
response = requests.get(pdf_url)

# Ensure the request was successful
if response.status_code != 200:
    raise Exception(f"Failed to fetch the PDF, status code {response.status_code}")

# Open the PDF from the response content
with pdfplumber.open(BytesIO(response.content)) as pdf:
    all_data = []
    current_county = None

    # Loop through the pages and extract the text
    for page_number, page in enumerate(pdf.pages, start=1):
        text = page.extract_text()

        # For debugging purposes, print out the first 500 characters of the text on each page
        # print(f"--- Page {page_number} ---")
        # print(text[:500])

        # Search for the county name, accounting for instances where "REPORT" precedes the county
        county_matches = re.findall(r'(?:REPORT\s+)?(\w+\s?\w+)\s+County', text)

        # Check if we found a county name
        if county_matches:
            current_county = county_matches[-1]  # Get the last county found (if multiple counties are mentioned)

        # Split the text into lines and process each line
        lines = text.split('\n')

        for line in lines:
            # Match the structure: DATE WATER City/Town SPECIES QUANTITY SIZE (in inches)
            match = re.match(r'(\d{1,2}/\d{1,2}/\d{4})\s+([A-Za-z\s]+)\s+([A-Za-z\s]+)\s+([A-Za-z\s]+)\s+(\d+)\s+(\d+)', line)

            if match:
                date = match.group(1)  # The date (MM/DD/YYYY)
                water = match.group(2)  # The water body (e.g., ANDROSCOGGIN R)
                city_town = match.group(3)  # City/Town (e.g., LISBON)
                species = match.group(4)  # Species (e.g., BROOK TROUT)
                quantity = match.group(5)  # Quantity (e.g., 300)
                size = match.group(6)  # Size (inches, e.g., 10)

                # Add the entry to the list, including the county if it exists
                if current_county:
                    all_data.append([current_county, date, water, city_town, species, quantity, size])

# Check if any data was extracted
if not all_data:
    raise ValueError("No data extracted from the PDF.")

# Convert to a pandas DataFrame
df = pd.DataFrame(all_data, columns=["County", "DATE", "WATER", "City/Town", "Species", "QTY", "SIZE"])

# Create a new Excel writer object
with pd.ExcelWriter("Fish_Stocking_Report_by_County.xlsx", engine='openpyxl') as writer:
    # Check if the DataFrame contains any data
    if not df.empty:
        # Group by "County" and save each group in its own sheet
        for county, group in df.groupby("County"):
            # Ensure that sheet names are 31 characters or less
            sheet_name = county[:31]
            group.to_excel(writer, sheet_name=sheet_name, index=False)
    else:
        raise ValueError("No valid data to write to Excel.")

print("Excel file has been created successfully.")
