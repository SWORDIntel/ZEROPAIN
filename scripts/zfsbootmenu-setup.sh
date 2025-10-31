#!/bin/bash
# ZFSBootMenu Setup Script for Siduction Linux on ZFS Root
# This script converts your existing setup to use ZFSBootMenu
# Target: /dev/sda with existing ZFS pool "devpool"

set -euo pipefail

# Configuration
POOL_NAME="devpool"
ROOT_DATASET="$POOL_NAME/ROOT"
BE_NAME="siduction"
EFI_DEVICE="/dev/sda1"
ISO_PATH="/home/siducer/Documents/siduction-2025.1.0-Shine_on-kde-amd64-202503241412.iso"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Logging
log() { echo -e "${GREEN}[$(date +'%H:%M:%S')] $1${NC}"; }
warn() { echo -e "${YELLOW}[WARNING] $1${NC}"; }
error() { echo -e "${RED}[ERROR] $1${NC}"; exit 1; }
info() { echo -e "${BLUE}[INFO] $1${NC}"; }

# Check root
[[ $EUID -ne 0 ]] && error "This script must be run as root"

echo "════════════════════════════════════════════════════════════════"
echo "            ZFSBootMenu Setup for Siduction Linux"
echo "════════════════════════════════════════════════════════════════"
echo ""

# Step 1: Install Prerequisites
install_prerequisites() {
    log "Installing prerequisites for ZFSBootMenu..."
    
    apt update || warn "Could not update package list"
    
    # Core ZFS packages
    apt install -y zfsutils-linux zfs-initramfs zfs-dkms || true
    
    # ZFSBootMenu dependencies
    apt install -y \
        git curl wget \
        kexec-tools \
        fzf \
        mbuffer \
        efibootmgr \
        dracut-core \
        bsdextrautils \
        perl \
        libsort-versions-perl \
        libboolean-perl \
        libyaml-pp-perl \
        systemd-boot-efi || warn "Some packages failed to install"
    
    # Development tools
    apt install -y \
        build-essential \
        linux-headers-$(uname -r) || true
    
    log "Prerequisites installed"
}

# Step 2: Setup ZFS Pool Structure
setup_zfs_structure() {
    log "Setting up ZFS dataset structure..."
    
    # Check if pool exists
    if ! zpool list "$POOL_NAME" &>/dev/null; then
        error "Pool $POOL_NAME not found. Please create it first."
    fi
    
    # Create ROOT container if it doesn't exist
    if ! zfs list "$ROOT_DATASET" &>/dev/null; then
        log "Creating ROOT container..."
        zfs create -o mountpoint=none "$ROOT_DATASET"
    fi
    
    # Create boot environment
    if zfs list "$ROOT_DATASET/$BE_NAME" &>/dev/null; then
        warn "Boot environment $ROOT_DATASET/$BE_NAME already exists"
        read -p "Destroy and recreate? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            zfs destroy -r "$ROOT_DATASET/$BE_NAME"
        else
            warn "Using existing boot environment"
            return
        fi
    fi
    
    log "Creating boot environment: $ROOT_DATASET/$BE_NAME"
    zfs create -o mountpoint=/ -o canmount=noauto \
        -o compression=lz4 -o atime=off \
        "$ROOT_DATASET/$BE_NAME"
    
    # Create sub-datasets for better management
    log "Creating sub-datasets..."
    zfs create -o mountpoint=/var \
        -o canmount=off \
        "$ROOT_DATASET/$BE_NAME/var"
    
    zfs create -o mountpoint=/var/lib \
        -o canmount=off \
        "$ROOT_DATASET/$BE_NAME/var/lib"
    
    zfs create -o mountpoint=/var/lib/docker \
        -o recordsize=64K \
        "$ROOT_DATASET/$BE_NAME/var/lib/docker"
    
    zfs create -o mountpoint=/tmp \
        -o com.sun:auto-snapshot=false \
        -o exec=on \
        "$ROOT_DATASET/$BE_NAME/tmp"
    
    # Create shared home dataset
    if ! zfs list "$POOL_NAME/home" &>/dev/null; then
        log "Creating home dataset..."
        zfs create -o mountpoint=/home \
            -o compression=lz4 \
            "$POOL_NAME/home"
    fi
    
    # Create development datasets
    log "Creating development datasets..."
    for ds in workspace projects src build; do
        if ! zfs list "$POOL_NAME/$ds" &>/dev/null; then
            zfs create -o compression=lz4 -o atime=off "$POOL_NAME/$ds"
        fi
    done
    
    # Set boot filesystem
    log "Setting boot filesystem..."
    zpool set bootfs="$ROOT_DATASET/$BE_NAME" "$POOL_NAME"
    
    # Set ZFSBootMenu properties
    log "Configuring ZFSBootMenu properties..."
    zfs set org.zfsbootmenu:commandline="quiet loglevel=4 elevator=noop" "$ROOT_DATASET"
    zfs set org.zfsbootmenu:active=on "$ROOT_DATASET/$BE_NAME"
    
    log "ZFS structure created successfully"
}

# Step 3: Mount and Prepare Root
mount_root() {
    log "Mounting ZFS root filesystem..."
    
    # Create mount point
    mkdir -p /mnt/zroot
    
    # Mount root dataset
    mount -t zfs "$ROOT_DATASET/$BE_NAME" /mnt/zroot
    
    # Mount other datasets
    mount -t zfs "$ROOT_DATASET/$BE_NAME/var" /mnt/zroot/var 2>/dev/null || true
    mount -t zfs "$ROOT_DATASET/$BE_NAME/var/lib" /mnt/zroot/var/lib 2>/dev/null || true
    mount -t zfs "$ROOT_DATASET/$BE_NAME/tmp" /mnt/zroot/tmp 2>/dev/null || true
    mount -t zfs "$POOL_NAME/home" /mnt/zroot/home 2>/dev/null || true
    
    # Create essential directories
    mkdir -p /mnt/zroot/{dev,proc,sys,run,boot,etc,usr,var,tmp}
    mkdir -p /mnt/zroot/boot/efi
    
    log "Root filesystem mounted at /mnt/zroot"
}

# Step 4: Extract Siduction to ZFS Root
install_siduction() {
    log "Installing Siduction to ZFS root..."
    
    if [[ ! -f "$ISO_PATH" ]]; then
        error "ISO not found at $ISO_PATH"
    fi
    
    # Mount ISO
    mkdir -p /mnt/iso
    mount -o loop,ro "$ISO_PATH" /mnt/iso
    
    log "Extracting filesystem from ISO..."
    
    # Find and extract the squashfs
    local squashfs=$(find /mnt/iso -name "filesystem.squashfs" -type f | head -1)
    
    if [[ -z "$squashfs" ]]; then
        error "No filesystem.squashfs found in ISO"
    fi
    
    # Extract squashfs to ZFS root
    log "Extracting squashfs (this will take several minutes)..."
    unsquashfs -f -d /mnt/zroot "$squashfs"
    
    # Copy kernel and initrd
    log "Copying kernel and initrd..."
    if [[ -d /mnt/iso/boot ]]; then
        cp -av /mnt/iso/boot/vmlinuz* /mnt/zroot/boot/ 2>/dev/null || true
        cp -av /mnt/iso/boot/initrd* /mnt/zroot/boot/ 2>/dev/null || true
    fi
    
    # If kernel was already extracted earlier
    if [[ -d /mnt/siduction/live/boot ]]; then
        log "Copying previously extracted kernel files..."
        cp -av /mnt/siduction/live/boot/vmlinuz* /mnt/zroot/boot/ 2>/dev/null || true
        cp -av /mnt/siduction/live/boot/initrd* /mnt/zroot/boot/ 2>/dev/null || true
    fi
    
    # Cleanup
    umount /mnt/iso
    
    log "Siduction extracted to ZFS root"
}

# Step 5: Configure System
configure_system() {
    log "Configuring system for ZFS boot..."
    
    # Mount virtual filesystems
    mount --bind /dev /mnt/zroot/dev
    mount --bind /proc /mnt/zroot/proc
    mount --bind /sys /mnt/zroot/sys
    mount --bind /run /mnt/zroot/run
    
    # Mount EFI
    mount "$EFI_DEVICE" /mnt/zroot/boot/efi
    
    # Create fstab
    cat > /mnt/zroot/etc/fstab << EOF
# ZFS datasets are mounted by ZFS, not fstab
# Only EFI needs to be here
$(blkid -s UUID -o value "$EFI_DEVICE") /boot/efi vfat defaults 0 0
EOF
    
    # Configure hostname
    echo "siduction-zfs" > /mnt/zroot/etc/hostname
    
    # Configure network
    cat > /mnt/zroot/etc/network/interfaces << EOF
auto lo
iface lo inet loopback

auto eth0
iface eth0 inet dhcp
EOF
    
    # Install ZFS in chroot
    log "Installing ZFS support in chroot..."
    cat > /mnt/zroot/tmp/install-zfs.sh << 'CHROOT_SCRIPT'
#!/bin/bash
export DEBIAN_FRONTEND=noninteractive

# Update package lists
apt update

# Install ZFS
apt install -y --no-install-recommends \
    zfsutils-linux \
    zfs-initramfs \
    zfs-dkms

# Install kernel if missing
if ! ls /boot/vmlinuz-* >/dev/null 2>&1; then
    apt install -y linux-image-amd64 linux-headers-amd64
fi

# Update initramfs
update-initramfs -c -k all

# Configure ZFS services
systemctl enable zfs-import-cache
systemctl enable zfs-mount
systemctl enable zfs-import.target
systemctl enable zfs.target

echo "ZFS installation complete"
CHROOT_SCRIPT
    
    chmod +x /mnt/zroot/tmp/install-zfs.sh
    chroot /mnt/zroot /tmp/install-zfs.sh
    
    log "System configuration complete"
}

# Step 6: Install ZFSBootMenu
install_zfsbootmenu() {
    log "Installing ZFSBootMenu..."
    
    # Create ZBM directory
    mkdir -p /mnt/zroot/boot/efi/EFI/ZBM
    
    # Download ZFSBootMenu EFI executable
    log "Downloading ZFSBootMenu EFI binary..."
    curl -L -o /mnt/zroot/boot/efi/EFI/ZBM/VMLINUZ.EFI \
        https://get.zfsbootmenu.org/efi || \
        wget -O /mnt/zroot/boot/efi/EFI/ZBM/VMLINUZ.EFI \
        https://get.zfsbootmenu.org/efi
    
    # Create backup
    cp /mnt/zroot/boot/efi/EFI/ZBM/VMLINUZ.EFI \
       /mnt/zroot/boot/efi/EFI/ZBM/VMLINUZ-BACKUP.EFI
    
    # Create ZFSBootMenu configuration
    mkdir -p /mnt/zroot/etc/zfsbootmenu
    cat > /mnt/zroot/etc/zfsbootmenu/config.yaml << EOF
Global:
  ManageImages: true
  BootMountPoint: /boot/efi
  DracutConfDir: /etc/zfsbootmenu/dracut.conf.d
  PreHooksDir: /etc/zfsbootmenu/hooks.d
  PostHooksDir: /etc/zfsbootmenu/hooks.d

Components:
  Enabled: false

EFI:
  ImageDir: /boot/efi/EFI/ZBM
  Versions: false
  Enabled: true

Kernel:
  CommandLine: "quiet loglevel=0 zbm.prefer=$POOL_NAME zbm.import_policy=hostid"
  Version: false
EOF
    
    # Create dracut configuration
    mkdir -p /mnt/zroot/etc/zfsbootmenu/dracut.conf.d
    cat > /mnt/zroot/etc/zfsbootmenu/dracut.conf.d/zfsbootmenu.conf << EOF
# ZFSBootMenu dracut configuration
hostonly=no
compress="zstd"
filesystems+=" zfs "
EOF
    
    # Register with UEFI
    log "Registering ZFSBootMenu with UEFI..."
    
    # Get partition number
    PART_NUM=$(echo "$EFI_DEVICE" | grep -o '[0-9]*$')
    DISK_DEVICE=$(echo "$EFI_DEVICE" | sed 's/[0-9]*$//')
    
    # Clear old entries
    for entry in $(efibootmgr | grep -E "ZFSBootMenu|Siduction" | cut -d' ' -f1 | sed 's/Boot//' | sed 's/\*//'); do
        efibootmgr -b "$entry" -B 2>/dev/null || true
    done
    
    # Create new entries
    efibootmgr -c -d "$DISK_DEVICE" -p "$PART_NUM" \
        -L "ZFSBootMenu" \
        -l '\EFI\ZBM\VMLINUZ.EFI' || warn "Failed to create primary EFI entry"
    
    efibootmgr -c -d "$DISK_DEVICE" -p "$PART_NUM" \
        -L "ZFSBootMenu (Backup)" \
        -l '\EFI\ZBM\VMLINUZ-BACKUP.EFI' || warn "Failed to create backup EFI entry"
    
    log "ZFSBootMenu installed successfully"
}

# Step 7: Create Recovery Tools
create_recovery_tools() {
    log "Creating recovery tools..."
    
    # Create snapshot management script
    cat > /mnt/zroot/usr/local/bin/zfs-snapshot << 'EOF'
#!/bin/bash
# Quick snapshot creation tool

POOL="devpool"
BE="siduction"
DATE=$(date +%Y%m%d-%H%M%S)

case "$1" in
    create)
        NAME="${2:-manual-$DATE}"
        zfs snapshot "$POOL/ROOT/$BE@$NAME"
        echo "Created snapshot: $POOL/ROOT/$BE@$NAME"
        ;;
    list)
        zfs list -t snapshot -r "$POOL/ROOT/$BE"
        ;;
    rollback)
        if [[ -z "$2" ]]; then
            echo "Usage: $0 rollback <snapshot-name>"
            exit 1
        fi
        zfs rollback "$POOL/ROOT/$BE@$2"
        echo "Rolled back to: $POOL/ROOT/$BE@$2"
        ;;
    *)
        echo "Usage: $0 {create|list|rollback} [name]"
        ;;
esac
EOF
    chmod +x /mnt/zroot/usr/local/bin/zfs-snapshot
    
    # Create boot environment management script
    cat > /mnt/zroot/usr/local/bin/be-manage << 'EOF'
#!/bin/bash
# Boot Environment Management

POOL="devpool"

case "$1" in
    list)
        echo "Boot Environments:"
        zfs list -r -t filesystem -o name,mountpoint,mounted "$POOL/ROOT"
        ;;
    create)
        if [[ -z "$2" ]]; then
            echo "Usage: $0 create <name> [source]"
            exit 1
        fi
        SOURCE="${3:-$POOL/ROOT/siduction}"
        NEW="$POOL/ROOT/$2"
        zfs snapshot "$SOURCE@be-base"
        zfs clone "$SOURCE@be-base" "$NEW"
        echo "Created boot environment: $NEW"
        ;;
    activate)
        if [[ -z "$2" ]]; then
            echo "Usage: $0 activate <name>"
            exit 1
        fi
        zpool set bootfs="$POOL/ROOT/$2" "$POOL"
        echo "Activated: $POOL/ROOT/$2"
        ;;
    *)
        echo "Usage: $0 {list|create|activate} [args]"
        ;;
esac
EOF
    chmod +x /mnt/zroot/usr/local/bin/be-manage
    
    log "Recovery tools created"
}

# Step 8: Final Configuration
final_configuration() {
    log "Performing final configuration..."
    
    # Create initial snapshot
    log "Creating initial system snapshot..."
    zfs snapshot "$ROOT_DATASET/$BE_NAME@initial-install"
    
    # Set memory limits for ZFS ARC (50% of RAM)
    cat > /mnt/zroot/etc/modprobe.d/zfs.conf << EOF
# Limit ZFS ARC to 50% of RAM
# Adjust the value based on your RAM (this is for 32GB, sets ARC to 16GB)
options zfs zfs_arc_max=17179869184
options zfs zfs_arc_min=1073741824
options zfs zfs_prefetch_disable=0
EOF
    
    # Create systemd service for ZFS tuning
    cat > /mnt/zroot/etc/systemd/system/zfs-tuning.service << EOF
[Unit]
Description=ZFS Performance Tuning
After=zfs-import-cache.service

[Service]
Type=oneshot
ExecStart=/usr/local/bin/zfs-tune.sh
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF
    
    # Create tuning script
    cat > /mnt/zroot/usr/local/bin/zfs-tune.sh << 'EOF'
#!/bin/bash
# ZFS Performance Tuning

# Set ARC size
echo 17179869184 > /sys/module/zfs/parameters/zfs_arc_max

# Optimize for NVMe/SSD
echo 1 > /sys/module/zfs/parameters/zfs_vdev_async_read_min_active
echo 3 > /sys/module/zfs/parameters/zfs_vdev_async_read_max_active
echo 1 > /sys/module/zfs/parameters/zfs_vdev_async_write_min_active
echo 5 > /sys/module/zfs/parameters/zfs_vdev_async_write_max_active

# Transaction group timeout (5 seconds)
echo 5 > /sys/module/zfs/parameters/zfs_txg_timeout

echo "ZFS tuning applied"
EOF
    chmod +x /mnt/zroot/usr/local/bin/zfs-tune.sh
    
    # Enable the service in chroot
    chroot /mnt/zroot systemctl enable zfs-tuning.service 2>/dev/null || true
    
    log "Final configuration complete"
}

# Step 9: Cleanup
cleanup() {
    log "Cleaning up..."
    
    # Unmount everything
    umount /mnt/zroot/boot/efi 2>/dev/null || true
    umount /mnt/zroot/dev 2>/dev/null || true
    umount /mnt/zroot/proc 2>/dev/null || true
    umount /mnt/zroot/sys 2>/dev/null || true
    umount /mnt/zroot/run 2>/dev/null || true
    
    # Export pool for clean import on boot
    log "Exporting ZFS pool..."
    zfs umount -a 2>/dev/null || true
    zpool export "$POOL_NAME" 2>/dev/null || true
    
    log "Cleanup complete"
}

# Step 10: Verification
verify_installation() {
    echo ""
    echo "════════════════════════════════════════════════════════════════"
    echo "                    Installation Complete!"
    echo "════════════════════════════════════════════════════════════════"
    echo ""
    
    # Show EFI entries
    echo "EFI Boot Entries:"
    efibootmgr | grep -E "Boot[0-9]|BootOrder"
    echo ""
    
    # Import pool to show status
    zpool import "$POOL_NAME" 2>/dev/null || true
    
    echo "ZFS Pool Status:"
    zpool status "$POOL_NAME" | head -20
    echo ""
    
    echo "Boot Environments:"
    zfs list -r -t filesystem -o name,mountpoint "$ROOT_DATASET"
    echo ""
    
    echo "Snapshots:"
    zfs list -t snapshot -r "$ROOT_DATASET"
    echo ""
    
    info "════════════════════════════════════════════════════════════════"
    info "                    Next Steps:"
    info "════════════════════════════════════════════════════════════════"
    info ""
    info "1. Reboot your system"
    info "2. ZFSBootMenu will appear automatically"
    info "3. Select 'devpool/ROOT/siduction' to boot"
    info ""
    info "If boot fails, ZFSBootMenu will drop to recovery shell where you can:"
    info "  - Type 'zfsbootmenu' for the menu"
    info "  - Type 'zfs-chroot devpool/ROOT/siduction' to enter the system"
    info "  - Type 'zsnapshots' to manage snapshots"
    info ""
    info "Management commands available after boot:"
    info "  - zfs-snapshot create [name]  # Create snapshot"
    info "  - zfs-snapshot list           # List snapshots"
    info "  - be-manage list              # List boot environments"
    info "  - be-manage create <name>     # Create new boot environment"
    info ""
    
    # Export pool again for clean boot
    zpool export "$POOL_NAME" 2>/dev/null || true
}

# Main execution
main() {
    echo "This will install ZFSBootMenu and convert your system to ZFS root."
    echo "Pool: $POOL_NAME"
    echo "Boot Environment: $ROOT_DATASET/$BE_NAME"
    echo ""
    read -p "Continue? (y/N): " -n 1 -r
    echo
    [[ ! $REPLY =~ ^[Yy]$ ]] && exit 1
    
    install_prerequisites
    setup_zfs_structure
    mount_root
    install_siduction
    configure_system
    install_zfsbootmenu
    create_recovery_tools
    final_configuration
    cleanup
    verify_installation
}

# Run with error handling
trap 'error "Script failed at line $LINENO"' ERR
main "$@"