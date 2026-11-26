/* rice-widget-fade: hides the desktop widgets while windows are open on their monitor, through the compositor:
 * sets _NET_WM_WINDOW_OPACITY 0 on the shell's widget windows (and removes it again). The widgets never re-render
 * (changing a dozen GL windows at once stalled X for ~150 ms per tag switch). Reads dwm's root _RICE_MONS
 * (per monitor: x y viewed-mask occupied-mask). Settings > Auto-hide widgets ("autoHide": false in
 * ~/.config/rice/desktop.json) turns it off.
 * C rewrite of the bash version (2026-11-26: bash + xprop -spy + xdotool/xprop runs every 3 s, ~1.5 MB -> ~0.2 MB),
 * same rules: widget = a window of the desktop shell's qs with _NET_WM_STATE_BELOW, wider than 8 px,
 * not covering a whole monitor; windows rescanned at most every 3 s; ends when no qs runs or X goes away, and
 * then shows every widget again. One copy runs ($XDG_RUNTIME_DIR/rice-widget-fade.lock). */
#include <ctype.h>
#include <dirent.h>
#include <fcntl.h>
#include <poll.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/file.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>
#include <X11/Xatom.h>
#include <X11/Xlib.h>
#include <X11/extensions/Xrandr.h>

#define MAXW 128
#define MAXM 16

typedef struct { Window w; int cx, cy; } Wid;
typedef struct { Window w; int state; } St;
typedef struct { int x, y, w, h; } Mon;

static Display *dpy;
static Window root;
static Atom a_mons, a_opacity, a_pid, a_state, a_below;
static Wid wins[MAXW];
static int nwins;
static St st[MAXW * 4];
static int nst;
static Mon mons[MAXM];
static int nmons;
static int autohide = 1;
static time_t cfg_mtime = -1;
static char cfg[4096];
static volatile sig_atomic_t quit;

static int xerr(Display *d, XErrorEvent *e) { (void)d; (void)e; return 0; }
static void onsig(int s) { (void)s; quit = 1; }

static double now(void)
{
	struct timespec t;
	clock_gettime(CLOCK_MONOTONIC, &t);
	return t.tv_sec + t.tv_nsec / 1e9;
}

/* the desktop shell: the newest "qs" running quickshell/rice-desktop; else the lowest pid named exactly "qs" (the
 * bash version's pgrep -x qs | head -1, which picked a Settings window when that was older). 0 if none. */
static int qs_pid(void)
{
	DIR *d = opendir("/proc");
	struct dirent *e;
	int low = 0, desk = 0;
	char p[64], comm[32], cmd[4096];
	if (!d) return 0;
	while ((e = readdir(d))) {
		FILE *f;
		int pid;
		size_t n, i;
		if (!isdigit((unsigned char)e->d_name[0])) continue;
		pid = atoi(e->d_name);
		snprintf(p, sizeof p, "/proc/%d/comm", pid);
		if (!(f = fopen(p, "r"))) continue;
		if (!fgets(comm, sizeof comm, f) || strcmp(comm, "qs\n")) { fclose(f); continue; }
		fclose(f);
		if (!low || pid < low) low = pid;
		snprintf(p, sizeof p, "/proc/%d/cmdline", pid);
		if (!(f = fopen(p, "r"))) continue;
		n = fread(cmd, 1, sizeof cmd - 1, f);
		fclose(f);
		for (i = 0; i < n; i++) if (!cmd[i]) cmd[i] = ' ';
		cmd[n] = 0;
		if (strstr(cmd, "quickshell/rice-desktop") && pid > desk) desk = pid;
	}
	closedir(d);
	return desk ? desk : low;
}

static void read_cfg(void)
{
	struct stat s;
	FILE *f;
	char *buf, *p;
	long n;
	if (stat(cfg, &s) != 0) { if (cfg_mtime != 0) { cfg_mtime = 0; autohide = 1; } return; }
	if (s.st_mtime == cfg_mtime) return;
	cfg_mtime = s.st_mtime;
	autohide = 1;
	if (!(f = fopen(cfg, "r"))) return;
	fseek(f, 0, SEEK_END);
	n = ftell(f);
	rewind(f);
	if (n > 0 && (buf = malloc(n + 1))) {
		n = (long)fread(buf, 1, n, f);
		buf[n] = 0;
		/* "autoHide": *false */
		for (p = buf; (p = strstr(p, "\"autoHide\":")); p++) {
			char *q = p + 11;
			while (*q == ' ') q++;
			if (!strncmp(q, "false", 5)) autohide = 0;
		}
		free(buf);
	}
	fclose(f);
}

static void scan_mons(void)
{
	int n, i;
	XRRMonitorInfo *m = XRRGetMonitors(dpy, root, True, &n);
	nmons = 0;
	for (i = 0; m && i < n && nmons < MAXM; i++)
		mons[nmons++] = (Mon){ m[i].x, m[i].y, m[i].width, m[i].height };
	if (m) XRRFreeMonitors(m);
}

static int has_below(Window w)
{
	Atom type;
	int fmt, r = 0;
	unsigned long n, after, i;
	unsigned char *d = NULL;
	if (XGetWindowProperty(dpy, w, a_state, 0, 64, False, XA_ATOM, &type, &fmt, &n, &after, &d) == Success && d) {
		for (i = 0; i < n; i++) if (((Atom *)d)[i] == a_below) r = 1;
		XFree(d);
	}
	return r;
}

static long win_pid(Window w)
{
	Atom type;
	int fmt;
	unsigned long n, after;
	unsigned char *d = NULL;
	long pid = 0;
	if (XGetWindowProperty(dpy, w, a_pid, 0, 1, False, XA_CARDINAL, &type, &fmt, &n, &after, &d) == Success && d) {
		if (n) pid = ((long *)d)[0];
		XFree(d);
	}
	return pid;
}

static void consider(Window w)
{
	XWindowAttributes a;
	int x, y, i;
	Window child;
	if (nwins >= MAXW || !has_below(w)) return;
	if (!XGetWindowAttributes(dpy, w, &a) || a.width <= 8) return;
	XTranslateCoordinates(dpy, w, root, 0, 0, &x, &y, &child);
	for (i = 0; i < nmons; i++)   /* the wallpaper window covers a whole monitor: not a widget */
		if (x == mons[i].x && y == mons[i].y && a.width >= mons[i].w && a.height >= mons[i].h) return;
	wins[nwins++] = (Wid){ w, x + a.width / 2, y + a.height / 2 };
}

/* every window, at any depth, whose _NET_WM_PID is pid (xdotool search --pid) */
static void walk(Window w, long pid)
{
	Window r, p, *kids = NULL;
	unsigned int n, i;
	if (win_pid(w) == pid) consider(w);
	if (!XQueryTree(dpy, w, &r, &p, &kids, &n)) return;
	for (i = 0; i < n; i++) walk(kids[i], pid);
	if (kids) XFree(kids);
}

static double lastscan;
static void scan_wins(void)
{
	int q = qs_pid();
	if (!q) return;
	nwins = 0;
	walk(root, q);
	lastscan = now();
}

static int *state_of(Window w)
{
	int i;
	for (i = 0; i < nst; i++) if (st[i].w == w) return &st[i].state;
	if (nst == (int)(sizeof st / sizeof *st)) nst = 0;   /* forget old windows */
	st[nst] = (St){ w, -1 };
	return &st[nst++].state;
}

static void apply(void)
{
	Atom type;
	int fmt, i, k;
	unsigned long n = 0, after;
	unsigned char *d = NULL;
	long *f = NULL;
	if (XGetWindowProperty(dpy, root, a_mons, 0, 1024, False, AnyPropertyType, &type, &fmt, &n, &after, &d) == Success
	    && d && fmt == 32)
		f = (long *)d;
	else
		n = 0;
	for (i = 0; i < nwins; i++) {
		int want = 0, *s;
		for (k = 0; k < nmons; k++) {
			Mon *m = &mons[k];
			unsigned long j;
			if (wins[i].cx < m->x || wins[i].cx >= m->x + m->w || wins[i].cy < m->y || wins[i].cy >= m->y + m->h)
				continue;
			for (j = 0; autohide && f && j + 3 < n; j += 4)
				if (f[j] == m->x && f[j + 1] == m->y && (f[j + 2] & f[j + 3])) want = 1;
		}
		s = state_of(wins[i].w);
		if (*s == want) continue;
		*s = want;
		if (want) {
			long zero = 0;
			XChangeProperty(dpy, wins[i].w, a_opacity, XA_CARDINAL, 32, PropModeReplace, (unsigned char *)&zero, 1);
		} else
			XDeleteProperty(dpy, wins[i].w, a_opacity);
	}
	if (d) XFree(d);
	XFlush(dpy);
}

static void cleanup(void)
{
	int i;
	for (i = 0; i < nwins; i++) XDeleteProperty(dpy, wins[i].w, a_opacity);
	XFlush(dpy);
}

static int xioerr(Display *d) { (void)d; _exit(0); }   /* X went away: nothing to show again */

int main(int argc, char **argv)
{
	char lock[4096];
	const char *rt = getenv("XDG_RUNTIME_DIR"), *home = getenv("HOME");
	int fd;
	struct pollfd p;
	struct sigaction sa = { 0 };

	if (argc > 1 && !strcmp(argv[1], "--list")) {   /* the widget windows it would fade, then exit */
		int i;
		if (!(dpy = XOpenDisplay(NULL))) return 1;
		root = DefaultRootWindow(dpy);
		a_pid = XInternAtom(dpy, "_NET_WM_PID", False);
		a_state = XInternAtom(dpy, "_NET_WM_STATE", False);
		a_below = XInternAtom(dpy, "_NET_WM_STATE_BELOW", False);
		XSetErrorHandler(xerr);
		scan_mons();
		scan_wins();
		for (i = 0; i < nwins; i++) printf("%lu %d %d\n", wins[i].w, wins[i].cx, wins[i].cy);
		return 0;
	}
	snprintf(lock, sizeof lock, "%s/rice-widget-fade.lock", rt ? rt : "/tmp");
	if ((fd = open(lock, O_WRONLY | O_CREAT | O_CLOEXEC, 0600)) < 0 || flock(fd, LOCK_EX | LOCK_NB)) return 0;
	snprintf(cfg, sizeof cfg, "%s/.config/rice/desktop.json", home ? home : "");
	if (!(dpy = XOpenDisplay(NULL))) return 1;
	XSetErrorHandler(xerr);
	XSetIOErrorHandler(xioerr);
	sa.sa_handler = onsig;
	sigaction(SIGTERM, &sa, NULL);
	sigaction(SIGINT, &sa, NULL);
	sigaction(SIGHUP, &sa, NULL);
	root = DefaultRootWindow(dpy);
	a_mons = XInternAtom(dpy, "_RICE_MONS", False);
	a_opacity = XInternAtom(dpy, "_NET_WM_WINDOW_OPACITY", False);
	a_pid = XInternAtom(dpy, "_NET_WM_PID", False);
	a_state = XInternAtom(dpy, "_NET_WM_STATE", False);
	a_below = XInternAtom(dpy, "_NET_WM_STATE_BELOW", False);
	XSelectInput(dpy, root, PropertyChangeMask);
	read_cfg();
	scan_mons();
	scan_wins();
	apply();
	p.fd = ConnectionNumber(dpy);
	p.events = POLLIN;
	while (!quit && qs_pid()) {
		int got = 0;
		if (!XPending(dpy)) poll(&p, 1, 1000);
		if (quit) break;
		while (XPending(dpy)) {
			XEvent ev;
			XNextEvent(dpy, &ev);
			if (ev.type == PropertyNotify && ev.xproperty.atom == a_mons) got = 1;
		}
		if (got ? now() - lastscan > 3 : now() - lastscan >= 3) scan_wins();
		read_cfg();
		apply();
	}
	cleanup();
	return 0;
}
