import os
import psycopg2
import requests
from pathlib import Path
from datetime import datetime, timedelta

# --- Constants for Standalone Execution ---
# These are the default configurations used only when the script is run directly.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_FOLDER_PATH = os.environ.get("KNOWN_PERSON_IMAGE_FOLDER", "/known_persons")
DEFAULT_LOG_FILE = os.environ.get("IMAGE_SHARE_LOG_FILE", "/project/logs/processed_files.log")

DEFAULT_DB_CONFIG = {
    "host": os.environ.get("POSTGRESQL_URL", "census_counters_postgres_db"),
    "port": os.environ.get("DB_PORT", "5432"),
    "database": os.environ.get("DB_NAME", "postgres_visitor_vehicle"),
    "user": os.environ.get("DB_USER_NAME", "postgres"),
    "password": os.environ.get("DB_PASSWORD", "postgres"),
}

DEFAULT_API_CONFIG = {
    "url": os.environ.get("IMAGE_SHARE_API_URL", ""),
    "key": os.environ.get("IMAGE_SHARE_API_KEY", ""),
    "timeout": int(os.environ.get("IMAGE_SHARE_TIMEOUT_SECONDS", "30")),
}

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


def send_to_api(file_path, new_filename, api_config, verbose=True):
    """
    Send the image file to the API with the new filename.
    """
    if not api_config.get('url') or not api_config.get('key'):
        if verbose: print("  Image sharing is disabled; API URL/key not configured")
        return False
    try:
        with open(file_path, 'rb') as f:
            files = {'image': (new_filename, f, 'image/jpeg')}
            headers = {'X-API-Key': api_config['key']}

            response = requests.post(
                api_config['url'],
                files=files,
                headers=headers,
                timeout=api_config['timeout']
            )

            if response.status_code in [200, 201]:
                if verbose: print(f"  ✓ API: Successfully sent to API (Status: {response.status_code})")
                return True
            else:
                if verbose: print(f"  ✗ API: Failed with status {response.status_code}: {response.text}")
                return False

    except requests.exceptions.Timeout:
        if verbose: print(f"  ✗ API: Request timed out after {api_config['timeout']} seconds")
        return False
    except requests.exceptions.RequestException as e:
        if verbose: print(f"  ✗ API: Request failed: {e}")
        return False
    except Exception as e:
        if verbose: print(f"  ✗ API: Unexpected error: {e}")
        return False


def load_processed_files(log_file):
    """
    Load the list of already processed files from the log.
    """
    processed = set()
    if os.path.exists(log_file):
        try:
            with open(log_file, 'r') as f:
                for line in f:
                    if '|' in line:
                        filename = line.split('|')[0].strip()
                        processed.add(filename)
        except Exception as e:
            print(f"Warning: Could not read log file: {e}")
    return processed


def log_processed_file(log_file, filename):
    """
    Add a filename to the processed files log with timestamp.
    """
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(log_file, 'a') as f:
            f.write(f"{filename} | {timestamp}\n")
    except Exception as e:
        print(f"Warning: Could not write to log file: {e}")


def get_enrollments_for_last_hour(cursor):
    """
    Queries the database for enrollment_ids created in the previous full hour.

    Returns:
        set: A set of enrollment_id strings, or None on error.
    """
    try:
        now = datetime.now()
        # The hour which just ended
        end_time = now.replace(minute=0, second=0, microsecond=0)
        start_time = end_time - timedelta(hours=1)

        print(
            f"Querying for records created between {start_time.strftime('%Y-%m-%d %H:%M:%S')} and {end_time.strftime('%Y-%m-%d %H:%M:%S')}")

        # IMPORTANT: Replace 'created_at' with the actual name of your timestamp column in the 'persons' table.
        query = """
            SELECT enrollment_id FROM persons
            WHERE created_at >= %s AND created_at < %s
        """
        cursor.execute(query, (start_time, end_time))
        results = cursor.fetchall()

        # Return a set for efficient 'in' checks
        return {row[0] for row in results}

    except Exception as e:
        print(f"Database error while fetching hourly records: {e}")
        return None


def process_and_send_images(folder_path, db_config, api_config, log_file, verbose=True, process_last_hour_only=False):
    """
    Main function to process images, query DB, and send to an API.

    Args:
        folder_path (str): The path to the folder containing images.
        db_config (dict): A dictionary with database connection details.
        api_config (dict): A dictionary with API details (url, key, timeout).
        log_file (str): Path to the log file for tracking processed files.
        verbose (bool): If True, print progress to the console.
        process_last_hour_only (bool): If True, only processes records created in the last full hour.

    Returns:
        dict: A summary of the operations performed.
    """
    if verbose: print(f"Processing folder: {folder_path}")

    try:
        conn = psycopg2.connect(**db_config)
        cursor = conn.cursor()
        if verbose: print("✓ Connected to PostgreSQL database")
    except Exception as e:
        print(f"Failed to connect to database: {e}")
        return {"error": f"Database connection failed: {e}"}

    eligible_enrollments = None
    if process_last_hour_only:
        eligible_enrollments = get_enrollments_for_last_hour(cursor)
        if eligible_enrollments is None:  # Error occurred
            conn.close()
            return {"error": "Failed to query hourly records from DB."}
        if not eligible_enrollments:
            if verbose: print("No new records found in the database for the last hour. Exiting.")
            conn.close()
            return {"message": "No new records to process.", "sent_to_api_success": 0}
        if verbose: print(f"Found {len(eligible_enrollments)} eligible records from the last hour.")

    processed_files = load_processed_files(log_file)
    if verbose: print(f"Found {len(processed_files)} previously processed files in log")

    folder = Path(folder_path)
    if not folder.exists():
        msg = f"Folder not found: {folder_path}"
        if verbose: print(msg)
        conn.close()
        return {"error": msg}

    stats = {
        "total_images_found": 0,
        "already_processed_skipped": 0,
        "sent_to_api_success": 0,
        "no_db_match": 0,
        "api_send_failed": 0,
        "not_in_hourly_window": 0
    }

    for file_path in folder.iterdir():
        if file_path.is_file() and file_path.suffix.lower() in IMAGE_EXTENSIONS:
            stats["total_images_found"] += 1
            filename_no_ext = file_path.stem

            if process_last_hour_only and filename_no_ext not in eligible_enrollments:
                stats["not_in_hourly_window"] += 1
                continue

            if file_path.name in processed_files:
                if verbose: print(f"\n⏭ Skipping (already processed): {file_path.name}")
                stats["already_processed_skipped"] += 1
                continue

            if verbose: print(f"\nProcessing: {file_path.name}")
            person_name, aadhar_number = get_person_info(cursor, filename_no_ext)

            if person_name and aadhar_number:
                #Manish Mohanty --> Manish_Mohanty
                clean_name = person_name.replace(' ', '_').replace('/', '_').replace('\\', '_')
                new_filename = f"{clean_name}_ID_{aadhar_number}_Watchlist_visitors{file_path.suffix}"

                if verbose: print(f"New filename: {new_filename}")

                if send_to_api(file_path, new_filename, api_config, verbose):
                    stats["sent_to_api_success"] += 1
                    log_processed_file(log_file, file_path.name)
                    if verbose: print(f"  ✓ Logged as processed")
                else:
                    stats["api_send_failed"] += 1
            else:
                if verbose: print(f"✗ Skipping (no database match)")
                stats["no_db_match"] += 1

    cursor.close()
    conn.close()

    if verbose:
        print(f"\n{'=' * 50}")
        print(f"Processing complete!")
        print(f"Total images found in folder: {stats['total_images_found']}")
        if process_last_hour_only:
            print(f"Skipped (not in last hour window): {stats['not_in_hourly_window']}")
        print(f"Already processed (skipped): {stats['already_processed_skipped']}")
        print(f"Successfully sent to API: {stats['sent_to_api_success']}")
        print(f"No database match: {stats['no_db_match']}")
        print(f"API send failed: {stats['api_send_failed']}")

    return stats


# --- SCRIPT EXECUTION BLOCK ---
if __name__ == "__main__":
    print("Choose processing mode:")
    print("1. Process ALL images in the folder (default)")
    print("2. Process only images for records created in the LAST FULL HOUR")
    choice = input("Enter your choice (1 or 2): ")

    if choice == '2':
        print("\nRunning in LAST HOUR mode...")
        process_and_send_images(
            folder_path=DEFAULT_FOLDER_PATH,
            db_config=DEFAULT_DB_CONFIG,
            api_config=DEFAULT_API_CONFIG,
            log_file=DEFAULT_LOG_FILE,
            verbose=True,
            process_last_hour_only=True
        )
    elif choice == '1':
        print("\nRunning in ALL IMAGES mode...")
        process_and_send_images(
            folder_path=DEFAULT_FOLDER_PATH,
            db_config=DEFAULT_DB_CONFIG,
            api_config=DEFAULT_API_CONFIG,
            log_file=DEFAULT_LOG_FILE,
            verbose=True,
            process_last_hour_only=False
        )
    else:
        print("Invalid choice. Operation cancelled.")
