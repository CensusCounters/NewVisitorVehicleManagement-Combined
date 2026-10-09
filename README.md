# Visitor Vehicle Management

## Admin: GitHub deploy keys

An admin does this on a workstation that already has this repository and an admin `gh` login. Each machine gets one read-only deploy key named `census-vv-<clientname>` (for example `census-vv-kupwara`).

Issue a key:

```bash
./scripts/issue_github_deploy_key.sh issue <clientname>
```

The private key is written to `~/.local/share/census-counters/deploy-keys/census-vv-<clientname>`. Give the user that file and `scripts/setup_git.sh`, then delete the workstation copy.

List keys:

```bash
./scripts/issue_github_deploy_key.sh list
```

Revoke a key:

```bash
./scripts/issue_github_deploy_key.sh revoke <key-id>
```

After a revoke, delete `~/.ssh/census-vv-<clientname>` on that machine.

## 1. New x86 machine

Follow these steps on a new machine with nothing but the OS installed.

### NVIDIA driver

1. Enable the PCIe settings for the GPU (RTX 5060 Ti) in the BIOS and disable Secure Boot and Fast Boot.
   To get to the BIOS: `systemctl reboot --firmware-setup`
2. After the reboot, install driver 595 or newer:
```bash
sudo apt install nvidia-driver-610-open
sudo reboot
nvidia-smi
```
3. `nvidia-smi` should show driver 595.x (or newer) and "CUDA Version: 13.2" (or higher).

### SSH

```bash
sudo apt update && sudo apt install -y mc tmux openssh-server
```

### Docker

```bash
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
```

### NVIDIA Container Toolkit

```bash
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
```

### Other tools

- AnyDesk:
```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://keys.anydesk.com/repos/DEB-GPG-KEY -o /etc/apt/keyrings/keys.anydesk.com.asc
sudo chmod a+r /etc/apt/keyrings/keys.anydesk.com.asc
echo "deb [signed-by=/etc/apt/keyrings/keys.anydesk.com.asc] https://deb.anydesk.com all main" | \
  sudo tee /etc/apt/sources.list.d/anydesk-stable.list > /dev/null
sudo apt-get update
sudo apt-get install -y anydesk
```
- Chrome:
```bash
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo apt install ./google-chrome-stable_current_amd64.deb
rm google-chrome-stable_current_amd64.deb
```

### Git

The admin provides `setup_git.sh` and the private key `census-vv-<clientname>`. On this machine, copy them to these paths:

- `setup_git.sh` to `~/Projects/setup_git.sh`
- `census-vv-<clientname>` to `~/.ssh/census-vv-<clientname>`

```bash
mkdir -p "$HOME/Projects" "$HOME/.ssh"
chmod 700 "$HOME/.ssh"
bash ~/Projects/setup_git.sh <clientname>
```

That installs Git, uses the key at `~/.ssh/census-vv-<clientname>`, and clones into `~/Projects/NewVisitorVehicleManagement-Combined`.

----------------------------------------------------------

## 2. Jetson Orin Nano (JetPack 7.2 or newer)

The same repository and compose file run on Jetson. JetPack 7.2+ ships the NVIDIA driver, Docker and the
NVIDIA Container Toolkit, so skip those steps in section 1, and skip AnyDesk and Chrome. Do the Git steps.

1. Flash JetPack 7.2.1 or later. 
2. Check that Docker has the `nvidia` runtime:
```bash
docker info | grep -i runtimes
# if nvidia is missing:
sudo nvidia-ctk runtime configure --runtime=docker && sudo systemctl restart docker
```
3. Install Git and clone with `bash ~/Projects/setup_git.sh <clientname>` (section 1, Git).
4. Continue with section 3. In section 5, use `.env.jetson.example`.


----------------------------------------------------------

## 3. Run BaseContainers

Run the BaseContainers repository first. It provides PostgreSQL, Redis and the external
`census_counters_network` Docker network used by this stack.

## 4. Load the database schema

**One time only, to create the PostgreSQL database:**

```bash
docker cp DB_Files/schema.sql census_counters_postgres_db:/schema.sql
docker exec census_counters_postgres_db psql -U postgres -d template1 -c "CREATE DATABASE postgres_visitor_vehicle;"
docker exec census_counters_postgres_db psql -v ON_ERROR_STOP=1 -U postgres -d postgres_visitor_vehicle -f /schema.sql
```

This also creates the initial users (password `password`); change their passwords after the first login.

## 5. Configuration

1. Copy the compose file and the helper scripts:
```bash
cp docker-compose-census-counters-visitor-vehicle.yml.example docker-compose-census-counters-visitor-vehicle.yml
cp build_all_containers.sh.example build_all_containers.sh
cp run_all_containers.sh.example run_all_containers.sh
cp stop_all_containers.sh.example stop_all_containers.sh
```
2. Copy the memory and index settings for the machine type:
```bash
cp .env.x86.example .env      # x86 with an NVIDIA GPU
cp .env.jetson.example .env   # Jetson Orin Nano
```
3. Set `SITE_PROFILE` (and a real `SECRET_KEY`) for `census_counters_webservice_fr` in the compose file:
   - `kupwara` (default)
   - `ncpass`
   - `ganganagar`
   - `tangdhar`

   An unknown profile stops application startup with a clear error.

## 6. Build and run

```bash
./build_all_containers.sh
./run_all_containers.sh
```

`./stop_all_containers.sh` stops the stack.

Website is available at https://<host>/censusvv/

----------------------------------------------------------

## 7. Upgrading an existing x86 install (CUDA 12, Milvus GPU + etcd + MinIO -> CUDA 13.2, single-container Milvus CPU)

Milvus now runs as one 2.6 container (embedded etcd, local storage, Woodpecker log on local disk, volume
`census_counters_milvus`) instead of three. Milvus can't upgrade 2.5.13 data to 2.6 in place, so the new volume
starts empty and the enrolled faces are copied over with `src/fr_engine/src/milvus_migrate.py`.

1. With the old stack still running, stop new enrollments and export the faces:
```bash
git pull
docker stop census_counters_webservice_fr
docker exec census_counters_fr_engine python /app/milvus_migrate.py export /models/milvus_export.json
```
2. Stop the old stack with the old compose file, so etcd and MinIO are stopped too:
```bash
docker compose -f docker-compose-census-counters-visitor-vehicle.yml down
```
3. Upgrade the driver to 595+ (see section 1) and reboot.
4. Re-copy `docker-compose-census-counters-visitor-vehicle.yml.example` and re-apply local edits (`SITE_PROFILE`, `SECRET_KEY`, ...).
   Then `cp .env.x86.example .env`.
5. Rebuild and start (`./build_all_containers.sh && ./run_all_containers.sh`). TensorRT engines are rebuilt
   automatically (their file names include the TensorRT version); wait until `census_counters_fr_engine` is healthy.
6. Import the faces and check the counts match the export:
```bash
docker exec census_counters_fr_engine python /app/milvus_migrate.py import /models/milvus_export.json
```
7. After verifying recognition of a known person, delete `src/fr_engine/models/milvus_export.json` (it contains
   names and Aadhaar numbers), the old `*.plan` files in `src/fr_engine/models/trt-engines/`, and the legacy
   volumes `*census_counters_facedb`, `*census_counters_etcd`, `*census_counters_minio` (`docker volume ls`).

