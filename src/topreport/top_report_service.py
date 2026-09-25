# import the necessary packages
import os
import sys
from time import sleep
from datetime import datetime
import psutil
import nvidia_smi
import json
from threading import Thread
import requests
from requests.exceptions import ConnectionError, Timeout, RequestException
import subprocess
from statistics import mean

from known_person_image_sharing_with_vogic import process_and_send_images
from known_person_image_sharing_with_vogic import DEFAULT_FOLDER_PATH, DEFAULT_DB_CONFIG, DEFAULT_API_CONFIG, DEFAULT_LOG_FILE

CPU_USAGE_THRESHOLD=int(os.environ["CPU_USAGE_THRESHOLD"])
CPU_MEMORY_USAGE_THRESHOLD=int(os.environ["CPU_MEMORY_USAGE_THRESHOLD"])
CPU_TEMPERATURE_USAGE_THRESHOLD=int(os.environ["CPU_TEMPERATURE_USAGE_THRESHOLD"])
STORAGE_LABEL=os.environ["STORAGE_LABEL"]
STORAGE_USE_THRESHOLD=int(os.environ["STORAGE_USE_THRESHOLD"])
SHM_USE_THRESHOLD=int(os.environ["SHM_USE_THRESHOLD"])
GPU_USAGE_THRESHOLD=int(os.environ["GPU_USAGE_THRESHOLD"])
GPU_MEMORY_USAGE_THRESHOLD=int(os.environ["GPU_MEMORY_USAGE_THRESHOLD"])
SLEEP_TIME=int(os.environ["SLEEP_TIME"])
REST_API_END_POINT=os.environ["REST_API_END_POINT"]
ENGINE_REGISTRY_URL=os.environ.get("ENGINE_REGISTRY_URL", "http://localhost:8087/register-engines")
EMAIL_ADDRESSES=os.environ["EMAIL_ADDRESSES"]
LOGS_FOLDER=os.environ["LOGS_FOLDER"]

def sendEmail(message, subject, address):
    print("[INFO] Send email")

    emailDataPacket = json.dumps({
        "Message" : message,
        "Subject" : subject,
        "Address" : address
    })
    Thread(target=request_task, args=(REST_API_END_POINT, emailDataPacket)).start()
    print("[INFO] Fire and forget started")

def request_task(REST_API_END_POINT, emailDataPacket):
    try:
        response = requests.post(REST_API_END_POINT,json=json.loads(emailDataPacket))
        responseJson = response.json()
        print("[INFO] Response received")
        if "Successfully Submitted for email" == responseJson["Status"]:
            print("[INFO] Status: ", responseJson["Status"], ". Message Sent")
        else:
            print("[INFO] Status: ", responseJson["Status"], "Message Failed after 3 attempts.")
    except Exception as error:
                print("[INFO] Exception in Send Email: ",  str(error))


def get_top_results(file_obj):
    # Run the 'top' command in batch mode, sort by RES, and capture the output
    result = subprocess.run(['top', '-b', '-o', '+RES', '-n', '1'], capture_output=True, text=True)
    # Split the output into lines
    lines = result.stdout.splitlines()

    # Debugging: Print the first 20 lines to understand the structure
    for i, line in enumerate(lines[:20]):
        print(f"Line {i}: {line}")

    # Find the header line (look for the line that starts with "PID")
    header_index = next((i for i, line in enumerate(lines) if line.lstrip().startswith("PID")), None)

    if header_index is None:
        print("Error: Header line not found.")
        return

    header = lines[header_index]
    # Get the top 30 rows after the header
    top_30 = lines[header_index + 1:header_index + 31]

    # Write the output to a file
    file_obj.write(header + '\n')
    file_obj.write('\n'.join(top_30))
    file_obj.write('***************\n')


def get_engine_containers():
    try:
        # Step 1: Get container IDs and names, filter by 'engine'
        result = subprocess.run(
            ["docker", "ps", "--format", "{{.ID}} {{.Names}}"],
            capture_output=True, text=True, check=True
        )
        lines = result.stdout.strip().splitlines()
        engine_lines = [line for line in lines if "engine" in line]

        engine_data = []

        # Step 2: Extract container ID and IP address
        for line in engine_lines:
            container_id = line.split()[0]
            inspect_result = subprocess.run(
                ["docker", "inspect", "-f", "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}", container_id],
                capture_output=True, text=True, check=True
            )
            ip_address = inspect_result.stdout.strip()

            engine_data.append({"id": container_id, "ip": ip_address})

        return engine_data

    except subprocess.CalledProcessError as e:
        print("Error running Docker commands:", e)
        return []

def send_to_api(data):
    url = ENGINE_REGISTRY_URL
    headers = {"Content-Type": "application/json"}

    response = requests.post(url, headers=headers, data=json.dumps(data))
    print("Status:", response.status_code)
    print("Response:", response.text)


if __name__ == '__main__':
    address = EMAIL_ADDRESSES
    address = address.split(',')

    nvidia_smi.nvmlInit()
    handle = nvidia_smi.nvmlDeviceGetHandleByIndex(0)

    counter = 0
    while True:
        #Update local engine container manager with current engines IDs
        try:
            engines = get_engine_containers()
            if engines:
                try:
                    send_to_api(engines)
                except (ConnectionError, Timeout) as e:
                    print(f"Failed to send to API due to connection issue: {e}")
                except RequestException as e:
                    print(f"General request error while sending to API: {e}")
            else:
                print("No matching containers found.")

        except Exception as e:
            print(f"Unexpected error: {e}")

        if counter % 12 == 0:
            results1 = process_and_send_images(
                folder_path=DEFAULT_FOLDER_PATH,
                db_config=DEFAULT_DB_CONFIG,
                api_config=DEFAULT_API_CONFIG,
                log_file=DEFAULT_LOG_FILE,
                verbose=True,  # Show all the print messages
                process_last_hour_only=False
            )
            print("\nRun process_and_send_images summary:", results1)
            print("-" * 20)
        else:
            print("\nRun process_and_send_images skipped this time")

        emailMessage=''
        alertReason=''

        print(f"Back from sleep for {SLEEP_TIME//60} mins")
        localTimeStampAtClick = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
        cpuUsage = psutil.cpu_percent()
        cpuMemUsage = psutil.virtual_memory().percent
        file_object = open(f'{LOGS_FOLDER}TopReport.txt', 'a')
        file_object.write('At time: ' + localTimeStampAtClick)
        file_object.write('\n')
        file_object.write('***************\n')
        file_object.write('CPU Used %: ')
        file_object.write(str(cpuUsage))
        file_object.write("\n")
        file_object.write('Mem Used %: ')
        file_object.write(str(cpuMemUsage))
        file_object.write('\n')

        get_top_results(file_object)

        file_object.write('\nDocker Stats: \n')
        docker_stats = subprocess.run(['docker', 'stats', '--no-stream'], capture_output=True, text=True)
        file_object.write(docker_stats.stdout)
        file_object.write('\n')

        file_object.write('\nDocker ps: \n')
        docker_ps = subprocess.run(['docker', 'ps'], capture_output=True, text=True)
        file_object.write(docker_ps.stdout)
        file_object.write('\n')

        mem_info = nvidia_smi.nvmlDeviceGetMemoryInfo(handle)
        gpuMemUsage = mem_info.used / mem_info.total * 100

        gpu_utilize = nvidia_smi.nvmlDeviceGetUtilizationRates(handle)
        gpuUsage = gpu_utilize.gpu

        gpu_temperature = nvidia_smi.nvmlDeviceGetTemperature(handle, nvidia_smi.NVML_TEMPERATURE_GPU)

        file_object.write('GPU Load %: ')
        file_object.write(str(gpuUsage))
        file_object.write("\n")
        file_object.write('GPU Mem Used %: ')
        file_object.write(str(gpuMemUsage))
        file_object.write('\n')
        file_object.write('GPU Temp: ')
        file_object.write(str(gpu_temperature))
        file_object.write('\n')


        if gpuUsage > GPU_USAGE_THRESHOLD:
            emailMessage+=f'[INFO] High GPU Load% {gpuUsage} at {localTimeStampAtClick}\n'
            alertReason+='[GPU Load]'

        if gpuMemUsage > GPU_MEMORY_USAGE_THRESHOLD:
            emailMessage+=f'[INFO] High GPU Memory % {gpuMemUsage} at {localTimeStampAtClick}\n'
            alertReason+='[GPU Memory]'

        cmd="sensors"
        temp_info = subprocess.run(["bash", "-c", cmd], stdout=subprocess.PIPE)
        temp_info_decoded=temp_info.stdout.decode('utf-8')
        try:
            temp_value_list = [int(temp_info_decoded.split('\n')[x][16:18]) for x in range(15, 25)]
            temp_value = mean(temp_value_list)
        except:
            temp_value=-1

        file_object.write('\nTemperature info : \n')
        file_object.write(f'CPU temperature (average among all cores): {temp_value}C\n')
        file_object.write('Extended Temperature info : \n')
        file_object.write(temp_info_decoded)
        file_object.write('\n\n')

        if cpuUsage > CPU_USAGE_THRESHOLD:
            emailMessage+=f'[WARNING] High CPU % {cpuUsage} at {localTimeStampAtClick}\n'
            alertReason+="[CPU Usage]"
            file_object.write(emailMessage)

        if cpuMemUsage > CPU_MEMORY_USAGE_THRESHOLD:
            emailMessage+=f'[WARNING] High CPU Memory % {cpuMemUsage} at {localTimeStampAtClick}\n'
            alertReason+='[CPU Memory]'
            file_object.write(emailMessage)

        if temp_value > CPU_TEMPERATURE_USAGE_THRESHOLD:
            emailMessage+=f'[WARNING] High CPU temperature {temp_value}C at {localTimeStampAtClick}\n'
            alertReason+='[CPU Temperature]'
            file_object.write(emailMessage)

        #storage
        cmd_storage_percent="""df -hl | grep '"""+STORAGE_LABEL+"""' | awk '{print $5}' | cut -f1 -d '%'"""
        get_storage_used_percent = subprocess.run(["bash", "-c", cmd_storage_percent], stdout=subprocess.PIPE)
        get_storage_used_percent_decoded=get_storage_used_percent.stdout.decode('utf-8')

        cmd_storage_available_space="""df -hl | grep '"""+STORAGE_LABEL+"""' | awk '{print $4}'"""
        get_storage_available_space = subprocess.run(["bash", "-c", cmd_storage_available_space], stdout=subprocess.PIPE)
        get_storage_available_space_decoded=get_storage_available_space.stdout.decode('utf-8')
        file_object.write(f'Total used {get_storage_used_percent_decoded}% of system volume. Only {get_storage_available_space_decoded} is available.\n')

        try:
            if int(get_storage_used_percent_decoded)>STORAGE_USE_THRESHOLD:
                emailMessage += f'[INFO] Low Storage space: {get_storage_used_percent_decoded}% at {localTimeStampAtClick}. Only {get_storage_available_space_decoded} is available.\n'
                alertReason += '[Low Storage space]'
                file_object.write(emailMessage)
        except:
            print(f'Error while obtaining of storage load percentage\n')
            file_object.write(f'Error while obtaining of storage load percentage\n')

        #shm
        SHM_LABEL='/dev/shm'
        cmd_shm_percent="""df -hl | grep '"""+SHM_LABEL+"""' | awk '{print $5}' | cut -f1 -d '%'"""
        get_shm_used_percent = subprocess.run(["bash", "-c", cmd_shm_percent], stdout=subprocess.PIPE)
        get_shm_used_percent_decoded=get_shm_used_percent.stdout.decode('utf-8')

        cmd_shm_available_space="""df -hl | grep '"""+SHM_LABEL+"""' | awk '{print $4}'"""
        get_shm_available_space = subprocess.run(["bash", "-c", cmd_shm_available_space], stdout=subprocess.PIPE)
        get_shm_available_space_decoded=get_shm_available_space.stdout.decode('utf-8')
        file_object.write(f'Total used {get_shm_used_percent_decoded}% of shared memory. Only {get_shm_available_space_decoded} is available.\n')
        try:
            if int(get_shm_used_percent_decoded)>SHM_USE_THRESHOLD:
                emailMessage += f'[INFO] Low Shared Memory Space: {get_shm_used_percent_decoded}% at {localTimeStampAtClick}. Only {get_shm_available_space_decoded} is available.\n'
                alertReason += '[Low Shared Memory Space]'
        except:
            print(f'Error while obtaining of shm load percentage\n')


        #TODO: for now email sending is deprecated
        # if alertReason != '':
        #     sendEmail(emailMessage, f"High {alertReason} Alert", address)

        file_object.write('***************\n')
        file_object.close()
        counter += 1
        print(f'Job done. Sleeping again for {SLEEP_TIME//60} mins')
        sleep(SLEEP_TIME)
