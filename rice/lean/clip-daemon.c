/* clip-daemon: clipboard history (text + images) -> ~/.cache/clip/<time_ns>.txt|.png, newest 100 kept.
 * C rewrite of the GTK/Python version (2026-11-26: ~18 MB of Python and GTK heap -> about 1 MB), same files:
 * an image is stored when the clipboard offers one (image/png as is; another image type is converted to PNG
 * once by a short Python/GdkPixbuf run), else the text (UTF-8; an identical older entry is removed first).
 * Whitespace-only text and a repeat of the last entry are skipped. */
#define _GNU_SOURCE
#include <dirent.h>
#include <errno.h>
#include <poll.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>
#include <X11/Xatom.h>
#include <X11/Xlib.h>
#include <X11/extensions/Xfixes.h>

#define MAX 100
#define WAIT_MS 1500   /* an owner that does not answer within this is skipped */

static Display *dpy;
static Window win;
static Atom CLIPBOARD, TARGETS, INCR, PROP, UTF8, TEXTPLAIN_U8, TEXTPLAIN, PNG;
static char dir[4096];
static uint64_t last;

typedef struct { unsigned char *d; size_t n; Atom type; } Data;

static int xerr(Display *d, XErrorEvent *e) { (void)d; (void)e; return 0; }

static uint64_t hash(const unsigned char *d, size_t n)
{
	uint64_t h = 1469598103934665603ULL;
	while (n--) { h ^= *d++; h *= 1099511628211ULL; }
	return h;
}

static long long now_ms(void)
{
	struct timespec t;
	clock_gettime(CLOCK_MONOTONIC, &t);
	return t.tv_sec * 1000LL + t.tv_nsec / 1000000;
}

/* the next event on our window of this type, or 0 after the deadline */
static int waitev(int type, XEvent *ev, long long deadline)
{
	struct pollfd p = { ConnectionNumber(dpy), POLLIN, 0 };
	for (;;) {
		long long left;
		/* other events (a newer owner change) stay queued for the main loop */
		if (XCheckTypedWindowEvent(dpy, win, type, ev)) {
			if (type != PropertyNotify || (ev->xproperty.atom == PROP && ev->xproperty.state == PropertyNewValue))
				return 1;
			continue;
		}
		left = deadline - now_ms();
		if (left <= 0) return 0;
		if (poll(&p, 1, (int)left) < 0 && errno != EINTR) return 0;
		XEventsQueued(dpy, QueuedAfterReading);
	}
}

static int readprop(Data *out, int del)
{
	Atom type;
	int fmt;
	unsigned long n, after;
	unsigned char *d = NULL;
	size_t unit;
	if (XGetWindowProperty(dpy, win, PROP, 0, 0x7fffffff / 4, del, AnyPropertyType, &type, &fmt, &n, &after, &d)
	    != Success)
		return 0;
	unit = fmt == 32 ? sizeof(long) : (size_t)(fmt / 8);
	out->type = type;
	if (type == INCR) { if (d) XFree(d); out->n = 0; return 1; }
	out->d = realloc(out->d, out->n + n * unit + 1);
	if (n && d) memcpy(out->d + out->n, d, n * unit);
	out->n += n * unit;
	out->d[out->n] = 0;
	if (d) XFree(d);
	return 1;
}

/* the clipboard converted to target (INCR transfers included) */
static int fetch(Atom target, Data *out)
{
	XEvent ev;
	long long deadline = now_ms() + WAIT_MS;
	memset(out, 0, sizeof *out);
	XDeleteProperty(dpy, win, PROP);
	XConvertSelection(dpy, CLIPBOARD, target, PROP, win, CurrentTime);
	if (!waitev(SelectionNotify, &ev, deadline) || ev.xselection.property == None) return 0;
	if (!readprop(out, False)) return 0;
	if (out->type != INCR) { XDeleteProperty(dpy, win, PROP); XFlush(dpy); return 1; }
	/* large data comes in chunks: delete the property, take the next one, until an empty one */
	XDeleteProperty(dpy, win, PROP);
	XFlush(dpy);
	for (;;) {
		size_t before;
		if (!waitev(PropertyNotify, &ev, now_ms() + WAIT_MS)) { free(out->d); out->d = NULL; return 0; }
		before = out->n;
		if (!readprop(out, True)) { free(out->d); out->d = NULL; return 0; }
		XFlush(dpy);
		if (out->n == before) return 1;
	}
}

static void prune(void)
{
	struct dirent **e;
	int n = scandir(dir, &e, NULL, alphasort), i, keep = 0;
	char p[8192];
	if (n < 0) return;
	for (i = 0; i < n; i++) if (strcmp(e[i]->d_name, ".") && strcmp(e[i]->d_name, "..")) keep++;
	keep -= MAX;
	for (i = 0; i < n; i++) {
		if (keep > 0 && strcmp(e[i]->d_name, ".") && strcmp(e[i]->d_name, "..")) {
			snprintf(p, sizeof p, "%s/%s", dir, e[i]->d_name);
			unlink(p);
			keep--;
		}
		free(e[i]);
	}
	free(e);
}

static void newname(char *p, size_t len, const char *ext)
{
	struct timespec t;
	clock_gettime(CLOCK_REALTIME, &t);
	snprintf(p, len, "%s/%lld%09ld.%s", dir, (long long)t.tv_sec, t.tv_nsec, ext);
}

static int writefile(const char *p, const unsigned char *d, size_t n)
{
	FILE *f = fopen(p, "wb");
	if (!f) return 0;
	fwrite(d, 1, n, f);
	return fclose(f) == 0;
}

/* an image type other than PNG: GdkPixbuf turns it into a PNG (a short Python run, only in this rare case) */
static void convert(Data *d, const char *png)
{
	char tmp[8200];
	pid_t pid;
	snprintf(tmp, sizeof tmp, "%s.in", png);
	if (!writefile(tmp, d->d, d->n)) return;
	if ((pid = fork()) == 0) {
		execlp("python3", "python3", "-c",
		       "import sys, gi\n"
		       "gi.require_version('GdkPixbuf', '2.0')\n"
		       "from gi.repository import GdkPixbuf\n"
		       "GdkPixbuf.Pixbuf.new_from_file(sys.argv[1]).savev(sys.argv[2], 'png', [], [])\n",
		       tmp, png, (char *)NULL);
		_exit(127);
	}
	if (pid > 0) waitpid(pid, NULL, 0);
	unlink(tmp);
}

static int blank(const unsigned char *s, size_t n)
{
	while (n--) if (!strchr(" \t\n\r\v\f", *s++)) return 0;
	return 1;
}

static void dedupe(const unsigned char *t, size_t n)
{
	DIR *d = opendir(dir);
	struct dirent *e;
	char p[8192];
	if (!d) return;
	while ((e = readdir(d))) {
		size_t l = strlen(e->d_name);
		struct stat st;
		FILE *f;
		unsigned char *buf;
		if (l < 4 || strcmp(e->d_name + l - 4, ".txt")) continue;
		snprintf(p, sizeof p, "%s/%s", dir, e->d_name);
		if (stat(p, &st) || (size_t)st.st_size != n || !(f = fopen(p, "rb"))) continue;
		buf = malloc(n + 1);
		if (fread(buf, 1, n, f) == n && !memcmp(buf, t, n)) unlink(p);
		free(buf);
		fclose(f);
	}
	closedir(d);
}

static void changed(void)
{
	Data tg, d;
	Atom *a, img = None, txt = None;
	size_t i, n;
	char p[8192];

	if (!fetch(TARGETS, &tg)) return;
	a = (Atom *)tg.d;
	n = tg.n / sizeof(Atom);
	for (i = 0; i < n; i++) {
		char *name;
		if (a[i] == PNG) img = PNG;
		else if (img == None && (name = XGetAtomName(dpy, a[i]))) {
			if (!strncmp(name, "image/", 6)) img = a[i];
			XFree(name);
		}
	}
	/* text: UTF-8 first, then Latin-1 STRING, as GTK picks it */
	for (i = 0; i < n; i++) if (a[i] == UTF8) txt = UTF8;
	for (i = 0; i < n && txt == None; i++) if (a[i] == TEXTPLAIN_U8) txt = TEXTPLAIN_U8;
	for (i = 0; i < n && txt == None; i++) if (a[i] == XA_STRING) txt = XA_STRING;
	for (i = 0; i < n && txt == None; i++) if (a[i] == TEXTPLAIN) txt = TEXTPLAIN;
	free(tg.d);

	if (img != None) {
		uint64_t h;
		if (!fetch(img, &d) || !d.n) { free(d.d); return; }
		if ((h = hash(d.d, d.n)) == last) { free(d.d); return; }
		last = h;
		newname(p, sizeof p, "png");
		if (img == PNG) writefile(p, d.d, d.n);
		else convert(&d, p);
		free(d.d);
	} else if (txt != None) {
		uint64_t h;
		if (!fetch(txt, &d)) return;
		if (txt == XA_STRING) {   /* Latin-1 -> UTF-8 */
			unsigned char *u = malloc(d.n * 2 + 1);
			size_t k = 0;
			for (i = 0; i < d.n; i++) {
				if (d.d[i] < 0x80) u[k++] = d.d[i];
				else { u[k++] = 0xc0 | (d.d[i] >> 6); u[k++] = 0x80 | (d.d[i] & 0x3f); }
			}
			free(d.d);
			d.d = u;
			d.n = k;
		}
		if (!d.n || blank(d.d, d.n)) { free(d.d); return; }
		if ((h = hash(d.d, d.n)) == last) { free(d.d); return; }
		last = h;
		dedupe(d.d, d.n);
		newname(p, sizeof p, "txt");
		writefile(p, d.d, d.n);
		free(d.d);
	} else
		return;
	prune();
}

int main(void)
{
	int evbase, errbase;
	XEvent ev;
	const char *home = getenv("HOME");

	snprintf(dir, sizeof dir, "%s/.cache/clip", home ? home : ".");
	{
		char parent[4096];
		snprintf(parent, sizeof parent, "%s/.cache", home ? home : ".");
		mkdir(parent, 0700);
		mkdir(dir, 0700);
	}
	if (!(dpy = XOpenDisplay(NULL))) { fputs("clip-daemon: no display\n", stderr); return 1; }
	if (!XFixesQueryExtension(dpy, &evbase, &errbase)) { fputs("clip-daemon: no XFixes\n", stderr); return 1; }
	XSetErrorHandler(xerr);
	CLIPBOARD = XInternAtom(dpy, "CLIPBOARD", False);
	TARGETS = XInternAtom(dpy, "TARGETS", False);
	INCR = XInternAtom(dpy, "INCR", False);
	PROP = XInternAtom(dpy, "RICE_CLIP", False);
	UTF8 = XInternAtom(dpy, "UTF8_STRING", False);
	TEXTPLAIN_U8 = XInternAtom(dpy, "text/plain;charset=utf-8", False);
	TEXTPLAIN = XInternAtom(dpy, "text/plain", False);
	PNG = XInternAtom(dpy, "image/png", False);
	win = XCreateSimpleWindow(dpy, DefaultRootWindow(dpy), -10, -10, 1, 1, 0, 0, 0);
	XSelectInput(dpy, win, PropertyChangeMask);
	XFixesSelectSelectionInput(dpy, DefaultRootWindow(dpy), CLIPBOARD, XFixesSetSelectionOwnerNotifyMask);
	for (;;) {
		XNextEvent(dpy, &ev);
		if (ev.type == evbase + XFixesSelectionNotify) {
			XFixesSelectionNotifyEvent *s = (XFixesSelectionNotifyEvent *)&ev;
			XEvent more;
			if (s->owner == None) continue;
			/* several changes in a row: only the newest counts */
			while (XCheckTypedEvent(dpy, evbase + XFixesSelectionNotify, &more)) ;
			changed();
		}
	}
}
