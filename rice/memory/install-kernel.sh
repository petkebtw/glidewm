#!/bin/sh
# Install the tailored 7.2.9-optimized kernel built in ~/src/linux-glide (rice/memory, 2026-11-26).
# Run: sudo ~/dwm/rice/memory/install-kernel.sh      Undo: sudo ~/dwm/rice/memory/install-kernel.sh --remove
# Menu only: sudo ~/dwm/rice/memory/install-kernel.sh --grub
#
# Same as 7.2.9-eclipse (cachyos 7.2.9: clang/LLVM, ThinLTO, -march=native, -O3, BORE, BBRv3, MGLRU, full
# preempt, 1000 Hz), minus the generic-distro weight: 249 modules instead of ~6300 (localmodconfig + a list of
# things you may plug in), NR_CPUS 16 instead of 8192 (MAXSMP), no NUMA, no debug info/BTF (sched_ext off: no
# scx here), no ftrace/kprobes/kexec/crash dump, no KALLSYMS_ALL. Hibernation, 32-bit (Steam/Wine), NTSYNC kept.
# The NVIDIA 615.78.08 open modules are built for it by hand (~/src/nvidia-glide), so portage keeps the
# eclipse kernel's own modules: the old kernel stays a working fallback (grub "Advanced options").
set -e
[ "$(id -u)" = 0 ] || { echo "run with sudo"; exit 1; }
U=$(stat -c %U "$0")
H=$(getent passwd "$U" | cut -d: -f6)
K="$H/src/linux-glide"
NV="$H/src/nvidia-glide/nv/kernel-open"
V=$(cat "$K/include/config/kernel.release")
M="make -C $K LLVM=1 LLVM_IAS=1 CC=clang"
# The menu that boots is Void's grub (/mnt/void, nvme0n1p2): its /etc/grub.d/15_gentoo makes "Gentoo Linux
# (runit)" from the newest kernel in this /boot. Gentoo's own grub.cfg is not used. Regenerate Void's menu too.
VOID=/mnt/void
void_grub() {
	[ -x "$VOID/etc/grub.d/15_gentoo" ] || { grub-mkconfig -o /boot/grub/grub.cfg; return; }
	grub-mkconfig -o /boot/grub/grub.cfg >/dev/null 2>&1 || true
	cp "$VOID/boot/grub/grub.cfg" "$VOID/boot/grub/grub.cfg.pre-$V" 2>/dev/null || true
	mount --rbind /dev "$VOID/dev" && mount --make-rslave "$VOID/dev"
	mount -t proc proc "$VOID/proc"
	mount --rbind /sys "$VOID/sys" && mount --make-rslave "$VOID/sys"
	if chroot "$VOID" grub-mkconfig -o /boot/grub/grub.cfg; then r=0; else r=1; fi
	umount -R "$VOID/sys" "$VOID/proc" "$VOID/dev"
	[ $r = 0 ] || { echo "Void grub-mkconfig failed (old menu kept: $VOID/boot/grub/grub.cfg.pre-$V)"; exit 1; }
	grep -A7 "Gentoo Linux (runit)" "$VOID/boot/grub/grub.cfg" | grep -m1 'linux /boot'
}
case "$V" in *-optimized) ;; *) echo "unexpected kernel release '$V'"; exit 1 ;; esac

if [ "$1" = --grub ]; then   # only the boot menu (kernel already installed)
	void_grub
	exit 0
fi

if [ "$1" = --remove ]; then
	rm -f "/boot/vmlinuz-$V" "/boot/System.map-$V" "/boot/config-$V" "/boot/initramfs-$V.img"
	rm -rf "/lib/modules/$V"
	void_grub
	echo "removed $V"
	exit 0
fi

[ -f "$K/arch/x86/boot/bzImage" ] || { echo "not built: $K"; exit 1; }
for m in nvidia nvidia-modeset nvidia-drm nvidia-uvm nvidia-peermem; do
	[ -f "$NV/$m.ko" ] || { echo "NVIDIA module not built: $NV/$m.ko"; exit 1; }
done
echo "installing $V"
$M INSTALL_MOD_STRIP=1 modules_install >/dev/null
mkdir -p "/lib/modules/$V/video"
for m in nvidia nvidia-modeset nvidia-drm nvidia-uvm nvidia-peermem; do
	install -m 644 "$NV/$m.ko" "/lib/modules/$V/video/$m.ko"
done
depmod "$V"
install -m 644 "$K/arch/x86/boot/bzImage" "/boot/vmlinuz-$V"
install -m 644 "$K/System.map" "/boot/System.map-$V"
install -m 644 "$K/.config" "/boot/config-$V"
dracut --force --kver "$V" "/boot/initramfs-$V.img"
void_grub
echo
echo "done: $V. Reboot. If it does not start, pick \"Advanced options for Gentoo Linux\" -> 7.2.9-eclipse (runit) in grub,"
echo "then: sudo $0 --remove"
