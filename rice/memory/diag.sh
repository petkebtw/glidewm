#!/bin/sh
# read-only: what the root side of the session holds (run with sudo)
for n in X Xorg sddm sddm-helper polkitd elogind-daemon udevd systemd-udevd upowerd dbus-daemon; do
  for p in $(pgrep -x "$n"); do
    printf '%-14s pid %-6s ' "$n" "$p"
    awk '/^Rss:/{r=$2} /^Pss_Anon:/{a=$2} /^AnonHugePages:/{h=$2} END{printf "rss %d MB  anon %d MB  hugepages %d MB\n", r/1024, a/1024, h/1024}' /proc/$p/smaps_rollup
  done
done
echo "--- biggest slab caches (MB)"
awk 'NR>2 {printf "%7.1f %s\n", $3*$4/1048576, $1}' /proc/slabinfo | sort -rn | head -12
echo "--- vmalloc by caller (MB)"
awk '{s[$3]+=$2} END{for(k in s) if(s[k]>2097152) printf "%7.1f %s\n", s[k]/1048576, k}' /proc/vmallocinfo | sort -rn | head -8
