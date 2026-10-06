> Combined-project users: read `COMBINED_SETUP.md` first and select a `SITE_PROFILE`.

Updated on Feb 1, 2026

1. If it is a new machine, ollow these instructions if the system is new with nothing other than the OS on it

#install nvidia drivers
1. Need to change the BIOS PCi Settings and check that those are enabled for RTX 5060Ti. Secure BIOS and Fast BOOT should be disabled 
systemctl reboot --firmware-setup to the BIOS
2. Then after reboot 
sudo apt install nvidia-driver-580-open (or the latest driver that is appropriate for the machine)
sudo reboot
nvidia-smi
3. nvidia-smi should show proper output to confirm that the drivers have been loaded


#enable ssh
sudo apt update && sudo apt install -y mc tmux openssh-server

# Add Docker's official GPG key:
sudo apt-get update
sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

# Add the repository to Apt sources:
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo groupadd docker
sudo usermod -aG docker $USER
newgrp docker
sudo systemctl restart docker
docker compose version


curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg \
  && curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
    sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
    sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
docker run --rm --runtime=nvidia --gpus all ubuntu nvidia-smi

sudo reboot

mkdir Projects && cd Projects

#install pycharm community edition
1. Install git following chatgpt instructions
2. go to the Software Apps on Ubuntu and install for PyCharm Community Edition and Google Chrome

#install anydesk
1. Get it from the ubuntu software store

#install Chrome

----------------------------------------------------------

2. If the host is going to be used for both Perimeter Surveillance and Visitor Vehicle, then download the Perimeter Surveillanace code first
and follow those instructions.
2. Download visitor vehicle code
3.  => please change the home dir. path in '/finalfrsproject/__init__.py'

    => please change the home dir. path in '/cleanup_images/clean_uploads_folder.py'

    => please change the home dir. path in '/cleanup_images/clean_uploads_folder.service'
4. cp ./build_all_containers.sh.example ./build_all_containers.sh 
5. cp ./run_all_containers.sh.example ./run_all_containers.sh 
6. cp ./stop_all_containers.sh.example ./stop_all_containers.sh 

7. Set up the database 
    => go to the folder where visitor vehicle is installed 
    => docker cp DB_Files/table_schema_May172025.sql census_counters_postgres_db:/table_schema_May172025.sql
    => docker exec -it census_counters_postgres_db /bin/bash
    => psql -U postgres -d template1 -c "CREATE DATABASE postgres_visitor_vehicle;"
    => psql -U postgres -d postgres_visitor_vehicle -f table_schema_May172025.sql
    => Add a new user 
       INSERT INTO users (created_by, user_name, email, password, user_type) 
       VALUES ('Super Admin','16RSR', '16rsr@censuscounters.com', crypt('password',gen_salt('bf')),'Admin')

8. ./build_all_containers.sh
9. ./run_all_containers.sh
 
---------------------------------------
10. For Vehicle Integration

    ==> Add the camera license to docker-compose-census-counters-visitor-vehicle.yml. The new license has to be run one time 
with the system connected to the internet. The vendor should have given us a license that does not ping home.

    To reuse a plate recognizer license key installed on an another server you will need to uninstall on previous machine first 
    (with Internet connected). https://guides.platerecognizer.com/docs/stream/onpremise/getting-started/#uninstall

    ==> Get the camera url and add it to config.ini file as shown below. If there are more than 1 cameras, repeat this section.

    [[camera-1]]
    active = yes
    url = rtsp://172.17.0.1:8554/mystream

    # Output methods. Uncomment/comment line to enable/disable.
    # - Save to CSV file. The corresponding frame is stored as an image in the same directory.
    csv_file = $(camera)_%y-%m-%d.csv

    # - Send to Webhook. The recognition data and vehicle image are encoded in
    # - multipart/form-data and sent to webhook_target.
    webhook_targets = http://census_anpr_webhook:6068
    # webhook_targets = my-webhook-1, parkpow

    # - Send to ParkPow. See https://app.parkpow.com/accounts/token/
    # - Save to file in JSONLines format. https://jsonlines.org/
    # jsonlines_file = $(camera)_%y-%m-%d.jsonl

    ==> Make sure the license is updated for each camera. A camera.conf file has to be created for each camera e.g. camera-1.conf for id camera-1
    This has to match the camera-id used in the config.ini
    Check with Pavel to confirm.

    ==> If there are folders in ANPR/anpr_data and ANPR/anpr_webhook with images of vehicles then remove those folders. All vehicle images should be stored in the static/anpr_vehicles
    else, it will require clean up from those folders

    ==> To test, run this command to start a rtsp stream for vehicle anpr
    ffmpeg -re -stream_loop -1 -i /home/manish/NewANPRDemoFinal_source/NewANPRDemoFinal/reencoded.mp4 -c:v libx264 -preset ultrafast -crf 23 -f rtsp rtsp://localhost:8554/mystream




--------------------------------------------- End Feb 1 2026 Update ------------------------------------------------






!!!!!!!!!!! This file is in conflict with DB_files/instructions and needs to be merged



    => Install requirements.

    $ pip install -r requirements.txt

    => please change the home dir. path in '/finalfrsproject/__init__.py'

    => please change the home dir. path in '/cleanup_images/clean_uploads_folder.py'

    => please change the home dir. path in '/cleanup_images/clean_uploads_folder.service'


    => Copy the clean up scripts to system.

    $ cd cleanup_images

    $ sudo scp clean_uploads_folder.service /etc/systemd/system/

    $ sudo scp clean_uploads_folder.timer /etc/systemd/system/


    => To start the clean up script.

    $ sudo systemctl start clean_snapshots_folder.timer


    => Flask - Babel Multi - language setup.

    $ cd finalfrsproject

    $ pybabel extract -F babel.cfg -o messages.pot .

    $ pybabel init -i messages.pot -d translations -l en

    $ pybabel init -i messages.pot -d translations -l hi

    $ pybabel compile -d translations

    =>   TO Update translations files

    $ cd finalfrsproject

    $ pybabel extract -F babel.cfg -o messages.pot .

    $ pybabel update -i messages.pot -d translations -l en

    $ pybabel update -i messages.pot -d translations -l hi

    $ pybabel compile -d translations

3. If it is an existing install
 ==> Remove the existing anpr_vehicle_readings table
 ==> Apply the database changes at the bottom from tables_schema.sql to create a new anpr_vehicle_readings table
 ==> Remove the uniqueness of aadhar_image_location from persions table.

4. For Vehicle Integration

    ==> Get the camera url and add it to config.ini file as shown below. If there are more than 1 cameras, repeat this section.

    [[camera-1]]
    active = yes
    url = rtsp://172.17.0.1:8554/mystream

    # Output methods. Uncomment/comment line to enable/disable.
    # - Save to CSV file. The corresponding frame is stored as an image in the same directory.
    csv_file = $(camera)_%y-%m-%d.csv

    # - Send to Webhook. The recognition data and vehicle image are encoded in
    # - multipart/form-data and sent to webhook_target.
    webhook_targets = http://census_anpr_webhook:6068
    # webhook_targets = my-webhook-1, parkpow

    # - Send to ParkPow. See https://app.parkpow.com/accounts/token/
    # - Save to file in JSONLines format. https://jsonlines.org/
    # jsonlines_file = $(camera)_%y-%m-%d.jsonl

    ==> Make sure the license is updated for each camera. A camera.conf file has to be created for each camera e.g. camera-1.conf for id camera-1
    This has to match the camera-id used in the config.ini
    Check with Pavel to confirm.

    ==> If there are folders in ANPR/anpr_data and ANPR/anpr_webhook with images of vehicles then remove those folders. All vehicle images should be stored in the static/anpr_vehicles
    else, it will require clean up from those folders

    ==> To test, run this command to start a rtsp stream for vehicle anpr
    ffmpeg -re -stream_loop -1 -i /home/manish/NewANPRDemoFinal_source/NewANPRDemoFinal/reencoded.mp4 -c:v libx264 -preset ultrafast -crf 23 -f rtsp rtsp://localhost:8554/mystream


--------------------------------- Instructions Added on Aug 1, 2025

5. Follow these instructions if the system is new with nothing other than the OS on it

#install nvidia drivers
1. Need to change the BIOS PCi Settings and check that those are enabled for RTX 5060Ti. Secure BIOS and Fast BOOT should be disabled 
systemctl reboot --firmware-setup to the BIOS
2. Then after reboot 
sudo apt install nvidia-driver-570-open
sudo reboot
nvidia-smi
3. nvidia-smi should show proper output to confirm that the drivers have been loaded


#enable ssh
sudo apt update && sudo apt install -y mc tmux openssh-server

# Add Docker's official GPG key:
sudo apt-get update
sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

# Add the repository to Apt sources:
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo groupadd docker
sudo usermod -aG docker $USER
newgrp docker
sudo systemctl restart docker
docker compose version


curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg \
  && curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
    sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
    sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
docker run --rm --runtime=nvidia --gpus all ubuntu nvidia-smi

sudo reboot

mkdir Projects && cd Projects

#install pycharm community edition
1. Install git following chatgpt instructions
2. go to the Software Apps on Ubuntu and install for PyCharm Community Edition and Google Chrome

#install anydesk
1. Get it from the ubuntu software store

#install Chrome

---------------- Instructions from Apr 1, 2025 --------------------------------

!!!!!!!!!!! This file is in conflict with DB_files/instructions and needs to be merged


1. git pull for Perimetersurveillance
2. ONLY in case of you are going to deploy without Perimetersurveillance on this host ./deployment/host1_run_only_baseline_containers.sh                   # from Perimetersurveillance folder
-----------------------
3. git pull for VisitorVehicle
4. cp ./build_all_containers.sh.example ./build_all_containers.sh 
5. cp ./run_all_containers.sh.example ./run_all_containers.sh 
6. cp ./stop_all_containers.sh.example ./stop_all_containers.sh 
7. ./run_all_containers.sh
docker cp DB_Files/table_schema_May172025.sql census_counters_postgres_db:/table_schema_May172025.sql
docker exec -it census_counters_postgres_db /bin/bash
psql -U postgres -d template1 -c "CREATE DATABASE postgres_visitor_vehicle;"
psql -U postgres -d postgres_visitor_vehicle -f table_schema_May172025.sql

8. Copy the AuraFace-v1 models (https://huggingface.co/fal/AuraFace-v1) into src/fr_engine/models/onnx, each in its own
sub folder and renamed after the model name used in models.json:
   - scrfd_10g_bnkps.onnx -> src/fr_engine/models/onnx/auraface_scrfd_10g_bnkps/auraface_scrfd_10g_bnkps.onnx
   - glintr100.onnx       -> src/fr_engine/models/onnx/auraface_glintr100/auraface_glintr100.onnx
   The engine checks their md5 on start-up and builds the TensorRT engines into src/fr_engine/models/trt-engines
   on the first run, which takes a few minutes.
9. To use it, go to https://localhost:4001/ 

4:07 @manish
4:08 My TODO list for Monday:
Integrate babel into Dockerfile building logic
Prepare cleanup container

---------------- End 
INSERT INTO users (created_by, user_name, email, password, user_type) 
VALUES 
('Super Admin','16RSR', '16rsr@censuscounters.com', crypt('password',gen_salt('bf')),'Admin')

To use a plate recognizer license key on a new server  
you will need to uninstall on previous machine first (with Internet connected)
https://guides.platerecognizer.com/docs/stream/onpremise/getting-started/#uninstall


------------------------------- Instructions from Sep 30, 2025 ---------------------

Blacklist Feature added

1. Add Images to Enroll Feature under Collection = blacklist. Has to small case. 
2. Flush After Enroll to make sure it is added to the collection
