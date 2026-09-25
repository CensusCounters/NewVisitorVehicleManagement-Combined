import os
import requests
import matplotlib.pyplot as plt
from PIL import Image

THRESHOLD = 0.8

# Define the API endpoints
RECOGNIZE_ENDPOINT = "http://172.17.0.1:18081/recognize"
ENROLL_ENDPOINT = "http://172.17.0.1:18081/enroll"

# Define the headers for the requests
HEADERS = {
    "accept": "application/json",
}

# Function to check if a photo is already enrolled
def recognize_photo(file_path):
    files = {
        "file": open(file_path, "rb")
    }
    response = requests.post(RECOGNIZE_ENDPOINT, files=files, headers=HEADERS)
    return response.json()

# Function to enroll a new photo
def enroll_photo(file_path, photo_id):
    files = {
        "file": open(file_path, "rb")
    }
    params = {
        "id": photo_id
    }
    response = requests.post(ENROLL_ENDPOINT, files=files, params=params, headers=HEADERS)
    return response.json()


def enroll_guy(image_path, photo_id):
    enroll_result = enroll_photo(image_path, photo_id)
    print(enroll_result)
    if enroll_result.get('status') == 'success':
        print(f"Photo {photo_id} enrolled successfully.")
    else:
        print(f"Failed to enroll photo {photo_id}: {enroll_result}")


# Folder containing the images
IMAGE_FOLDER = "/home/pavel/Projects/WDUWG/Verigram/FacialTest/KnownPersonsDataset"

# Process each image in the folder
for image_name in os.listdir(IMAGE_FOLDER):
    if image_name.lower().endswith(('.png', '.jpg', '.jpeg')):
        image_path = os.path.join(IMAGE_FOLDER, image_name)
        photo_id = os.path.splitext(image_name)[0]
        print(photo_id)

        # Step 1: Check if the photo is already enrolled
        recognize_result = recognize_photo(image_path)
        # print(recognize_result)
        if recognize_result.get("detail") and recognize_result["detail"] == 'Face not recognized':
            print(f'Face {photo_id} not recognized at all')
            enroll_guy(image_path, photo_id)
        elif recognize_result['matches'][0]['similarity'] < THRESHOLD:
            print(f'Face {photo_id} not recognized with threshold {THRESHOLD}')
            enroll_guy(image_path, photo_id)
            # print(recognize_result)
            # break
        else:
            similarity = recognize_result['matches'][0]['similarity']
            similar_guy_id = recognize_result['matches'][0]['id']
            if similarity < 0.99:
                # similarity = recognize_result['matches'][1]['similarity']
                # similar_guy_id = recognize_result['matches'][1]['id']
                print(f"Face {photo_id} recognized, closest match is {similarity}, id={similar_guy_id}")
                fig, axes = plt.subplots(1, 2, figsize=(10, 5))
                pair = (f'{photo_id}.png', f'{similar_guy_id}.png')
                for i, image_name in enumerate(pair):
                    image_path = os.path.join(IMAGE_FOLDER, image_name)
                    if os.path.exists(image_path):
                        image = Image.open(image_path)
                        axes[i].imshow(image)
                        axes[i].set_title(image_name)
                        axes[i].axis('off')
                    else:
                        axes[i].text(0.5, 0.5, 'Image not found', horizontalalignment='center',
                                     verticalalignment='center')
                        axes[i].set_title(image_name)
                        axes[i].axis('off')
                # plt.tight_layout()
                # plt.show()
            else:
                print(f"Face {photo_id} recognized, closest match is {similarity}, id={similar_guy_id}")


        # # Step 2: If similar photo is found, print a message
        # if recognize_result.get('result') and recognize_result['result']:
        #     print(f"A similar photo for {photo_id} is already enrolled.")
        # else:
        #     # Step 3: If not, enroll the photo
        #     pass
