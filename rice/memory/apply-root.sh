#!/bin/sh
# glidewm memory, the root part (2026-11-26). Run: sudo ~/dwm/rice/memory/apply-root.sh   (undo: --undo)
#
# 1. runit never applied /etc/sysctl.d (stage 1 has no `sysctl --system`): swappiness 10 and the game
#    vm.max_map_count were not in effect. Adds `sysctl --system` to /etc/runit/1.
# 2. /etc/sysctl.d/90-glidewm-memory.conf: the kernel's free-memory reserves back to the size it picks without
#    transparent huge pages. THP "always" raised min_free_kbytes from ~22 MB to 66 MB, and the DMA32 zone kept
#    117 MB away from normal allocations; both count as "used" in free/fastfetch (MemAvailable), ~230 MB.
# 3. Xorg starts without transparent huge pages (sddm [X11] ServerPath -> /usr/local/bin/X-nothp, which runs
#    /usr/bin/X through nothp and falls back to plain /usr/bin/X if nothp is missing).
# 4. /etc/X11/xorg.conf.d/10-glidewm-noautogpu.conf: AutoAddGPU off. With nvidia_drm.modeset=1, Xorg added the
#    same RTX card a second time as a "modesetting" GPU screen (three times per start, /dev/dri/card1), set up
#    glamor (a GL context inside X) each time and then failed drmSetMaster. One GPU here: nothing is lost.
set -e
[ "$(id -u)" = 0 ] || { echo "run with sudo"; exit 1; }
HERE=$(cd "$(dirname "$0")" && pwd)
SYS=/etc/sysctl.d/90-glidewm-memory.conf
SDDM=/etc/sddm.conf.d/20-glidewm-memory.conf
WRAP=/usr/local/bin/X-nothp
XCONF=/etc/X11/xorg.conf.d/10-glidewm-noautogpu.conf
MARK="# glidewm: apply /etc/sysctl.d"

if [ "$1" = --undo ]; then
	rm -f "$SYS" "$SDDM" "$WRAP" "$XCONF"
	[ -f /etc/runit/1.pre-glidewm ] && cp /etc/runit/1.pre-glidewm /etc/runit/1
	echo "undone (min_free_kbytes and the X wrapper go back at the next boot)"
	exit 0
fi

# nothp (root-owned copy, Xorg runs it)
[ -x "$HERE/../lean/nothp" ] || cc -O2 -o "$HERE/../lean/nothp" "$HERE/../lean/nothp.c"
install -m 755 "$HERE/../lean/nothp" /usr/local/bin/nothp
/usr/local/bin/nothp true || { echo "nothp does not run"; exit 1; }

# 1
if ! grep -q "$MARK" /etc/runit/1; then
	[ -f /etc/runit/1.pre-glidewm ] || cp /etc/runit/1 /etc/runit/1.pre-glidewm
	printf '\n%s (runit stage 1 did not)\nsysctl --system >/dev/null 2>&1\n' "$MARK" >> /etc/runit/1
fi

# 2
cat > "$SYS" <<'EOF2'
# glidewm (rice/memory/apply-root.sh): the reserves the kernel picks without transparent huge pages.
# THP "always" raised min_free_kbytes to 67584; 22528 is the kernel's own default for 32 GB.
vm.min_free_kbytes = 22528
# DMA32 (the low 4 GB) kept 1/256 of normal memory (117 MB) away from normal allocations; 1/2048 is 15 MB.
# The 16 MB ISA DMA zone was fully reserved (1/256); 1/32768 keeps 1 MB.
vm.lowmem_reserve_ratio = 32768 2048 32 0 0
EOF2

# 3
cat > "$WRAP" <<'EOF2'
#!/bin/sh
# Xorg without transparent huge pages (glidewm, rice/memory/apply-root.sh); plain X if nothp is gone
[ -x /usr/local/bin/nothp ] && exec /usr/local/bin/nothp /usr/bin/X "$@"
exec /usr/bin/X "$@"
EOF2
chmod 755 "$WRAP"
mkdir -p /etc/sddm.conf.d
printf '[X11]\n# glidewm: Xorg without transparent huge pages (rice/memory/apply-root.sh)\nServerPath=%s\n' "$WRAP" > "$SDDM"

# 4
cat > "$XCONF" <<'EOF2'
# glidewm (rice/memory/apply-root.sh): do not add the NVIDIA card again as a modesetting GPU screen (it set up
# glamor inside X three times per start and failed drmSetMaster). Remove this file for PRIME / a second GPU.
Section "ServerFlags"
    Option "AutoAddGPU" "false"
EndSection
EOF2

sysctl --system >/dev/null 2>&1 || true
echo "done. Now: swappiness $(cat /proc/sys/vm/swappiness), max_map_count $(cat /proc/sys/vm/max_map_count), min_free_kbytes $(cat /proc/sys/vm/min_free_kbytes)"
echo "Xorg runs through $WRAP and without the extra modesetting screen from the next login screen on (reboot to measure)."
