import csv
import requests
from datetime import datetime
import os

# Define CompreFace API details
DOMAIN = "http://localhost"  
PORT = 8000  
RECOGNITION_API_KEY = "675b5153-3a80-45af-96b0-bb2c04337c64"  # Replace with your RECOGNITION_API_KEY

url = f"{DOMAIN}:{PORT}/api/v1/recognition/subjects"

# Headers for the API request
headers = {
    "x-api-key": RECOGNITION_API_KEY
}

# Send the GET request to fetch all subjects
response = requests.get(url, headers=headers)

# Check if the request was successful
if response.status_code == 200:
    data = response.json()
    
    # Extract subject names
    subject_names = data.get("subjects", [])

    # Generate filename with current date and time
    current_datetime = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_filename = f'subjects_{current_datetime}.csv'

    with open(csv_filename, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['Subject Name'])  # Write the header
        for name in subject_names:
            writer.writerow([name])

    # Get the full file path
    full_file_path = os.path.abspath(csv_filename)
    print(f"Subject names have been exported to {full_file_path}")
else:
    print(f"Failed to fetch subjects: {response.status_code} {response.text}")
