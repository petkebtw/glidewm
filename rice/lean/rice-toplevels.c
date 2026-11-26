/* rice-toplevels: X11 window list for the Quickshell port (the X11 stand-in for Quickshell.Wayland's
 * ToplevelManager). C rewrite of the Python version (2026-11-26: ~6 MB of Python heap -> well under 1 MB),
 * same output line for line.
 *
 * rice-toplevels          print JSON lines {"active": id, "wins": [[id, "class", "title"], ...]} at start and
 *                         whenever dwm's client list (_NET_CLIENT_LIST) or the active window changes;
 *                         {"hover": [tag, x, y, monitor, window ids ...]} when the pointer moves onto a tag of dwm's
 *                         bar (root _RICE_HOVER; [] when it leaves the tags): the TagPeek card
 * rice-toplevels close ID ask window ID to close (WM_DELETE_WINDOW, as Mod+Shift+c does)
 *
 * Activating a window is dwm IPC 9: xprop -root -f _RICE_CMD 32c -set _RICE_CMD "9, ID". Ids are decimal. */
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/prctl.h>
#include <X11/Xatom.h>
#include <X11/Xlib.h>
#include <X11/Xutil.h>

typedef struct { Window w; char *cls, *title; int seen; } Win;

static Display *dpy;
static Window root;
static Atom a_list, a_active, a_hover, a_netname, a_utf8;
static Win *cache;
static int ncache;
static char *last;

static int xerr(Display *d, XErrorEvent *e) { (void)d; (void)e; return 0; }   /* a window that just went away */

/* a growing string */
typedef struct { char *s; size_t n, cap; } Buf;
static void put(Buf *b, const char *s, size_t n)
{
	if (b->n + n + 1 > b->cap) {
		b->cap = (b->n + n + 1) * 2;
		if (!(b->s = realloc(b->s, b->cap))) exit(1);
	}
	memcpy(b->s + b->n, s, n);
	b->n += n;
	b->s[b->n] = 0;
}
static void puts_(Buf *b, const char *s) { put(b, s, strlen(s)); }

/* one UTF-8 sequence at s (max n bytes): its length, 0 if invalid */
static int u8len(const unsigned char *s, size_t n)
{
	int l, i;
	unsigned c = s[0], cp;
	if (c < 0x80) return 1;
	if (c >= 0xc2 && c <= 0xdf) { l = 2; cp = c & 0x1f; }
	else if (c >= 0xe0 && c <= 0xef) { l = 3; cp = c & 0x0f; }
	else if (c >= 0xf0 && c <= 0xf4) { l = 4; cp = c & 0x07; }
	else return 0;
	if ((size_t)l > n) return 0;
	for (i = 1; i < l; i++) {
		if ((s[i] & 0xc0) != 0x80) return 0;
		cp = (cp << 6) | (s[i] & 0x3f);
	}
	if ((l == 3 && (cp < 0x800 || (cp >= 0xd800 && cp <= 0xdfff))) || (l == 4 && (cp < 0x10000 || cp > 0x10ffff)))
		return 0;
	return l;
}

/* a JSON string like Python's json.dumps(ensure_ascii=False); bad UTF-8 becomes U+FFFD */
static void jstr(Buf *b, const char *str)
{
	const unsigned char *s = (const unsigned char *)str;
	size_t n = strlen(str), i = 0;
	char e[8];
	puts_(b, "\"");
	while (i < n) {
		unsigned c = s[i];
		int l;
		if (c == '"') { puts_(b, "\\\""); i++; continue; }
		if (c == '\\') { puts_(b, "\\\\"); i++; continue; }
		if (c < 0x20) {
			switch (c) {
			case '\n': puts_(b, "\\n"); break;
			case '\r': puts_(b, "\\r"); break;
			case '\t': puts_(b, "\\t"); break;
			case '\b': puts_(b, "\\b"); break;
			case '\f': puts_(b, "\\f"); break;
			default: snprintf(e, sizeof e, "\\u%04x", c); puts_(b, e);
			}
			i++;
			continue;
		}
		if (!(l = u8len(s + i, n - i))) { puts_(b, "\xef\xbf\xbd"); i++; continue; }
		put(b, (const char *)s + i, l);
		i += l;
	}
	puts_(b, "\"");
}

/* a text property as UTF-8 (STRING is Latin-1) */
static char *textprop(Window w, Atom prop)
{
	Atom type;
	int fmt;
	unsigned long n, after;
	unsigned char *d = NULL;
	char *out;
	if (XGetWindowProperty(dpy, w, prop, 0, 65536, False, AnyPropertyType, &type, &fmt, &n, &after, &d) != Success
	    || !d || fmt != 8) {
		if (d) XFree(d);
		return NULL;
	}
	if (type == XA_STRING) {
		size_t i, k = 0;
		out = malloc(n * 2 + 1);
		for (i = 0; i < n; i++) {
			if (d[i] < 0x80) out[k++] = d[i];
			else { out[k++] = 0xc0 | (d[i] >> 6); out[k++] = 0x80 | (d[i] & 0x3f); }
		}
		out[k] = 0;
	} else {
		out = malloc(n + 1);
		memcpy(out, d, n);
		out[n] = 0;
	}
	XFree(d);
	return out;
}

static void info(Win *c)
{
	XClassHint h = { 0 };
	char *t;
	c->cls = NULL;
	if (XGetClassHint(dpy, c->w, &h)) {
		/* the class (2nd string), else the instance */
		c->cls = strdup(h.res_class && *h.res_class ? h.res_class : (h.res_name ? h.res_name : ""));
		if (h.res_name) XFree(h.res_name);
		if (h.res_class) XFree(h.res_class);
	}
	if (!c->cls) c->cls = strdup("");
	t = textprop(c->w, a_netname);
	if (!t || !*t) { free(t); t = textprop(c->w, XA_WM_NAME); }
	c->title = t ? t : strdup("");
}

static long *cards(Window w, Atom prop, unsigned long *n)
{
	Atom type;
	int fmt;
	unsigned long after;
	unsigned char *d = NULL;
	*n = 0;
	if (XGetWindowProperty(dpy, w, prop, 0, 4096, False, AnyPropertyType, &type, &fmt, n, &after, &d) != Success
	    || !d || fmt != 32) {
		if (d) XFree(d);
		*n = 0;
		return NULL;
	}
	return (long *)d;
}

static void emit(const char *s)
{
	fputs(s, stdout);
	fputc('\n', stdout);
	if (fflush(stdout) == EOF) exit(0);
}

static void hover(void)
{
	unsigned long n, i;
	long *h = cards(root, a_hover, &n);
	char num[32];
	Buf b = { 0 };
	puts_(&b, "{\"hover\": [");
	if (h && n && h[0] > 0)
		for (i = 0; i < n; i++) {
			snprintf(num, sizeof num, "%s%lu", i ? ", " : "", (unsigned long)h[i]);
			puts_(&b, num);
		}
	puts_(&b, "]}");
	if (h) XFree(h);
	emit(b.s);
	free(b.s);
}

static void wins(int refocus)
{
	unsigned long n = 0, na = 0, i;
	long *l = cards(root, a_list, &n), *a = cards(root, a_active, &na);
	Window active = a && na ? (Window)(unsigned long)a[0] : 0;
	char num[48];
	Buf b = { 0 };
	int k;

	/* the focused window's title is read again; windows no longer listed leave the cache */
	for (k = 0; k < ncache; k++) {
		int keep = 0;
		for (i = 0; i < n; i++) if ((Window)(unsigned long)l[i] == cache[k].w) keep = 1;
		if (!keep || (refocus && cache[k].w == active)) {
			free(cache[k].cls);
			free(cache[k].title);
			cache[k--] = cache[--ncache];
		}
	}
	snprintf(num, sizeof num, "{\"active\": %lu, \"wins\": [", (unsigned long)active);
	puts_(&b, num);
	for (i = 0; i < n; i++) {
		Window w = (Window)(unsigned long)l[i];
		Win *c = NULL;
		for (k = 0; k < ncache; k++) if (cache[k].w == w) c = &cache[k];
		if (!c) {
			if (!(cache = realloc(cache, (ncache + 1) * sizeof *cache))) exit(1);
			c = &cache[ncache++];
			c->w = w;
			info(c);
		}
		snprintf(num, sizeof num, "%s[%lu, ", i ? ", " : "", (unsigned long)w);
		puts_(&b, num);
		jstr(&b, c->cls);
		puts_(&b, ", ");
		jstr(&b, c->title);
		puts_(&b, "]");
	}
	puts_(&b, "]}");
	if (l) XFree(l);
	if (a) XFree(a);
	if (!last || strcmp(last, b.s)) {
		free(last);
		last = b.s;
		emit(b.s);
	} else
		free(b.s);
}

static int closewin(const char *id)
{
	XEvent ev = { 0 };
	Window w = strtoul(id, NULL, 0);
	if (!(dpy = XOpenDisplay(NULL))) return 1;
	ev.xclient.type = ClientMessage;
	ev.xclient.window = w;
	ev.xclient.message_type = XInternAtom(dpy, "WM_PROTOCOLS", False);
	ev.xclient.format = 32;
	ev.xclient.data.l[0] = XInternAtom(dpy, "WM_DELETE_WINDOW", False);
	ev.xclient.data.l[1] = CurrentTime;
	XSendEvent(dpy, w, False, NoEventMask, &ev);
	XFlush(dpy);
	XCloseDisplay(dpy);
	return 0;
}

int main(int argc, char **argv)
{
	XEvent ev;

	if (argc > 2 && !strcmp(argv[1], "close")) return closewin(argv[2]);
	prctl(PR_SET_PDEATHSIG, SIGTERM);   /* qs killed: this goes too */
	if (!(dpy = XOpenDisplay(NULL))) return 1;
	XSetErrorHandler(xerr);
	root = DefaultRootWindow(dpy);
	a_list = XInternAtom(dpy, "_NET_CLIENT_LIST", False);
	a_active = XInternAtom(dpy, "_NET_ACTIVE_WINDOW", False);
	a_hover = XInternAtom(dpy, "_RICE_HOVER", False);
	a_netname = XInternAtom(dpy, "_NET_WM_NAME", False);
	a_utf8 = XInternAtom(dpy, "UTF8_STRING", False);
	XSelectInput(dpy, root, PropertyChangeMask);
	/* at start, in xprop -spy's order: the list, the active window, the hover state */
	wins(0);
	wins(1);
	hover();
	for (;;) {
		XNextEvent(dpy, &ev);
		if (ev.type != PropertyNotify || ev.xproperty.window != root) continue;
		if (ev.xproperty.atom == a_hover) hover();
		else if (ev.xproperty.atom == a_list) wins(0);
		else if (ev.xproperty.atom == a_active) wins(1);
	}
}
