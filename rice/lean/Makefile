# glidewm lean helpers (2026-11-26): C versions of the resident rice daemons (~45 MB less at login), and nothp
# (runs a program without transparent huge pages). rice/install.sh builds them; rice/bin and shell/ours link here.
CFLAGS ?= -O2 -Wall -Wextra
PROGS = nothp rice-toplevels clip-daemon polkit-agent rice-busy rice-wm-watch rice-widget-fade rice-cava dwm-status \
        rice-supervise

all: $(PROGS)

nothp: nothp.c
	$(CC) $(CFLAGS) -o $@ $<
rice-toplevels: rice-toplevels.c
	$(CC) $(CFLAGS) -o $@ $< $$(pkg-config --cflags --libs x11)
clip-daemon: clip-daemon.c
	$(CC) $(CFLAGS) -o $@ $< $$(pkg-config --cflags --libs x11 xfixes)
polkit-agent: polkit-agent.c
	$(CC) $(CFLAGS) -o $@ $< $$(pkg-config --cflags --libs polkit-agent-1)
rice-busy: rice-busy.c
	$(CC) $(CFLAGS) -o $@ $< $$(pkg-config --cflags --libs x11 xrandr)
rice-wm-watch: rice-wm-watch.c
	$(CC) $(CFLAGS) -o $@ $< $$(pkg-config --cflags --libs x11)
rice-widget-fade: rice-widget-fade.c
	$(CC) $(CFLAGS) -o $@ $< $$(pkg-config --cflags --libs x11 xrandr)
rice-cava: rice-cava.c
	$(CC) $(CFLAGS) -o $@ $<
dwm-status: dwm-status.c
	$(CC) $(CFLAGS) -o $@ $< $$(pkg-config --cflags --libs x11)
rice-supervise: rice-supervise.c
	$(CC) $(CFLAGS) -o $@ $<

clean:
	rm -f $(PROGS)
.PHONY: all clean
