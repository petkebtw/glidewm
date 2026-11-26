/* rice-wm-watch: dwm state as JSON lines for the Quickshell port:
 *   {"view":mask,"occ":mask,"urg":mask,"mon":n,"title":"..","class":".."}
 * once at start, whenever _RICE_TAGS or the active window change, and every 2 s (title changes).
 * C rewrite of the bash version (2026-11-26: bash x4 + xprop -spy + a watchdog, ~2 MB -> ~0.2 MB). The title
 * is now plain JSON (bash passed xprop's own escapes through, so a '"' in a title showed as '\"').
 * Ends with the shell that started it (PR_SET_PDEATHSIG). */
#include <poll.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/prctl.h>
#include <time.h>
#include <X11/Xatom.h>
#include <X11/Xlib.h>
#include <X11/Xutil.h>

static Display *dpy;
static Window root;
static Atom a_tags, a_active, a_netname;

static int xerr(Display *d, XErrorEvent *e) { (void)d; (void)e; return 0; }

static unsigned char *prop(Window w, Atom p, int want_fmt, unsigned long *n)
{
	Atom type;
	int fmt;
	unsigned long after;
	unsigned char *d = NULL;
	*n = 0;
	if (XGetWindowProperty(dpy, w, p, 0, 65536, False, AnyPropertyType, &type, &fmt, n, &after, &d) != Success
	    || !d || fmt != want_fmt) {
		if (d) XFree(d);
		*n = 0;
		return NULL;
	}
	return d;
}

/* a JSON string body; bad UTF-8 bytes become U+FFFD */
static void jput(const unsigned char *s, size_t n)
{
	size_t i = 0;
	while (i < n) {
		unsigned c = s[i];
		int l = 0, k;
		if (c == '"' || c == '\\') { putchar('\\'); putchar(c); i++; continue; }
		if (c < 0x20) { printf(c == '\n' ? "\\n" : c == '\t' ? "\\t" : "\\u%04x", c); i++; continue; }
		if (c < 0x80) { putchar(c); i++; continue; }
		if (c >= 0xc2 && c <= 0xdf) l = 2; else if (c >= 0xe0 && c <= 0xef) l = 3; else if (c >= 0xf0 && c <= 0xf4) l = 4;
		for (k = 1; l && k < l; k++) if (i + k >= n || (s[i + k] & 0xc0) != 0x80) l = 0;
		if (!l) { fputs("\xef\xbf\xbd", stdout); i++; continue; }
		fwrite(s + i, 1, l, stdout);
		i += l;
	}
}

static void emit(void)
{
	unsigned long n = 0, na = 0, nt = 0;
	long *t = (long *)prop(root, a_tags, 32, &n);
	long *a = (long *)prop(root, a_active, 32, &na);
	long v = n > 0 ? t[0] : 1, o = n > 1 ? t[1] : 0, u = n > 2 ? t[2] : 0, m = n > 3 ? t[3] : 0;
	Window w = a && na ? (Window)(unsigned long)a[0] : 0;
	unsigned char *title = NULL;
	XClassHint h = { 0 };

	if (w) {
		title = prop(w, a_netname, 8, &nt);
		XGetClassHint(dpy, w, &h);
	}
	printf("{\"view\":%lu,\"occ\":%lu,\"urg\":%lu,\"mon\":%lu,\"title\":\"", (unsigned long)v, (unsigned long)o,
	       (unsigned long)u, (unsigned long)m);
	if (title) jput(title, nt);
	fputs("\",\"class\":\"", stdout);
	if (h.res_class) jput((unsigned char *)h.res_class, strlen(h.res_class));
	fputs("\"}\n", stdout);
	if (fflush(stdout) == EOF) exit(0);
	if (title) XFree(title);
	if (h.res_name) XFree(h.res_name);
	if (h.res_class) XFree(h.res_class);
	if (t) XFree(t);
	if (a) XFree(a);
}

static long long now_ms(void)
{
	struct timespec ts;
	clock_gettime(CLOCK_MONOTONIC, &ts);
	return ts.tv_sec * 1000LL + ts.tv_nsec / 1000000;
}

int main(void)
{
	struct pollfd p;
	long long next;

	prctl(PR_SET_PDEATHSIG, SIGTERM);
	if (!(dpy = XOpenDisplay(NULL))) return 1;
	XSetErrorHandler(xerr);
	root = DefaultRootWindow(dpy);
	a_tags = XInternAtom(dpy, "_RICE_TAGS", False);
	a_active = XInternAtom(dpy, "_NET_ACTIVE_WINDOW", False);
	a_netname = XInternAtom(dpy, "_NET_WM_NAME", False);
	XSelectInput(dpy, root, PropertyChangeMask);
	p.fd = ConnectionNumber(dpy);
	p.events = POLLIN;
	emit();
	next = now_ms() + 2000;
	for (;;) {
		long long left = next - now_ms();
		int changed = 0;
		XFlush(dpy);
		if (!XPending(dpy) && left > 0) poll(&p, 1, (int)left);
		while (XPending(dpy)) {
			XEvent ev;
			XNextEvent(dpy, &ev);
			if (ev.type == PropertyNotify && (ev.xproperty.atom == a_tags || ev.xproperty.atom == a_active))
				changed = 1;
		}
		if (changed) emit();
		if (now_ms() >= next) {   /* the 2 s poll: the title of the focused window */
			emit();
			next = now_ms() + 2000;
		}
	}
}
