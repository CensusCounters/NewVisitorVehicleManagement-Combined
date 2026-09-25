#!/usr/bin/env python3
import os
import time

# Folder path
#image_folder = '/project/static/images/uploads'
image_folder = '/home/sankar/Documents/Projects/Visitor-Vehicle-Management/finalfrsproject/static/images/uploads'

# Time in seconds
time_threshold = 60 * 3  # 3 minutes

# Current time
current_time = time.time()

# Iterate over files in the folder
for filename in os.listdir(image_folder):
    file_path = os.path.join(image_folder, filename)
    # Check if the file is an image and older than the threshold
    if os.path.isfile(file_path) and filename.endswith(('.png', '.jpg', '.jpeg')) and current_time - os.path.getmtime(file_path) > time_threshold:
        os.remove(file_path)  # Delete the file