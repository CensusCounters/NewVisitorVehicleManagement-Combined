> Combined-project users: read `COMBINED_SETUP.md` first and select a `SITE_PROFILE`.

1. If it is a new machine, follow these instructions if the system is new with nothing other than the OS on it

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

#TODO: why chatgpt??
1. Install git following chatgpt instructions

#TODO: rework
#install anydesk
1. Get it from the ubuntu software store

#install Chrome

----------------------------------------------------------


## Run BaseContainers 

Run BaseContainers repository to supply with required baseline like databases/etc

## Load ddl into the database

**One time run only to create postrgesql database):** 

```bash
docker cp DB_Files/table_schema_May172025.sql census_counters_postgres_db:/table_schema_May172025.sql
docker exec census_counters_postgres_db psql -U postgres -d postgres_visitor_vehicle -f /table_schema_May172025.sql
```

## Select configuration

Define `SITE_PROFILE` in the docker-compose file 

- `kupwara`
- `ncpass`
- `ganganagar`
- `tangdhar`

The default is `kupwara`. An unknown profile stops application startup with a clear error.

## Logo note

The repository contains the NCPass and Ganganagar logo files. The configured Kupwara and Tangdhar logo filenames were referenced by their branches but
were not present in the supplied repositories. The common layout therefore falls back to `images/census-logo.png` if either deployment-specific logo is missing. Add the real files at:

```text
src/frontend/finalfrsproject/static/images/vajr-28-div-logo.jpeg
src/frontend/finalfrsproject/static/images/shakti-vijay-logo.jpeg
```

#TODO:review this
## Cache busting

Templates call:

```jinja2
{{ asset_url('css/style.css') }}
```

which renders like:

```text
/static/css/style.css?v=combined-1
```

Increment `ASSET_URL_VERSION` when static files change.

```bash
./build_all_containers.sh
./run_all_containers.sh
```
