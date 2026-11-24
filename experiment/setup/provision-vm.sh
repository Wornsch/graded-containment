#!/usr/bin/env bash
# provision-vm.sh
#
# Provisions the experiment VM (Ubuntu Server 26.04 LTS) with the tooling the
# runner needs: base packages and Docker Engine from Docker's official apt
# repository. Run INSIDE the VM as the normal user (uses sudo):
#
#   bash /work/graded-containment/experiment/setup/provision-vm.sh
#
# Deliberately NOT done here: no GitHub or model-provider credentials are put
# into the VM. The repository is copied in from the workstation (rsync), so a
# misbehaving agent in L0 cannot reach the author's accounts.

set -euo pipefail

log() { printf '\033[1;34m[provision]\033[0m %s\n' "$*"; }

[[ -f /etc/os-release ]] && . /etc/os-release
log "Host: ${PRETTY_NAME:-unknown}, kernel $(uname -r)"

log "System update"
sudo apt-get update -q
sudo DEBIAN_FRONTEND=noninteractive apt-get upgrade -yq

log "Base packages"
sudo DEBIAN_FRONTEND=noninteractive apt-get install -yq \
  ca-certificates curl git jq make rsync \
  python3 python3-venv python3-pip

log "Removing conflicting distro packages (if any)"
for p in docker.io docker-compose docker-compose-v2 docker-doc podman-docker containerd runc; do
  sudo apt-get remove -yq "$p" >/dev/null 2>&1 || true
done

log "Docker apt repository"
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
sudo tee /etc/apt/sources.list.d/docker.sources >/dev/null <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: ${UBUNTU_CODENAME:-$VERSION_CODENAME}
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF

log "Docker Engine"
sudo apt-get update -q
sudo DEBIAN_FRONTEND=noninteractive apt-get install -yq \
  docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker

# The runner user drives Docker in the VM. This is the VM's own daemon,
# separate from the workstation; profile containers never get this socket
# unless a profile mounts it on purpose (L0, finding B1).
sudo usermod -aG docker "$USER"

log "Work directory"
sudo mkdir -p /work
sudo chown "$USER:$USER" /work

log "Versions"
{
  echo "date:    $(date -Iseconds)"
  echo "os:      ${PRETTY_NAME:-unknown}"
  echo "kernel:  $(uname -r)"
  echo "docker:  $(sudo docker version --format '{{.Server.Version}}')"
  echo "python:  $(python3 --version 2>&1)"
  echo "git:     $(git --version)"
} | tee /work/vm-info.txt

log "Done. Log out and back in (or 'newgrp docker') so the docker group applies."