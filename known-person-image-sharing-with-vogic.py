import os
import psycopg2
import requests
from pathlib import Path
from datetime import datetime

# Configuration
# Get the directory where this script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Construct path to static/known_persons folder
FOLDER_PATH = os.path.join(SCRIPT_DIR, "src", "frontend", "finalfrsproject", "static", "known_persons")
# Log file to track processed files
LOG_FILE = os.path.join(SCRIPT_DIR, "processed_files.log")
POSTGRESQL_HOST = "localhost"  # or "127.0.0.1" if running script outside Docker
POSTGRESQL_PORT = "5432"
POSTGRESQL_DATABASE = "postgres_visitor_vehicle"
POSTGRESQL_USER = "postgres"
POSTGRESQL_PASSWORD = "postgres"

# API Configuration
API_URL = "http://136.51.57.128:8010/api/file-drop/single/"
API_KEY = "external-integration-face-2025"
API_TIMEOUT = 30  # API request timeout in seconds

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png'}


def get_person_info(cursor, filename):
    """
    Query PostgreSQL database to get person name and aadhar number based on enrollment_id.
    """
    try:
        query = """
            SELECT person_name, aadhar_number 
            FROM persons 
            WHERE enrollment_id = %s
        """
        cursor.execute(query, (filename,))
        result = cursor.fetchone()

        if result:
            person_name, aadhar_number = result
            return person_name, aadhar_number
        else:
            print(f"No match found for: {filename}")
            return None, None
    except Exception as e:
        print(f"Database error for {filename}: {e}")
        return None, None


def send_to_api(file_path, new_filename):
    """
    Send the image file to the API with the new filename.
    file_path: Path to the original file to read
    new_filename: The filename to send to the API
    Returns True if successful, False otherwise.
    """
    try:
        # Open the file in binary mode
        with open(file_path, 'rb') as f:
            # Send with the new filename (but read from original file)
            files = {'image': (new_filename, f, 'image/jpeg')}

            # Set the X-API-Key header
            headers = {
                'X-API-Key': API_KEY
            }

            # Make the API request
            response = requests.post(
                API_URL,
                files=files,
                headers=headers,
                timeout=API_TIMEOUT
            )

            # Check if request was successful
            if response.status_code in [200, 201]:
                print(f"  ✓ API: Successfully sent to API (Status: {response.status_code})")
                return True
            else:
                print(f"  ✗ API: Failed with status {response.status_code}: {response.text}")
                return False

    except requests.exceptions.Timeout:
        print(f"  ✗ API: Request timed out after {API_TIMEOUT} seconds")
        return False
    except requests.exceptions.RequestException as e:
        print(f"  ✗ API: Request failed: {e}")
        return False
    except Exception as e:
        print(f"  ✗ API: Unexpected error: {e}")
        return False


def load_processed_files():
    """
    Load the list of already processed files from the log.
    Returns a set of processed filenames.
    """
    processed = set()
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, 'r') as f:
                for line in f:
                    # Each line format: "filename.jpg | 2025-09-30 10:30:45"
                    if '|' in line:
                        filename = line.split('|')[0].strip()
                        processed.add(filename)
        except Exception as e:
            print(f"Warning: Could not read log file: {e}")
    return processed


def log_processed_file(filename):
    """
    Add a filename to the processed files log with timestamp.
    """
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_FILE, 'a') as f:
            f.write(f"{filename} | {timestamp}\n")
    except Exception as e:
        print(f"Warning: Could not write to log file: {e}")


def rename_images():
    """Main function to process and rename images."""

    # Load previously processed files
    processed_files = load_processed_files()
    print(f"Found {len(processed_files)} previously processed files in log")

    # Connect to PostgreSQL database
    try:
        conn = psycopg2.connect(
            host=POSTGRESQL_HOST,
            port=POSTGRESQL_PORT,
            database=POSTGRESQL_DATABASE,
            user=POSTGRESQL_USER,
            password=POSTGRESQL_PASSWORD
        )
        cursor = conn.cursor()
        print("✓ Connected to PostgreSQL database")
    except Exception as e:
        print(f"Failed to connect to database: {e}")
        return

    # Get all image files in the folder
    folder = Path(FOLDER_PATH)

    if not folder.exists():
        print(f"Folder not found: {FOLDER_PATH}")
        conn.close()
        return

    processed = 0
    sent_to_api = 0
    skipped_already_processed = 0

    # Loop through all files in the folder
    for file_path in folder.iterdir():
        if file_path.is_file():
            # Check if it's an image file
            if file_path.suffix.lower() in IMAGE_EXTENSIONS:
                processed += 1

                # Check if this file was already processed
                if file_path.name in processed_files:
                    print(f"\n⏭ Skipping (already processed): {file_path.name}")
                    skipped_already_processed += 1
                    continue

                # Get filename without extension
                filename_no_ext = file_path.stem
                extension = file_path.suffix

                print(f"\nProcessing: {file_path.name}")

                # Query database for person info
                person_name, aadhar_number = get_person_info(cursor, filename_no_ext)

                if person_name and aadhar_number:
                    # Create new filename: PersonName_ID_AadharNumber_Watchlist_visitors.ext
                    # Clean person name (remove special characters that might cause issues)
                    clean_name = person_name.replace(' ', '_').replace('/', '_').replace('\\', '_')
                    new_filename = f"{clean_name}_ID_{aadhar_number}_Watchlist_visitors{extension}"

                    print(f"New filename: {new_filename}")

                    # Send original file to API with new filename
                    if send_to_api(file_path, new_filename):
                        sent_to_api += 1
                        # Log the original file as processed after successful API call
                        log_processed_file(file_path.name)
                        print(f"  ✓ Logged as processed")
                else:
                    print(f"✗ Skipping (no database match)")

    # Close database connection
    cursor.close()
    conn.close()

    print(f"\n{'=' * 50}")
    print(f"Processing complete!")
    print(f"Total images found: {processed}")
    print(f"Already processed (skipped): {skipped_already_processed}")
    print(f"Successfully sent to API: {sent_to_api}")
    print(f"Failed/No match: {processed - sent_to_api - skipped_already_processed}")


if __name__ == "__main__":
    # Optional: Ask for confirmation before proceeding
    print(f"This script will send image files from: {FOLDER_PATH}")
    print(f"Files will be sent to API with renamed filenames (originals preserved).")
    response = input("Do you want to continue? (yes/no): ")

    if response.lower() in ['yes', 'y']:
        rename_images()
    else:
        print("Operation cancelled.")