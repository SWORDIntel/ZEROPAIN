#!/usr/bin/env bash
# ==============================================================================
# ZEROPAIN - Nebius Cloud 10M Patient GPU Deployment & Execution Script
# ==============================================================================
# Automates spinning up a GPU instance (1x H100 SXM or 1x L40S) in Nebius Cloud,
# deploying the ZEROPAIN codebase, executing the 10,000,000 patient trial
# with PyTorch CUDA tensor acceleration, retrieving results, and tearing down.
#
# Supported GPU Platforms:
#   - H100 SXM5 80GB  : platform: gpu-h100-sxm, preset: 1gpu-16vcpu-200gb (Default)
#   - L40S PCIe 48GB  : platform: gpu-l40s-d,  preset: 1gpu-16vcpu-96gb
#
# Usage:
#   ./deploy_nebius_10m.sh [--gpu-type h100|l40s] [--test-mode] [--dry-run] [--auto-terminate]
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

NEBIUS_BIN="$(command -v nebius || echo "${HOME}/.nebius/bin/nebius")"
if [[ ! -x "${NEBIUS_BIN}" ]]; then
    echo "[-] Error: Nebius CLI binary not found at ${NEBIUS_BIN}" >&2
    exit 1
fi

# Default configuration
GPU_TYPE="h100"
REGION="eu-north1"
PROJECT_ID="project-e00re3c0pr00026p9jzhq4"
SUBNET_ID="vpcsubnet-e00j50ben51r17797n"
IMAGE_ID="computeimage-e00gks08cn3zbqssgz" # vectorrevamp-gpu-v1 (ready PyTorch/CUDA)
DISK_SIZE_GB="300"
SSH_KEY_PUB=""
TEST_MODE=""
DRY_RUN="false"
AUTO_TERMINATE="false"
INSTANCE_NAME="zeropain-10m-$(date +%s)"

# Parse CLI arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --gpu-type)
            GPU_TYPE="$2"
            shift 2
            ;;
        --project-id)
            PROJECT_ID="$2"
            shift 2
            ;;
        --subnet-id)
            SUBNET_ID="$2"
            shift 2
            ;;
        --image-id)
            IMAGE_ID="$2"
            shift 2
            ;;
        --disk-size)
            DISK_SIZE_GB="$2"
            shift 2
            ;;
        --ssh-key)
            SSH_KEY_PUB="$2"
            shift 2
            ;;
        --test-mode)
            TEST_MODE="--test-mode"
            shift
            ;;
        --dry-run)
            DRY_RUN="true"
            shift
            ;;
        --auto-terminate)
            AUTO_TERMINATE="true"
            shift
            ;;
        *)
            echo "[-] Unknown option: $1" >&2
            exit 1
            ;;
    esac
done

# Select Platform and Preset based on GPU_TYPE
if [[ "${GPU_TYPE}" == "h100" ]]; then
    PLATFORM="gpu-h100-sxm"
    PRESET="1gpu-16vcpu-200gb"
    GPU_LABEL="1x NVIDIA H100 SXM5 (80GB VRAM, 200GB Host RAM, 16 vCPUs)"
elif [[ "${GPU_TYPE}" == "l40s" ]]; then
    PLATFORM="gpu-l40s-d"
    PRESET="1gpu-16vcpu-96gb"
    GPU_LABEL="1x NVIDIA L40S (48GB VRAM, 96GB Host RAM, 16 vCPUs)"
else
    echo "[-] Error: Unsupported gpu-type '${GPU_TYPE}'. Use 'h100' or 'l40s'." >&2
    exit 1
fi

# Locate or generate SSH Key
if [[ -z "${SSH_KEY_PUB}" ]]; then
    if [[ -f "${HOME}/.ssh/id_rsa.pub" ]]; then
        SSH_KEY_PUB="${HOME}/.ssh/id_rsa.pub"
    elif [[ -f "${HOME}/.ssh/id_ed25519.pub" ]]; then
        SSH_KEY_PUB="${HOME}/.ssh/id_ed25519.pub"
    else
        echo "[*] Generating ephemeral SSH key pair for deployment..."
        mkdir -p "${HOME}/.ssh"
        ssh-keygen -t ed25519 -N "" -f "${HOME}/.ssh/id_nebius_zeropain" -C "zeropain-runner"
        SSH_KEY_PUB="${HOME}/.ssh/id_nebius_zeropain.pub"
    fi
fi

SSH_KEY_CONTENT="$(cat "${SSH_KEY_PUB}")"
SSH_PRIV_KEY="${SSH_KEY_PUB%.pub}"

# Prepare Cloud-Init User Data
CLOUD_INIT=$(cat <<EOF
#cloud-config
users:
  - name: ubuntu
    sudo: ALL=(ALL) NOPASSWD:ALL
    shell: /bin/bash
    ssh_authorized_keys:
      - ${SSH_KEY_CONTENT}
package_update: true
packages:
  - git
  - rsync
  - python3-pip
  - python3-venv
  - htop
EOF
)

# Prepare Nebius Instance Specification JSON
SPEC_DIR="runs/nebius_deploy"
mkdir -p "${SPEC_DIR}"
SPEC_FILE="${SPEC_DIR}/instance_spec_${INSTANCE_NAME}.json"

cat <<EOF > "${SPEC_FILE}"
{
  "metadata": {
    "name": "${INSTANCE_NAME}",
    "parent_id": "${PROJECT_ID}",
    "labels": {
      "workload": "zeropain-10m-simulation",
      "gpu_type": "${GPU_TYPE}"
    }
  },
  "spec": {
    "resources": {
      "platform": "${PLATFORM}",
      "preset": "${PRESET}"
    },
    "boot_disk": {
      "attach_mode": "read_write",
      "managed_disk": {
        "source_image_id": "${IMAGE_ID}",
        "size_gibibytes": ${DISK_SIZE_GB},
        "type": "network_ssd"
      }
    },
    "network_interfaces": [
      {
        "name": "eth0",
        "subnet_id": "${SUBNET_ID}",
        "public_ip_address": {}
      }
    ],
    "cloud_init_user_data": $(echo "${CLOUD_INIT}" | jq -s -R .)
  }
}
EOF

echo "================================================================================"
echo "          ZEROPAIN NEBIUS GPU DEPLOYMENT ORCHESTRATOR                           "
echo "================================================================================"
echo "  Target Region        : ${REGION}"
echo "  Project ID           : ${PROJECT_ID}"
echo "  Subnet ID            : ${SUBNET_ID}"
echo "  Instance Name        : ${INSTANCE_NAME}"
echo "  GPU Hardware         : ${GPU_LABEL}"
echo "  Boot Image ID        : ${IMAGE_ID}"
echo "  Disk Size            : ${DISK_SIZE_GB} GiB Network SSD"
echo "  SSH Key File         : ${SSH_KEY_PUB}"
echo "  Trial Mode           : ${TEST_MODE:-FULL 10,000,000 PATIENT RUN}"
echo "  Dry Run              : ${DRY_RUN}"
echo "  Auto Terminate       : ${AUTO_TERMINATE}"
echo "  Spec Manifest Path   : ${SPEC_FILE}"
echo "================================================================================"

if [[ "${DRY_RUN}" == "true" ]]; then
    echo ""
    echo "[DRY RUN] Manifest generated successfully. Planned execution commands:"
    echo "  1. nebius compute instance create --file ${SPEC_FILE}"
    echo "  2. Poll instance status until READY"
    echo "  3. rsync -avz --exclude '.git' --exclude 'runs' . ubuntu@<IP>:~/ZEROPAIN/"
    echo "  4. ssh ubuntu@<IP> 'cd ~/ZEROPAIN && ./run_10m_simulations.sh --device cuda ${TEST_MODE}'"
    echo "  5. rsync -avz ubuntu@<IP>:~/ZEROPAIN/runs/ ./runs/nebius_results/"
    echo "  6. nebius compute instance delete --id <INSTANCE_ID>"
    echo ""
    echo "[DRY RUN] Finished without creating cloud resources."
    exit 0
fi

# Step 1: Create Compute Instance
echo ""
echo "[1/6] Requesting instance creation via Nebius CLI..."
CREATE_OUT="$("${NEBIUS_BIN}" compute instance create --file "${SPEC_FILE}" --format json)"
INSTANCE_ID="$(echo "${CREATE_OUT}" | jq -r '.metadata.id // .id // empty')"

if [[ -z "${INSTANCE_ID}" ]]; then
    # Fallback to operation ID check
    OP_ID="$(echo "${CREATE_OUT}" | jq -r '.id // empty')"
    echo "[*] Tracking creation operation: ${OP_ID}..."
    sleep 10
    INSTANCE_ID="$("${NEBIUS_BIN}" compute instance list --format json | jq -r ".items[] | select(.metadata.name == \"${INSTANCE_NAME}\") | .metadata.id")"
fi

if [[ -z "${INSTANCE_ID}" ]]; then
    echo "[-] Failed to determine created instance ID. Output was:"
    echo "${CREATE_OUT}"
    exit 1
fi

echo "[+] Instance created with ID: ${INSTANCE_ID}"

# Trap cleanup instructions in case of error
cleanup_notice() {
    echo ""
    echo "================================================================================"
    echo "  CRITICAL VM LIFECYCLE NOTICE: Instance is active!"
    echo "  To avoid unwanted billing charges, delete the VM when done:"
    echo "    nebius compute instance delete --id ${INSTANCE_ID}"
    echo "================================================================================"
}
trap cleanup_notice EXIT

# Step 2: Wait for Instance to be RUNNING & Obtain Public IP
echo ""
echo "[2/6] Waiting for instance to become RUNNING and obtain public IP..."
MAX_WAIT_SECS=300
ELAPSED=0
PUBLIC_IP=""

while [[ ${ELAPSED} -lt ${MAX_WAIT_SECS} ]]; do
    INST_INFO="$("${NEBIUS_BIN}" compute instance get --id "${INSTANCE_ID}" --format json 2>/dev/null || true)"
    STATE="$(echo "${INST_INFO}" | jq -r '.status.state // empty')"
    PUBLIC_IP="$(echo "${INST_INFO}" | jq -r '.status.network_interfaces[0].public_ip_address.address // empty')"

    if [[ "${STATE}" == "RUNNING" || "${STATE}" == "READY" ]] && [[ -n "${PUBLIC_IP}" && "${PUBLIC_IP}" != "null" ]]; then
        echo "[+] Instance is RUNNING with Public IP: ${PUBLIC_IP}"
        break
    fi

    echo "    Status: ${STATE:-WAITING}, IP: ${PUBLIC_IP:-PENDING}... (${ELAPSED}s elapsed)"
    sleep 10
    ELAPSED=$((ELAPSED + 10))
done

if [[ -z "${PUBLIC_IP}" || "${PUBLIC_IP}" == "null" ]]; then
    echo "[-] Timeout waiting for instance public IP. Exiting."
    exit 1
fi

# Step 3: Wait for SSH Availability
echo ""
echo "[3/6] Waiting for SSH port to open on ${PUBLIC_IP}..."
SSH_OPTS=(-i "${SSH_PRIV_KEY}" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=5)
SSH_READY=0
for i in {1..30}; do
    if ssh "${SSH_OPTS[@]}" "ubuntu@${PUBLIC_IP}" "echo 'SSH_READY'" >/dev/null 2>&1; then
        SSH_READY=1
        echo "[+] SSH is active and accepting connections!"
        break
    fi
    sleep 5
done

if [[ ${SSH_READY} -eq 0 ]]; then
    echo "[-] Unable to establish SSH connection to ${PUBLIC_IP}. Check security groups/firewall."
    exit 1
fi

# Step 4: Synchronize Codebase to Remote VM
echo ""
echo "[4/6] Rsyncing ZEROPAIN repository to remote VM..."
ssh "${SSH_OPTS[@]}" "ubuntu@${PUBLIC_IP}" "mkdir -p ~/ZEROPAIN"
rsync -avz -e "ssh ${SSH_OPTS[*]}" \
    --exclude '.git' \
    --exclude 'runs' \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    ./ "ubuntu@${PUBLIC_IP}:~/ZEROPAIN/"

# Step 5: Verify GPU & Execute 10M Simulation on Remote Instance
echo ""
echo "[5/6] Verifying CUDA and launching 10M Simulation on GPU..."
ssh "${SSH_OPTS[@]}" "ubuntu@${PUBLIC_IP}" "nvidia-smi"
ssh "${SSH_OPTS[@]}" "ubuntu@${PUBLIC_IP}" "python3 -c \"import torch; print('PyTorch CUDA Ready:', torch.cuda.is_available(), '| Device Name:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'NONE')\""

REMOTE_OUT_DIR="runs/nebius_10m_run"
echo "[*] Starting simulation run on GPU..."
ssh "${SSH_OPTS[@]}" "ubuntu@${PUBLIC_IP}" "cd ~/ZEROPAIN && ./run_10m_simulations.sh --device cuda --output-dir ${REMOTE_OUT_DIR} ${TEST_MODE}"

# Step 6: Download Results
echo ""
echo "[6/6] Downloading trial results from remote instance..."
LOCAL_DEST_DIR="runs/nebius_results_$(date +%Y%m%d_%H%M%S)"
mkdir -p "${LOCAL_DEST_DIR}"
rsync -avz -e "ssh ${SSH_OPTS[*]}" "ubuntu@${PUBLIC_IP}:~/ZEROPAIN/${REMOTE_OUT_DIR}/" "${LOCAL_DEST_DIR}/"

echo ""
echo "================================================================================"
echo "  NEBIUS GPU RUN COMPLETED SUCCESSFULLY!"
echo "  Local Results Dir: ${LOCAL_DEST_DIR}"
echo "================================================================================"

# Auto-terminate if requested
if [[ "${AUTO_TERMINATE}" == "true" ]]; then
    echo "[*] Auto-terminate enabled: deleting VM instance ${INSTANCE_ID}..."
    "${NEBIUS_BIN}" compute instance delete --id "${INSTANCE_ID}"
    echo "[+] VM instance successfully deleted."
    trap - EXIT
else
    echo ""
    echo "================================================================================"
    echo "  REMINDER: To terminate this instance and stop billing, run:"
    echo "    nebius compute instance delete --id ${INSTANCE_ID}"
    echo "================================================================================"
fi
