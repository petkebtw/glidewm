/* rice-busy SCREEN: prints 1 while the viewed tag(s) of that output (e.g. DP-4) have windows, 0 when its desktop
 * is empty (changes only). Reads dwm's root _RICE_MONS (per monitor: x, y, viewed mask, occupied mask); falls back
 * to _RICE_TAGS. C rewrite of the bash version (2026-11-26: bash + xprop -spy + a watchdog subshell, ~1.5 MB ->
 * ~0.2 MB). Ends with the shell that started it (PR_SET_PDEATHSIG). */
#include <signal.h>
#include <stdio.h>
#include <string.h>
#include <sys/prctl.h>
#include <X11/Xlib.h>
#include <X11/extensions/Xrandr.h>

static Display *dpy;
static Window root;
static Atom a_mons, a_tags;

static int xerr(Display *d, XErrorEvent *e) { (void)d; (void)e; return 0; }

static long *cards(Atom prop, unsigned long *n)
{
	Atom type;
	int fmt;
	unsigned long after;
	unsigned char *d = NULL;
	*n = 0;
	if (XGetWindowProperty(dpy, root, prop, 0, 1024, False, AnyPropertyType, &type, &fmt, n, &after, &d) != Success
	    || !d || fmt != 32) {
		if (d) XFree(d);
		*n = 0;
		return NULL;
	}
	return (long *)d;
}

/* the origin of the monitor whose output (or monitor) name is scr, as `xrandr --listmonitors` shows it */
static void origin(const char *scr, int *ox, int *oy)
{
	int n, i, k;
	XRRMonitorInfo *m = XRRGetMonitors(dpy, root, True, &n);
	XRRScreenResources *res = XRRGetScreenResourcesCurrent(dpy, root);
	*ox = *oy = 0;
	for (i = 0; m && i < n; i++) {
		int hit = 0;
		char *name = XGetAtomName(dpy, m[i].name);
		if (name && !strcmp(name, scr)) hit = 1;
		if (name) XFree(name);
		for (k = 0; !hit && res && k < m[i].noutput; k++) {
			XRROutputInfo *o = XRRGetOutputInfo(dpy, res, m[i].outputs[k]);
			if (o && !strcmp(o->name, scr)) hit = 1;
			if (o) XRRFreeOutputInfo(o);
		}
		if (hit) { *ox = m[i].x; *oy = m[i].y; break; }
	}
	if (res) XRRFreeScreenResources(res);
	if (m) XRRFreeMonitors(m);
}

int main(int argc, char **argv)
{
	int ox, oy, last = -1;
	XEvent ev;

	prctl(PR_SET_PDEATHSIG, SIGTERM);
	if (!(dpy = XOpenDisplay(NULL))) return 1;
	XSetErrorHandler(xerr);
	root = DefaultRootWindow(dpy);
	a_mons = XInternAtom(dpy, "_RICE_MONS", False);
	a_tags = XInternAtom(dpy, "_RICE_TAGS", False);
	origin(argc > 1 ? argv[1] : "", &ox, &oy);
	XSelectInput(dpy, root, PropertyChangeMask);
	for (;;) {
		unsigned long n, i;
		int b = 0;
		long *f = cards(a_mons, &n);
		if (f && n) {
			for (i = 0; i + 3 < n; i += 4)
				if (f[i] == ox && f[i + 1] == oy && (f[i + 2] & f[i + 3])) b = 1;
		} else {
			long *t;
			if (f) XFree(f);
			f = NULL;
			t = cards(a_tags, &n);
			/* no _RICE_TAGS: view 1, nothing occupied */
			if (t && n >= 2 && (t[0] & t[1])) b = 1;
			if (t) XFree(t);
		}
		if (f) XFree(f);
		if (b != last) {
			last = b;
			printf("%d\n", b);
			if (fflush(stdout) == EOF) return 0;
		}
		do {
			XNextEvent(dpy, &ev);
		} while (ev.type != PropertyNotify ||
		         (ev.xproperty.atom != a_mons && ev.xproperty.atom != a_tags));
	}
}
