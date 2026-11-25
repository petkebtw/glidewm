/* See LICENSE file for copyright and license details.
 *
 * dynamic window manager is designed like any other X client as well. It is
 * driven through handling X events. In contrast to other X clients, a window
 * manager selects for SubstructureRedirectMask on the root window, to receive
 * events about window (dis-)appearance. Only one X connection at a time is
 * allowed to select for this event mask.
 *
 * The event handlers of dwm are organized in an array which is accessed
 * whenever a new event has been fetched. This allows event dispatching
 * in O(1) time.
 *
 * Each child of the root window is called a client, except windows which have
 * set the override_redirect flag. Clients are organized in a linked client
 * list on each monitor, the focus history is remembered through a stack list
 * on each monitor. Each client contains a bit array to indicate the tags of a
 * client.
 *
 * Keys and tagging rules are organized as arrays and defined in config.h.
 *
 * To understand everything else, start reading main().
 */
#include <errno.h>
#include <locale.h>
#include <signal.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include <sys/select.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <X11/cursorfont.h>
#include <X11/keysym.h>
#include <X11/Xatom.h>
#include <X11/Xlib.h>
#include <strings.h>
#include <X11/Xproto.h>
#include <X11/Xresource.h>
#include <X11/Xutil.h>
#ifdef XINERAMA
#include <X11/extensions/Xinerama.h>
#endif /* XINERAMA */
#include <X11/extensions/shape.h>
#include <X11/Xft/Xft.h>
#include <math.h>
#include <cairo/cairo.h>
#include <cairo/cairo-xlib.h>
#include <X11/extensions/XTest.h>

#include "drw.h"
#include "util.h"

/* macros */
#define BUTTONMASK              (ButtonPressMask|ButtonReleaseMask)
#define CLEANMASK(mask)         (mask & ~(numlockmask|LockMask) & (ShiftMask|ControlMask|Mod1Mask|Mod2Mask|Mod3Mask|Mod4Mask|Mod5Mask))
#define INTERSECT(x,y,w,h,m)    (MAX(0, MIN((x)+(w),(m)->wx+(m)->ww) - MAX((x),(m)->wx)) \
                               * MAX(0, MIN((y)+(h),(m)->wy+(m)->wh) - MAX((y),(m)->wy)))
#define ISVISIBLE(C)            ((C->tags & C->mon->tagset[C->mon->seltags]))
#define MOUSEMASK               (BUTTONMASK|PointerMotionMask)
#define WIDTH(X)                ((X)->w + 2 * (X)->bw)
#define HEIGHT(X)               ((X)->h + 2 * (X)->bw)
#define TAGMASK                 ((1 << LENGTH(tags)) - 1)
#define TEXTW(X)                (drw_fontset_getwidth(drw, (X)) + lrpad)
#define XRDB_LOAD_COLOR(R,V)    if (XrmGetResource(xrdb, R, NULL, &type, &value) == True) { \
                                  if (value.addr != NULL && strnlen(value.addr, 8) == 7 && value.addr[0] == '#') { \
                                    int i = 1; \
                                    for (; i <= 6; i++) { \
                                      if (value.addr[i] < 48) break; \
                                      if (value.addr[i] > 57 && value.addr[i] < 65) break; \
                                      if (value.addr[i] > 70 && value.addr[i] < 97) break; \
                                      if (value.addr[i] > 102) break; \
                                    } \
                                    if (i == 7) { \
                                      strncpy(V, value.addr, 7); \
                                      V[7] = '\0'; \
                                    } \
                                  } \
                                }

#define SYSTEM_TRAY_REQUEST_DOCK    0
/* XEMBED messages */
#define XEMBED_EMBEDDED_NOTIFY      0
#define XEMBED_WINDOW_ACTIVATE      1
#define XEMBED_FOCUS_IN             4
#define XEMBED_MODALITY_ON         10
#define XEMBED_MAPPED              (1 << 0)
#define XEMBED_WINDOW_ACTIVATE      1
#define XEMBED_WINDOW_DEACTIVATE    2
#define VERSION_MAJOR               0
#define VERSION_MINOR               0
#define XEMBED_EMBEDDED_VERSION (VERSION_MAJOR << 16) | VERSION_MINOR

/* enums */
enum { CurNormal, CurResize, CurMove, CurLast }; /* cursor */
enum { SchemeNorm, SchemeSel }; /* color schemes */
enum { NetSupported, NetWMName, NetWMState, NetWMCheck,
       NetSystemTray, NetSystemTrayOP, NetSystemTrayOrientation, NetSystemTrayOrientationHorz,
       NetWMFullscreen, NetActiveWindow, NetWMWindowType,
       NetWMWindowTypeDialog, NetClientList, NetLast }; /* EWMH atoms */
enum { Manager, Xembed, XembedInfo, XLast }; /* Xembed atoms */
enum { WMProtocols, WMDelete, WMState, WMTakeFocus, WMLast }; /* default atoms */
enum { ClkTagBar, ClkLtSymbol, ClkStatusText, ClkWinTitle,
       ClkClientWin, ClkRootWin, ClkAccount, ClkClock, ClkLast }; /* clicks */

typedef union {
	int i;
	unsigned int ui;
	float f;
	const void *v;
} Arg;

typedef struct {
	unsigned int click;
	unsigned int mask;
	unsigned int button;
	void (*func)(const Arg *arg);
	const Arg arg;
} Button;

typedef struct Monitor Monitor;
typedef struct Client Client;
struct Client {
	char name[256];
	float mina, maxa;
	int x, y, w, h;
	int oldx, oldy, oldw, oldh;
	int basew, baseh, incw, inch, maxw, maxh, minw, minh, hintsvalid;
	int bw, oldbw;
	unsigned int tags;
	int isfixed, isfloating, isurgent, neverfocus, oldstate, isfullscreen;
	float ax, ay, aw, ah;   /* displayed (animated) geometry */
	float fx, fy, fw, fh;   /* animation start */
	float tx, ty, tw, th;   /* animation target */
	double t0;
	int anim, park, parked, placed, snapx, snapy, hasb, bt, clipped;
	int isgame;            /* window of a game Steam started (see detectgame) */
	float bm;               /* border colour mix: 0 = normal, 1 = selected (animated) */
	Client *next;
	Client *snext;
	Monitor *mon;
	Window win;
	float bx, by, bw0, bh0;  /* canvas zoom: geometry at zoom 1 (world) */
	int lx, ly, lw, lh, lvalid; /* last geometry the canvas zoom applied (a difference = the user moved it) */
};

typedef struct {
	unsigned int mod;
	KeySym keysym;
	void (*func)(const Arg *);
	const Arg arg;
} Key;

typedef struct {
	unsigned int mod;
	KeySym keysym;
	void (*func)(const Arg *);
	Arg arg;
} DKey;

static DKey *curkeys;
static unsigned int ncur;

typedef struct {
	const char *symbol;
	void (*arrange)(Monitor *);
} Layout;

struct Monitor {
	char ltsymbol[16];
	float mfact;
	int nmaster;
	int num;
	int by;               /* bar geometry */
	int mx, my, mw, mh;   /* screen size */
	int wx, wy, ww, wh;   /* window area  */
	unsigned int seltags;
	unsigned int sellt;
	unsigned int tagset[2];
	int showbar;
	int topbar;
	Client *clients;
	Client *sel;
	Client *stack;
	Monitor *next;
	Window barwin;
	const Layout *lt[2];
	float pl, pr;         /* animated tag-pill edges */
	int pinit;
	float flushf, flushfrom; /* animated bar flush fraction (0 floating .. 1 flush) */
	int flusht;
	double flusht0;
	int canvas;           /* free-drag canvas mode */
	const Layout *canvaslt;
	float cz, cpx, cpy;   /* canvas zoom and pan: screen = world * cz + cp */
};

typedef struct {
	const char *class;
	const char *instance;
	const char *title;
	unsigned int tags;
	int isfloating;
	int monitor;
} Rule;

typedef struct {
	Window win;
	Client *icons;
} Systray;

/* function declarations */
static void applyrules(Client *c);
static int applysizehints(Client *c, int *x, int *y, int *w, int *h, int interact);
static void arrange(Monitor *m);
static void arrangemon(Monitor *m);
static void attach(Client *c);
static void attachstack(Client *c);
static void buttonpress(XEvent *e);
static void checkotherwm(void);
static void cleanup(void);
static void cleanupmon(Monitor *mon);
static void clientmessage(XEvent *e);
static void configure(Client *c);
static void configurenotify(XEvent *e);
static void configurerequest(XEvent *e);
static Monitor *createmon(void);
static void destroynotify(XEvent *e);
static void detach(Client *c);
static void detachstack(Client *c);
static Monitor *dirtomon(int dir);
static void publishmons(void);
static int shapeev = -1; /* ShapeNotify event number */
static void shellcheck(Window w);
static Window shellfocus; /* a Quickshell panel that asked for the keyboard (_NET_ACTIVE_WINDOW) */
#define MAXSHELLABOVE 64
static Window shellabove[MAXSHELLABOVE]; /* Quickshell ABOVE windows (dock, menus): kept over floating windows, under fullscreen */
static int nshellabove;
static void drawbar(Monitor *m);
static int barflush(Monitor *m);
static int tagw(int sel);
static void animstep(void);
static int baranim;          /* animation running */
static int noanim, panning, swipedir;
static int companim = 0; /* 1: dwm snaps windows to the final geometry, picom animates it (rules in rice.conf) */
static Monitor *swipemon;
static unsigned int vp(Monitor *m);
static unsigned int gp(Monitor *m);
static unsigned int spa(Monitor *m);
static unsigned int vpa(Monitor *m);
static void applygeom(Client *c);
static void reborder(Client *c);
static void spawnat(const Arg *arg);
static void togglecanvas(const Arg *arg);
static void canvaswheel(const Arg *arg);
static void canvaszoomreset(const Arg *arg);
static void panmouse(const Arg *arg);
static void snapwin(const Arg *arg);
static void movewin(const Arg *arg);
static void sizewin(const Arg *arg);
#define ICW 18
static int avatard(void);
static int traymirrorclick(Monitor *m, XButtonPressedEvent *ev);
static void syncptrmon(void);
static void rlayout(int bw, int *acx, int *ckx, int *ckw, int *icx, int *hasicon);
static Atom ricecmd;
static int tagstyle = 0, showtitle = 1, showlayout = 1; /* bar options, IPC 11 */
#define LTW(m) (showlayout ? TEXTW(layoutlabel(m)) : 0)
static void ricecmdrun(void);
static int clickx, clicky;   /* root coords of last bar click (popup anchor) */
static void setgaps(const Arg *arg);
static void drawbars(void);
static void enternotify(XEvent *e);
static void expose(XEvent *e);
static void focus(Client *c);
static void focusin(XEvent *e);
static void focusmon(const Arg *arg);
static void focusstack(const Arg *arg);
static Atom getatomprop(Client *c, Atom prop);
static int getrootptr(int *x, int *y);
static long getstate(Window w);
static unsigned int getsystraywidth();
static int gettextprop(Window w, Atom atom, char *text, unsigned int size);
static void grabbuttons(Client *c, int focused);
static void grabkeys(void);
static void incnmaster(const Arg *arg);
static void keypress(XEvent *e);
static void killclient(const Arg *arg);
static void loadxrdb(void);
static void manage(Window w, XWindowAttributes *wa);
static void mappingnotify(XEvent *e);
static void maprequest(XEvent *e);
static int isshellwin(Window w);
static void monocle(Monitor *m);
static void motionnotify(XEvent *e);
static void movemouse(const Arg *arg);
static Client *nexttiled(Client *c);
static void pop(Client *c);
static void propertynotify(XEvent *e);
static void quit(const Arg *arg);
static Monitor *recttomon(int x, int y, int w, int h);
static void removesystrayicon(Client *i);
static void resize(Client *c, int x, int y, int w, int h, int interact);
static void resizebarwin(Monitor *m);
static int detectgame(Window w);
static void resizeclient(Client *c, int x, int y, int w, int h);
static void resizemouse(const Arg *arg);
static void resizerequest(XEvent *e);
static void restack(Monitor *m);
static void raiseshell(void);
static void run(void);
static void scan(void);
static int sendevent(Window w, Atom proto, int m, long d0, long d1, long d2, long d3, long d4);
static void sendmon(Client *c, Monitor *m);
static void setclientstate(Client *c, long state);
static void setfocus(Client *c);
static void setfullscreen(Client *c, int fullscreen);
static void setlayout(const Arg *arg);
static void setmfact(const Arg *arg);
static void setup(void);
static void seturgent(Client *c, int urg);
static void showhide(Client *c);
static void spawn(const Arg *arg);
static Monitor *systraytomon(Monitor *m);
static Monitor *traymon;
static Monitor *traytemp; /* tray briefly moved under a clicked mirror icon */
static double traytemp_t;
static void tag(const Arg *arg);
static void tagmon(const Arg *arg);
static void tile(Monitor *m);
static void bento(Monitor *m);
static void dock(Monitor *m);
static void mosaic(Monitor *m);
static void cyclelayout(const Arg *arg);
static void movestack(const Arg *arg);
static void resetlayout(const Arg *arg);
static const char *layoutlabel(Monitor *m);
static void loadkeys(void);
static void dumpkeys(void);
static void sighup(int unused);
static void sigterm(int unused);
static void togglebar(const Arg *arg);
static void togglefloating(const Arg *arg);
static void toggletag(const Arg *arg);
static void toggleview(const Arg *arg);
static void unfocus(Client *c, int setfocus);
static void unmanage(Client *c, int destroyed);
static void unmapnotify(XEvent *e);
static void updatebarpos(Monitor *m);
static void updatebars(void);
static void updateclientlist(void);
static int updategeom(void);
static void updatenumlockmask(void);
static void updatesizehints(Client *c);
static void updatestatus(void);
static void updatesystray(void);
static void updatesystrayicongeom(Client *i, int w, int h);
static void updatesystrayiconstate(Client *i, XPropertyEvent *ev);
static void updatetitle(Client *c);
static void updatewindowtype(Client *c);
static void updatewmhints(Client *c);
static void view(const Arg *arg);
static Client *wintoclient(Window w);
static Monitor *wintomon(Window w);
static Client *wintosystrayicon(Window w);
static int xerror(Display *dpy, XErrorEvent *ee);
static int xerrordummy(Display *dpy, XErrorEvent *ee);
static int xerrorstart(Display *dpy, XErrorEvent *ee);
static void xrdb(const Arg *arg);
static void zoom(const Arg *arg);

/* variables */
static Systray *systray = NULL;
static const char broken[] = "broken";
static char stext[256];
static int screen;
static int sw, sh;           /* X display screen geometry width, height */
static int bh;               /* bar height */
static int lrpad;            /* sum of left and right padding for text */
static int (*xerrorxlib)(Display *, XErrorEvent *);
static unsigned int numlockmask = 0;
static void (*handler[LASTEvent]) (XEvent *) = {
	[ButtonPress] = buttonpress,
	[ClientMessage] = clientmessage,
	[ConfigureRequest] = configurerequest,
	[ConfigureNotify] = configurenotify,
	[DestroyNotify] = destroynotify,
	[EnterNotify] = enternotify,
	[Expose] = expose,
	[FocusIn] = focusin,
	[KeyPress] = keypress,
	[MappingNotify] = mappingnotify,
	[MapRequest] = maprequest,
	[MotionNotify] = motionnotify,
	[PropertyNotify] = propertynotify,
	[ResizeRequest] = resizerequest,
	[UnmapNotify] = unmapnotify
};
static Atom wmatom[WMLast], netatom[NetLast], xatom[XLast];
static int running = 1;
static int restart = 0;
static char **restartargv;
static Cur *cursor[CurLast];
static Clr **scheme;
static Display *dpy;
static Drw *drw;
static Monitor *mons, *selmon;
static Window root, wmcheckwin;

/* configuration, allows nested code to access above variables */
#include "config.h"

/* compile-time check if all tags fit into an unsigned int bit array. */
struct NumTags { char limitexceeded[LENGTH(tags) > 31 ? -1 : 1]; };

/* function implementations */
void
applyrules(Client *c)
{
	const char *class, *instance;
	unsigned int i;
	const Rule *r;
	Monitor *m;
	XClassHint ch = { NULL, NULL };

	/* rule matching */
	c->isfloating = 0;
	c->tags = 0;
	XGetClassHint(dpy, c->win, &ch);
	class    = ch.res_class ? ch.res_class : broken;
	instance = ch.res_name  ? ch.res_name  : broken;

	for (i = 0; i < LENGTH(rules); i++) {
		r = &rules[i];
		if ((!r->title || strstr(c->name, r->title))
		&& (!r->class || strstr(class, r->class))
		&& (!r->instance || strstr(instance, r->instance)))
		{
			c->isfloating = r->isfloating;
			c->tags |= r->tags;
			for (m = mons; m && m->num != r->monitor; m = m->next);
			if (m)
				c->mon = m;
		}
	}
	if (ch.res_class)
		XFree(ch.res_class);
	if (ch.res_name)
		XFree(ch.res_name);
	c->tags = c->tags & TAGMASK ? c->tags & TAGMASK : c->mon->tagset[c->mon->seltags];
}

int
applysizehints(Client *c, int *x, int *y, int *w, int *h, int interact)
{
	int baseismin;
	Monitor *m = c->mon;

	/* set minimum possible */
	*w = MAX(1, *w);
	*h = MAX(1, *h);
	if (interact) {
		if (*x > sw)
			*x = sw - WIDTH(c);
		if (*y > sh)
			*y = sh - HEIGHT(c);
		if (*x + *w + 2 * c->bw < 0)
			*x = 0;
		if (*y + *h + 2 * c->bw < 0)
			*y = 0;
	} else {
		if (*x >= m->wx + m->ww)
			*x = m->wx + m->ww - WIDTH(c);
		if (*y >= m->wy + m->wh)
			*y = m->wy + m->wh - HEIGHT(c);
		if (*x + *w + 2 * c->bw <= m->wx)
			*x = m->wx;
		if (*y + *h + 2 * c->bw <= m->wy)
			*y = m->wy;
	}
	if (*h < bh)
		*h = bh;
	if (*w < bh)
		*w = bh;
	if (resizehints || c->isfloating || !c->mon->lt[c->mon->sellt]->arrange) {
		if (!c->hintsvalid)
			updatesizehints(c);
		/* see last two sentences in ICCCM 4.1.2.3 */
		baseismin = c->basew == c->minw && c->baseh == c->minh;
		if (!baseismin) { /* temporarily remove base dimensions */
			*w -= c->basew;
			*h -= c->baseh;
		}
		/* adjust for aspect limits */
		if (c->mina > 0 && c->maxa > 0) {
			if (c->maxa < (float)*w / *h)
				*w = *h * c->maxa + 0.5;
			else if (c->mina < (float)*h / *w)
				*h = *w * c->mina + 0.5;
		}
		if (baseismin) { /* increment calculation requires this */
			*w -= c->basew;
			*h -= c->baseh;
		}
		/* adjust for increment value */
		if (c->incw)
			*w -= *w % c->incw;
		if (c->inch)
			*h -= *h % c->inch;
		/* restore base dimensions */
		*w = MAX(*w + c->basew, c->minw);
		*h = MAX(*h + c->baseh, c->minh);
		if (c->maxw)
			*w = MIN(*w, c->maxw);
		if (c->maxh)
			*h = MIN(*h, c->maxh);
	}
	return *x != c->x || *y != c->y || *w != c->w || *h != c->h;
}

void
arrange(Monitor *m)
{
	if (m)
		showhide(m->stack);
	else for (m = mons; m; m = m->next)
		showhide(m->stack);
	if (m) {
		arrangemon(m);
		restack(m);
	} else for (m = mons; m; m = m->next)
		arrangemon(m);
}

int
tagw(int sel)
{
	(void)sel;
	return 28; /* fixed slot so the pill can animate without shifting layout */
}

#ifdef MIRRORTEST
#define MIRRORCOND 1
#define MIRRORTM 1
#else
#define MIRRORCOND (mons && mons->next)
#define MIRRORTM (tm != traymon)
#endif
#define ANIMDUR 0.20
#define GEODUR 0.22   /* window geometry: a little longer so the soft landing reads */
#define TAGX0 14   /* left padding before the first workspace dot */
#define PI 3.14159265358979323846

static double
nowsec(void)
{
	struct timespec ts;
	clock_gettime(CLOCK_MONOTONIC, &ts);
	return ts.tv_sec + ts.tv_nsec / 1e9;
}

static float
ease(float p)
{
	if (p >= 1) return 1;
	if (p <= 0) return 0;
	p = 1 - p;
	return 1 - p * p * p * p; /* ease-out quart */
}

/* cubic-bezier easing (CSS style); the Hyprland default curve overshoots slightly, so only use it for geometry */
static float
bez(float p, float x1, float y1, float x2, float y2)
{
	float lo = 0, hi = 1, u = p, x;
	int i;

	if (p >= 1) return 1;
	if (p <= 0) return 0;
	for (i = 0; i < 20; i++) {
		x = 3 * (1 - u) * (1 - u) * u * x1 + 3 * (1 - u) * u * u * x2 + u * u * u;
		if (x < p) lo = u; else hi = u;
		u = (lo + hi) / 2;
	}
	return 3 * (1 - u) * (1 - u) * u * y1 + 3 * (1 - u) * u * u * y2 + u * u * u;
}

static float
easeg(float p)
{
	return bez(p, 0.22f, 1.0f, 0.36f, 1.0f); /* smooth ease-out, no overshoot */
}

/* per-channel blend of two 24-bit TrueColor pixels */
static unsigned long
blendpx(unsigned long a, unsigned long b, float f)
{
	unsigned long out = 0;
	int sh;

	for (sh = 0; sh <= 16; sh += 8) {
		int ca = (a >> sh) & 0xff, cb = (b >> sh) & 0xff;
		out |= (unsigned long)(ca + (cb - ca) * f + 0.5f) << sh;
	}
	return out;
}

/* canvas mode: panning is per monitor, so a window never shows on another monitor.
 * The part outside its own monitor is cut off with a bounding shape. */
static void
clipcanvas(Client *c, int x, int y, int w, int h, int hasb)
{
	/* x,y,w,h = inner box. Visible box = inner box plus border when outlined. */
	Monitor *m = c->mon;
	XRectangle r;
	int bwv = hasb ? c->bw : 0;
	int vx = x - bwv, vy = y - bwv, vw = w + 2 * bwv, vh = h + 2 * bwv;
	int x1 = vx, y1 = vy, x2 = vx + vw, y2 = vy + vh;
	int full = hasb || c->bw == 0;

	if (m && m->canvas && !c->isfullscreen) {
		x1 = MAX(x1, m->mx); y1 = MAX(y1, m->my);
		x2 = MIN(x2, m->mx + m->mw); y2 = MIN(y2, m->my + m->mh);
		if (x1 != vx || y1 != vy || x2 != vx + vw || y2 != vy + vh)
			full = 0;
	}
	if (full) {
		if (c->clipped) {
			XShapeCombineMask(dpy, c->win, ShapeBounding, 0, 0, None, ShapeSet);
			c->clipped = 0;
		}
		return;
	}
	if (x2 <= x1 || y2 <= y1) {
		XShapeCombineRectangles(dpy, c->win, ShapeBounding, 0, 0, NULL, 0, ShapeSet, 0);
	} else {
		r.x = x1 - x; r.y = y1 - y; /* shape coordinates start at the inner origin */
		r.width = x2 - x1; r.height = y2 - y1;
		XShapeCombineRectangles(dpy, c->win, ShapeBounding, 0, 0, &r, 1, ShapeSet, 0);
	}
	c->clipped = 1;
}

/* push displayed geometry to X. The X border width is constant, so content never
 * resizes; an unfocused window just has its outline cut off with a bounding shape. */
void
applygeom(Client *c)
{
	XWindowChanges wc;

	wc.x = (int)(c->ax + 0.5f);
	wc.y = (int)(c->ay + 0.5f);
	wc.width = MAX(1, (int)(c->aw + 0.5f));
	wc.height = MAX(1, (int)(c->ah + 0.5f));
	wc.border_width = c->bw;
	XConfigureWindow(dpy, c->win, CWX|CWY|CWWidth|CWHeight|CWBorderWidth, &wc);
	clipcanvas(c, wc.x, wc.y, wc.width, wc.height, 1); /* outline stays; unfocused just uses the normal border colour */
}

void
reborder(Client *c)
{
	if (c && c->placed && !c->parked)
		applygeom(c);
}

void
animstep(void)
{
	static double last;
	double t = nowsec();
	Monitor *m;
	Client *c;
	unsigned int i;
	float dt = last ? (float)(t - last) : 0.016f;

	if (dt > 0.05f || dt <= 0) dt = 0.016f;
	last = t;
	baranim = 0;
	for (m = mons; m; m = m->next) {
		int first = -1, lastb = -1;
		for (i = 0; i < LENGTH(tags); i++)
			if (m->tagset[m->seltags] & 1 << i) {
				if (first < 0) first = i;
				lastb = i;
			}
		if (first >= 0) {
			float tl = TAGX0 + first * tagw(0) + 2, tr = TAGX0 + lastb * tagw(0) + tagw(0) - 2;
			float kf = 1 - expf(-34 * dt), ks = 1 - expf(-12 * dt), kl, kr;
			if (!m->pinit) { m->pl = tl; m->pr = tr; m->pinit = 1; }
			if ((tl + tr) - (m->pl + m->pr) > 0) { kr = kf; kl = ks; } /* leading edge fast, trailing edge lags: stretch */
			else { kl = kf; kr = ks; }
			m->pl += (tl - m->pl) * kl;
			m->pr += (tr - m->pr) * kr;
			if (fabsf(tl - m->pl) < 0.3f && fabsf(tr - m->pr) < 0.3f) { m->pl = tl; m->pr = tr; }
			else baranim = 1;
		}
		if (m->flushf != (float)m->flusht) {
			float p = (float)((t - m->flusht0) / ANIMDUR);
			m->flushf = m->flushfrom + (m->flusht - m->flushfrom) * ease(p);
			if (p >= 1) m->flushf = m->flusht; else baranim = 1;
			updatebarpos(m);
			resizebarwin(m);
			if (m == systraytomon(m))
				updatesystray();
		}
		drawbar(m);
		for (c = m->clients; c; c = c->next) {
			float p, e;
			if (c->hasb && c->bm != (float)c->bt) {
				float st = dt / (c->bt ? 0.14f : 0.08f);
				c->bm += c->bt ? st : -st;
				if (c->bm < 0) c->bm = 0;
				if (c->bm > 1) c->bm = 1;
				XSetWindowBorder(dpy, c->win, blendpx(scheme[SchemeNorm][ColBorder].pixel,
					scheme[SchemeSel][ColBorder].pixel, ease(c->bm)));
				if (c->bm == (float)c->bt) {
					if (!c->bt) { c->hasb = 0; reborder(c); }
				} else
					baranim = 1;
			}
			if (!c->anim) continue;
			p = (float)((t - c->t0) / GEODUR);
			e = easeg(p);
			c->ax = c->fx + (c->tx - c->fx) * e;
			c->ay = c->fy + (c->ty - c->fy) * e;
			c->aw = c->fw + (c->tw - c->fw) * e;
			c->ah = c->fh + (c->th - c->fh) * e;
			if (p >= 1) {
				c->ax = c->tx; c->ay = c->ty; c->aw = c->tw; c->ah = c->th;
				c->anim = 0;
				if (c->park) {
					c->park = 0;
					c->parked = 1;
					XMoveWindow(dpy, c->win, -2 * (int)(c->aw + 2 * c->bw), (int)c->ay);
				} else
					applygeom(c);
			} else {
				applygeom(c);
				baranim = 1;
			}
		}
	}
	XFlush(dpy);
}

int
barflush(Monitor *m)
{
	unsigned int n = 0;
	Client *c;

	for (c = nexttiled(m->clients); c; c = nexttiled(c->next))
		n++;
	if (m->canvas)
		return 0;
	if (m->lt[m->sellt]->arrange == monocle)
		return n >= 1;
	if (m->lt[m->sellt]->arrange)
		return n == 1;
	return 0;
}

/* layout gaps follow the target state; bar position follows the animated state */
unsigned int vp(Monitor *m) { return barflush(m) ? 0 : vertpad; }
unsigned int gp(Monitor *m) { return barflush(m) ? 0 : gappx; }
unsigned int spa(Monitor *m) { return (unsigned int)(sidepad * (1 - m->flushf) + 0.5f); }
unsigned int vpa(Monitor *m) { return (unsigned int)(vertpad * (1 - m->flushf) + 0.5f); }

void
arrangemon(Monitor *m)
{
	int ft;
	strncpy(m->ltsymbol, m->lt[m->sellt]->symbol, sizeof m->ltsymbol);
	if (m->canvas)
		strncpy(m->ltsymbol, "\xef\x81\x87", sizeof m->ltsymbol); /* nf-fa-arrows */
	if ((ft = barflush(m)) != m->flusht) {
		m->flusht = ft;
		m->flushfrom = m->flushf;
		m->flusht0 = nowsec();
	}
	baranim = 1;
	updatebarpos(m);
	if (m->barwin && (systray || !showsystray))
		resizebarwin(m);
	if (m->lt[m->sellt]->arrange)
		m->lt[m->sellt]->arrange(m);
	if (systray && showsystray && m == systraytomon(m))
		updatesystray();
}

void
attach(Client *c)
{
	c->next = c->mon->clients;
	c->mon->clients = c;
}

void
attachstack(Client *c)
{
	c->snext = c->mon->stack;
	c->mon->stack = c;
}

void
buttonpress(XEvent *e)
{
	unsigned int i, x, click;
	Arg arg = {0};
	Client *c;
	Monitor *m;
	XButtonPressedEvent *ev = &e->xbutton;

	click = ClkRootWin;
	/* focus monitor if necessary */
	if ((m = wintomon(ev->window)) && m != selmon) {
		unfocus(selmon->sel, 1);
		selmon = m;
		focus(NULL);
	}
	if (traymirrorclick(m, ev))
		return;
	if (ev->window == selmon->barwin) {
		int bw = selmon->ww - 2 * spa(selmon), acx, ckx, ckw, icx, hi;
		i = 0; x = TAGX0;
		do
			x += tagw(selmon->tagset[selmon->seltags] & 1 << i);
		while (ev->x >= x && ++i < LENGTH(tags));
		if (i < LENGTH(tags)) {
			click = ClkTagBar;
			arg.ui = 1 << i;
		} else if (ev->x < x + LTW(selmon))
			click = ClkLtSymbol;
		else {
			rlayout(bw, &acx, &ckx, &ckw, &icx, &hi);
			click = ClkWinTitle;
			if (ev->x >= acx - 6) { click = ClkAccount; clickx = selmon->wx + spa(selmon) + acx + avatard() / 2; }
			else if (hi && ev->x >= icx - 8 && ev->x < icx + ICW + 8) { click = ClkStatusText; clickx = selmon->wx + spa(selmon) + icx + ICW / 2; }
			else if (ev->x >= ckx - 8) click = ClkClock;
			clicky = selmon->by + bh;
		}
	} else if ((c = wintoclient(ev->window))) {
		focus(c);
		restack(selmon);
		XAllowEvents(dpy, ReplayPointer, CurrentTime);
		click = ClkClientWin;
	}
	for (i = 0; i < LENGTH(buttons); i++)
		if (click == buttons[i].click && buttons[i].func && buttons[i].button == ev->button
		&& CLEANMASK(buttons[i].mask) == CLEANMASK(ev->state))
			buttons[i].func(click == ClkTagBar && buttons[i].arg.i == 0 ? &arg : &buttons[i].arg);
}

void
checkotherwm(void)
{
	xerrorxlib = XSetErrorHandler(xerrorstart);
	/* this causes an error if some other window manager is running */
	XSelectInput(dpy, DefaultRootWindow(dpy), SubstructureRedirectMask);
	XSync(dpy, False);
	XSetErrorHandler(xerror);
	XSync(dpy, False);
}

void
cleanup(void)
{
	Arg a = {.ui = ~0};
	Layout foo = { "", NULL };
	Monitor *m;
	size_t i;

	if (restart) { /* remember tags so windows come back where they were */
		Atom at = XInternAtom(dpy, "_RICE_TAGS", False);
		Client *rc;
		unsigned long tv;
		for (m = mons; m; m = m->next)
			for (rc = m->clients; rc; rc = rc->next) {
				tv = rc->tags;
				XChangeProperty(dpy, rc->win, at, XA_CARDINAL, 32, PropModeReplace, (unsigned char *)&tv, 1);
			}
		tv = selmon->tagset[selmon->seltags];
		XChangeProperty(dpy, root, XInternAtom(dpy, "_RICE_VIEW", False), XA_CARDINAL, 32, PropModeReplace, (unsigned char *)&tv, 1);
	}
	view(&a);
	selmon->lt[selmon->sellt] = &foo;
	for (m = mons; m; m = m->next)
		while (m->stack)
			unmanage(m->stack, 0);
	XUngrabKey(dpy, AnyKey, AnyModifier, root);
	while (mons)
		cleanupmon(mons);

	if (showsystray) {
		XUnmapWindow(dpy, systray->win);
		XDestroyWindow(dpy, systray->win);
		free(systray);
	}

	for (i = 0; i < CurLast; i++)
		drw_cur_free(drw, cursor[i]);
	for (i = 0; i < LENGTH(colors); i++)
		drw_scm_free(drw, scheme[i], 3);
	free(scheme);
	XDestroyWindow(dpy, wmcheckwin);
	drw_free(drw);
	XSync(dpy, False);
	XSetInputFocus(dpy, PointerRoot, RevertToPointerRoot, CurrentTime);
	XDeleteProperty(dpy, root, netatom[NetActiveWindow]);
}

void
cleanupmon(Monitor *mon)
{
	Monitor *m;

	if (mon == mons)
		mons = mons->next;
	else {
		for (m = mons; m && m->next != mon; m = m->next);
		m->next = mon->next;
	}
	XUnmapWindow(dpy, mon->barwin);
	XDestroyWindow(dpy, mon->barwin);
	free(mon);
}

void
clientmessage(XEvent *e)
{
	XWindowAttributes wa;
	XSetWindowAttributes swa;
	XClientMessageEvent *cme = &e->xclient;
	Client *c = wintoclient(cme->window);

	if (!c && cme->message_type == netatom[NetActiveWindow] && isshellwin(cme->window)) {
		/* a shell menu / launcher / settings panel wants keys (Esc, typing): give it the X focus until it goes away */
		XSetInputFocus(dpy, cme->window, RevertToPointerRoot, CurrentTime);
		shellfocus = cme->window;
		return;
	}
	if (showsystray && cme->window == systray->win && cme->message_type == netatom[NetSystemTrayOP]) {
		/* add systray icons */
		if (cme->data.l[1] == SYSTEM_TRAY_REQUEST_DOCK) {
			if (!(c = (Client *)calloc(1, sizeof(Client))))
				die("fatal: could not malloc() %u bytes\n", sizeof(Client));
			if (!(c->win = cme->data.l[2])) {
				free(c);
				return;
			}
			c->mon = selmon;
			c->next = systray->icons;
			systray->icons = c;
			if (!XGetWindowAttributes(dpy, c->win, &wa)) {
				/* use sane defaults */
				wa.width = bh;
				wa.height = bh;
				wa.border_width = 0;
			}
			c->x = c->oldx = c->y = c->oldy = 0;
			c->w = c->oldw = wa.width;
			c->h = c->oldh = wa.height;
			c->oldbw = wa.border_width;
			c->bw = 0;
			c->isfloating = True;
			/* reuse tags field as mapped status */
			c->tags = 1;
			updatesizehints(c);
			updatesystrayicongeom(c, wa.width, wa.height);
			XAddToSaveSet(dpy, c->win);
			XSelectInput(dpy, c->win, StructureNotifyMask | PropertyChangeMask | ResizeRedirectMask);
			XReparentWindow(dpy, c->win, systray->win, 0, 0);
			/* use parents background color */
			swa.background_pixel  = scheme[SchemeNorm][ColBg].pixel;
			XChangeWindowAttributes(dpy, c->win, CWBackPixel, &swa);
			sendevent(c->win, netatom[Xembed], StructureNotifyMask, CurrentTime, XEMBED_EMBEDDED_NOTIFY, 0 , systray->win, XEMBED_EMBEDDED_VERSION);
			/* FIXME not sure if I have to send these events, too */
			sendevent(c->win, netatom[Xembed], StructureNotifyMask, CurrentTime, XEMBED_FOCUS_IN, 0 , systray->win, XEMBED_EMBEDDED_VERSION);
			sendevent(c->win, netatom[Xembed], StructureNotifyMask, CurrentTime, XEMBED_WINDOW_ACTIVATE, 0 , systray->win, XEMBED_EMBEDDED_VERSION);
			sendevent(c->win, netatom[Xembed], StructureNotifyMask, CurrentTime, XEMBED_MODALITY_ON, 0 , systray->win, XEMBED_EMBEDDED_VERSION);
			XSync(dpy, False);
			resizebarwin(selmon);
			updatesystray();
			setclientstate(c, NormalState);
		}
		return;
	}

	if (!c)
		return;
	if (cme->message_type == netatom[NetWMState]) {
		if (cme->data.l[1] == netatom[NetWMFullscreen]
		|| cme->data.l[2] == netatom[NetWMFullscreen])
			setfullscreen(c, (cme->data.l[0] == 1 /* _NET_WM_STATE_ADD    */
				|| (cme->data.l[0] == 2 /* _NET_WM_STATE_TOGGLE */ && !c->isfullscreen)));
	} else if (cme->message_type == netatom[NetActiveWindow]) {
		if (c != selmon->sel && !c->isurgent)
			seturgent(c, 1);
	}
}

void
configure(Client *c)
{
	XConfigureEvent ce;

	ce.type = ConfigureNotify;
	ce.display = dpy;
	ce.event = c->win;
	ce.window = c->win;
	ce.x = c->x;
	ce.y = c->y;
	ce.width = c->w;
	ce.height = c->h;
	ce.border_width = c->bw;
	ce.above = None;
	ce.override_redirect = False;
	XSendEvent(dpy, c->win, False, StructureNotifyMask, (XEvent *)&ce);
}

void
configurenotify(XEvent *e)
{
	Monitor *m;
	Client *c;
	XConfigureEvent *ev = &e->xconfigure;
	int dirty;

	/* TODO: updategeom handling sucks, needs to be simplified */
	if (ev->window == root) {
		dirty = (sw != ev->width || sh != ev->height);
		sw = ev->width;
		sh = ev->height;
		if (updategeom() || dirty) {
			drw_resize(drw, sw, bh);
			updatebars();
			for (m = mons; m; m = m->next) {
				for (c = m->clients; c; c = c->next)
					if (c->isfullscreen)
						resizeclient(c, m->mx, m->my, m->mw, m->mh);
				resizebarwin(m);
			}
			focus(NULL);
			arrange(NULL);
		}
	}
}

void
configurerequest(XEvent *e)
{
	Client *c;
	Monitor *m;
	XConfigureRequestEvent *ev = &e->xconfigurerequest;
	XWindowChanges wc;

	if ((c = wintoclient(ev->window))) {
		if (ev->value_mask & CWBorderWidth)
			c->bw = ev->border_width;
		else if (c->isfloating || !selmon->lt[selmon->sellt]->arrange) {
			m = c->mon;
			if (ev->value_mask & CWX) {
				c->oldx = c->x;
				c->x = m->mx + ev->x;
			}
			if (ev->value_mask & CWY) {
				c->oldy = c->y;
				c->y = m->my + ev->y;
			}
			if (ev->value_mask & CWWidth) {
				c->oldw = c->w;
				c->w = ev->width;
			}
			if (ev->value_mask & CWHeight) {
				c->oldh = c->h;
				c->h = ev->height;
			}
			if ((c->x + c->w) > m->mx + m->mw && c->isfloating)
				c->x = m->mx + (m->mw / 2 - WIDTH(c) / 2); /* center in x direction */
			if ((c->y + c->h) > m->my + m->mh && c->isfloating)
				c->y = m->my + (m->mh / 2 - HEIGHT(c) / 2); /* center in y direction */
			if ((ev->value_mask & (CWX|CWY)) && !(ev->value_mask & (CWWidth|CWHeight)))
				configure(c);
			if (ISVISIBLE(c))
				XMoveResizeWindow(dpy, c->win, c->x, c->y, c->w, c->h);
		} else
			configure(c);
	} else {
		wc.x = ev->x;
		wc.y = ev->y;
		wc.width = ev->width;
		wc.height = ev->height;
		wc.border_width = ev->border_width;
		wc.sibling = ev->above;
		wc.stack_mode = ev->detail;
		XConfigureWindow(dpy, ev->window, ev->value_mask, &wc);
	}
	XSync(dpy, False);
}

Monitor *
createmon(void)
{
	Monitor *m;

	m = ecalloc(1, sizeof(Monitor));
	m->tagset[0] = m->tagset[1] = 1;
	m->flusht = 0; m->flushf = 0;
	m->cz = 1;
	m->mfact = mfact;
	m->nmaster = nmaster;
	m->showbar = showbar;
	m->topbar = topbar;
	m->lt[0] = &layouts[0];
	m->lt[1] = &layouts[1 % LENGTH(layouts)];
	strncpy(m->ltsymbol, layouts[0].symbol, sizeof m->ltsymbol);
	return m;
}

void
destroynotify(XEvent *e)
{
	Client *c;
	XDestroyWindowEvent *ev = &e->xdestroywindow;

	if ((c = wintoclient(ev->window)))
		unmanage(c, 1);
	else if (shellfocus && ev->window == shellfocus) {
		shellfocus = 0;
		focus(NULL);
	}
	else if ((c = wintosystrayicon(ev->window))) {
		removesystrayicon(c);
		resizebarwin(selmon);
		updatesystray();
	}
}

void
detach(Client *c)
{
	Client **tc;

	for (tc = &c->mon->clients; *tc && *tc != c; tc = &(*tc)->next);
	*tc = c->next;
}

void
detachstack(Client *c)
{
	Client **tc, *t;

	for (tc = &c->mon->stack; *tc && *tc != c; tc = &(*tc)->snext);
	*tc = c->snext;

	if (c == c->mon->sel) {
		for (t = c->mon->stack; t && !ISVISIBLE(t); t = t->snext);
		c->mon->sel = t;
	}
}

Monitor *
dirtomon(int dir)
{
	Monitor *m = NULL;

	if (dir > 0) {
		if (!(m = selmon->next))
			m = mons;
	} else if (selmon == mons)
		for (m = mons; m->next; m = m->next);
	else
		for (m = mons; m->next != selmon; m = m->next);
	return m;
}

void
setgaps(const Arg *arg)
{
	int g = arg->i == 0 ? 10 : (int)gappx + arg->i;
	gappx = g < 0 ? 0 : g > 60 ? 60 : g;
	arrange(selmon);
}

/* ---- right cluster: [systray] [volume icon] [clock] [avatar] ---- */
#define RMARGIN 10
#define RGAP 16

static int
avatard(void) { return bh - 4; }

/* stext format: "<level>\x01<clock text>", level in m,0,1,2,3 */
static const char *
clocktext(int *level)
{
	char *p = strchr(stext, '\x01');
	if (!p) { *level = -1; return stext; }
	*level = stext[0] == 'm' ? 0 : stext[0] - '0';
	return p + 1;
}

static int
muted(void) { return stext[0] == 'm' && stext[1] == '\x01'; }

static void
rlayout(int bw, int *acx, int *ckx, int *ckw, int *icx, int *hasicon)
{
	int lvl;
	const char *ck = clocktext(&lvl);
	*ckw = TEXTW(ck) - lrpad;
	*hasicon = lvl >= 0;
	*acx = bw - RMARGIN - avatard();
	*ckx = *acx - RGAP - *ckw;
	*icx = *hasicon ? *ckx - RGAP - ICW : *ckx;
}

static int
rwidth(void)
{
	int acx, ckx, ckw, icx, hi, bw = 10000;
	rlayout(bw, &acx, &ckx, &ckw, &icx, &hi);
	return bw - icx + 12;
}

static void
setpx(cairo_t *cr, unsigned long px, double a)
{
	cairo_set_source_rgba(cr, ((px >> 16) & 255) / 255.0, ((px >> 8) & 255) / 255.0, (px & 255) / 255.0, a);
}

static void
capsule(cairo_t *cr, double x, double y, double w, double h)
{
	double r = h / 2;
	cairo_new_sub_path(cr);
	cairo_arc(cr, x + w - r, y + r, r, -PI / 2, PI / 2);
	cairo_arc(cr, x + r, y + r, r, PI / 2, 3 * PI / 2);
	cairo_close_path(cr);
}

static void
volicon(cairo_t *cr, double x, double cy, int level, unsigned long px)
{
	setpx(cr, px, 1);
	cairo_set_line_width(cr, 1.6);
	cairo_set_line_cap(cr, CAIRO_LINE_CAP_ROUND);
	cairo_set_line_join(cr, CAIRO_LINE_JOIN_ROUND);
	/* speaker body */
	cairo_move_to(cr, x + 1, cy - 2.6);
	cairo_line_to(cr, x + 4.2, cy - 2.6);
	cairo_line_to(cr, x + 8, cy - 5.6);
	cairo_line_to(cr, x + 8, cy + 5.6);
	cairo_line_to(cr, x + 4.2, cy + 2.6);
	cairo_line_to(cr, x + 1, cy + 2.6);
	cairo_close_path(cr);
	cairo_fill_preserve(cr);
	cairo_stroke(cr);
	if (level == 0) { /* muted: cross */
		cairo_move_to(cr, x + 11, cy - 2.8); cairo_line_to(cr, x + 16, cy + 2.8);
		cairo_move_to(cr, x + 16, cy - 2.8); cairo_line_to(cr, x + 11, cy + 2.8);
		cairo_stroke(cr);
		return;
	}
	if (level >= 1) { cairo_new_sub_path(cr); cairo_arc(cr, x + 8.6, cy, 3.6, -PI / 3.2, PI / 3.2); cairo_stroke(cr); }
	if (level >= 2) { cairo_new_sub_path(cr); cairo_arc(cr, x + 8.6, cy, 6.6, -PI / 3.2, PI / 3.2); cairo_stroke(cr); }
}

static void
avatar(cairo_t *cr, double x, double cy, double d)
{
	double r = d / 2, cx = x + r;
	setpx(cr, scheme[SchemeSel][ColBg].pixel, 1);
	cairo_arc(cr, cx, cy, r, 0, 2 * PI);
	cairo_fill(cr);
	setpx(cr, scheme[SchemeSel][ColFg].pixel, 1);
	cairo_arc(cr, cx, cy - r * 0.26, r * 0.32, 0, 2 * PI); /* head */
	cairo_fill(cr);
	cairo_save(cr);
	cairo_arc(cr, cx, cy, r, 0, 2 * PI);
	cairo_clip(cr);
	cairo_translate(cr, cx, cy + r * 0.98);
	cairo_scale(cr, 1.3, 1.0);
	cairo_arc(cr, 0, 0, r * 0.62, 0, 2 * PI); /* shoulders: wide, flush with the rim, no light sliver under them */
	cairo_fill(cr);
	cairo_restore(cr);
}

/* The real tray window lives on one monitor (a window cannot be on two). On every other
 * bar the icons' pixels are painted straight from the icon windows with cairo. */
static void
drawtraymirror(cairo_t *cr, Monitor *m, int bw, int rw)
{
	Client *i;
	int stw;

#ifdef MIRRORTEST
	if (!showsystray || !systray || !systray->icons)
		return;
#else
	if (!showsystray || !systray || m == traymon || !systray->icons)
		return;
#endif
	stw = getsystraywidth();
	for (i = systray->icons; i; i = i->next) {
		XWindowAttributes wa;
		cairo_surface_t *is;
		if (!i->tags || !XGetWindowAttributes(dpy, i->win, &wa) || wa.map_state != IsViewable)
			continue;
		is = cairo_xlib_surface_create(dpy, i->win, wa.visual, wa.width, wa.height);
#ifdef MIRRORTEST
		cairo_set_source_surface(cr, is, bw - rw - stw + i->x - 300, 0);
#else
		cairo_set_source_surface(cr, is, bw - rw - stw + i->x, 0);
#endif
		cairo_paint(cr);
		cairo_surface_destroy(is);
	}
}

/* a click on a mirrored icon is forwarded to the real icon window */
static int
traymirrorclick(Monitor *m, XButtonPressedEvent *ev)
{
	Client *i;
	int bw, rw, stw;

#ifdef MIRRORTEST
	if (!showsystray || !systray || !systray->icons || !m || ev->window != m->barwin)
		return 0;
#else
	if (!showsystray || !systray || !systray->icons || !m || m == traymon || ev->window != m->barwin)
		return 0;
#endif
	bw = m->ww - 2 * spa(m); rw = rwidth(); stw = getsystraywidth();
	for (i = systray->icons; i; i = i->next) {
#ifdef MIRRORTEST
		int ix = bw - rw - stw + i->x - 300;
#else
		int ix = bw - rw - stw + i->x;
#endif
		if (i->tags && ev->x >= ix && ev->x < ix + i->w) {
			/* Move the real tray under the pointer and replay the click with XTest: apps get a
			 * genuine event, so left and right click both work and menus open on this monitor. */
			traytemp = m;
			traytemp_t = nowsec();
			updatesystray();
			XUngrabPointer(dpy, CurrentTime);
#ifdef MIRRORTEST
			XWarpPointer(dpy, None, root, 0, 0, 0, 0, m->wx + spa(m) + bw - rw - stw + i->x + i->w / 2, m->by + 10);
#endif
			XTestFakeButtonEvent(dpy, ev->button, False, CurrentTime); /* the physical press is still down */
			XTestFakeButtonEvent(dpy, ev->button, True, CurrentTime);
			XFlush(dpy);
			usleep(30000); /* short hold so menus that open on press do not see a zero-length click */
			XTestFakeButtonEvent(dpy, ev->button, False, CurrentTime);
			XFlush(dpy);
			return 1;
		}
	}
	return 0;
}

void
publishmons(void)
{ /* _RICE_MONS = per monitor {x, y, viewed mask, occupied mask}: the Quickshell port hides widgets per screen */
	static unsigned long last[64];
	unsigned long now[64];
	int n = 0;
	Monitor *m;
	Client *c;
	unsigned int occ;

	for (m = mons; m && n + 4 <= 64; m = m->next) {
		occ = 0;
		for (c = m->clients; c; c = c->next)
			occ |= c->tags;
		now[n++] = m->mx; now[n++] = m->my; now[n++] = m->tagset[m->seltags]; now[n++] = occ;
	}
	if (memcmp(now, last, n * sizeof *now) || !last[63]) {
		memcpy(last, now, n * sizeof *now);
		last[63] = 1;
		XChangeProperty(dpy, root, XInternAtom(dpy, "_RICE_MONS", False), XA_CARDINAL, 32,
			PropModeReplace, (unsigned char *)now, n);
	}
}

void
drawbar(Monitor *m)
{
	int x, w, bw = m->ww - 2 * spa(m), rw = rwidth(), stw = 0;
	int cy = bh / 2;
	unsigned int i, occ = 0, urg = 0;
	Client *c;
	cairo_surface_t *cs;
	cairo_t *cr;

	publishmons();
	if (!m->showbar)
		return;
	if (showsystray && !systrayonleft)
		stw = getsystraywidth(); /* every bar keeps the room: the real tray is on one, the others show a mirror */

	drw_setscheme(drw, scheme[SchemeNorm]);
	drw_rect(drw, 0, 0, bw, bh, 1, 1);
	resizebarwin(m);
	for (c = m->clients; c; c = c->next) {
		occ |= c->tags;
		if (c->isurgent)
			urg |= c->tags;
	}
	if (m == selmon) { /* _RICE_TAGS = {viewed mask, occupied mask, urgent mask, monitor number}: read by the Quickshell port */
		static unsigned long last[4];
		unsigned long now[4];
		int mn = 0;
		Monitor *mm;
		for (mm = mons; mm && mm != m; mm = mm->next)
			mn++;
		now[0] = m->tagset[m->seltags]; now[1] = occ; now[2] = urg; now[3] = mn;
		if (memcmp(now, last, sizeof now)) {
			memcpy(last, now, sizeof now);
			XChangeProperty(dpy, root, XInternAtom(dpy, "_RICE_TAGS", False), XA_CARDINAL, 32,
				PropModeReplace, (unsigned char *)now, 4);
		}
	}

	/* tags: dots + sliding pill (antialiased) */
	cs = cairo_xlib_surface_create(dpy, drw->drawable, DefaultVisual(dpy, screen), drw->w, drw->h);
	cr = cairo_create(cs);
	for (i = 0; i < LENGTH(tags); i++) {
		double dx = TAGX0 + i * tagw(0) + tagw(0) / 2.0;
		if (tagstyle == 1 || tagstyle == 3)
			continue; /* numbers are drawn below, style 3 shows only the pill */
		if (tagstyle == 2) { /* dashes */
			if (urg & 1 << i) { setpx(cr, scheme[SchemeSel][ColBg].pixel, 1); capsule(cr, dx - 8, cy - 2, 16, 4); }
			else if (occ & 1 << i) { setpx(cr, scheme[SchemeNorm][ColFg].pixel, 1); capsule(cr, dx - 7, cy - 1.5, 14, 3); }
			else { setpx(cr, scheme[SchemeNorm][ColBorder].pixel, 1); capsule(cr, dx - 4, cy - 1, 8, 2); }
			cairo_fill(cr);
			continue;
		}
		if (urg & 1 << i) { setpx(cr, scheme[SchemeSel][ColBg].pixel, 1); cairo_arc(cr, dx, cy, 4, 0, 2 * PI); }
		else if (occ & 1 << i) { setpx(cr, scheme[SchemeNorm][ColFg].pixel, 1); cairo_arc(cr, dx, cy, 3.5, 0, 2 * PI); }
		else { setpx(cr, scheme[SchemeNorm][ColBorder].pixel, 1); cairo_arc(cr, dx, cy, 2.5, 0, 2 * PI); }
		cairo_fill(cr);
	}
	if (!m->pinit) { /* first draw: place the pill without waiting for animstep */
		int f = -1, l = -1;
		for (i = 0; i < LENGTH(tags); i++)
			if (m->tagset[m->seltags] & 1 << i) { if (f < 0) f = i; l = i; }
		if (f >= 0) {
			m->pl = TAGX0 + f * tagw(0) + 2; m->pr = TAGX0 + l * tagw(0) + tagw(0) - 2;
			m->pinit = 1;
		}
	}
	if (m->pinit) {
		setpx(cr, scheme[SchemeSel][ColBg].pixel, 1);
		capsule(cr, m->pl, cy - 4.5, m->pr - m->pl, 9);
		cairo_fill(cr);
	}
	x = TAGX0 + LENGTH(tags) * tagw(0);
	/* layout symbol: accent capsule in canvas mode */
	w = LTW(m);
	if (m->canvas) {
		setpx(cr, scheme[SchemeSel][ColBg].pixel, 1);
		capsule(cr, x + 2, cy - 10, w - 4, 20);
		cairo_fill(cr);
	}
	{
		int acx, ckx, ckw, icx, hi, lvl;
		const char *ck = clocktext(&lvl);
		rlayout(bw, &acx, &ckx, &ckw, &icx, &hi);
		avatar(cr, acx, cy, avatard());
		if (hi) volicon(cr, icx, cy, muted() ? 0 : lvl, scheme[SchemeNorm][ColFg].pixel);
		drawtraymirror(cr, m, bw, rw);
		cairo_destroy(cr);
		cairo_surface_destroy(cs);
		drw->nofill = 1;
		drw_setscheme(drw, scheme[SchemeNorm]);
		drw_text(drw, ckx, 0, ckw + 2, bh, 0, ck, 0);
		drw->nofill = 0;
	}
	if (tagstyle == 1) { /* tag numbers, text colour follows the pill */
		Clr nc[3];
		drw->nofill = 1;
		for (i = 0; i < LENGTH(tags); i++) {
			char nb[4];
			int sel = (m->tagset[m->seltags] & 1 << i) != 0, tx;
			snprintf(nb, sizeof nb, "%u", i + 1);
			nc[ColFg] = sel ? scheme[SchemeSel][ColFg] : (occ & 1 << i) ? scheme[SchemeNorm][ColFg] : scheme[SchemeNorm][ColBorder];
			nc[ColBg] = scheme[SchemeNorm][ColBg]; nc[ColBorder] = scheme[SchemeNorm][ColBorder];
			drw_setscheme(drw, nc);
			tx = TAGX0 + i * tagw(0) + (tagw(0) - (TEXTW(nb) - lrpad)) / 2;
			drw_text(drw, tx, 0, tagw(0), bh, 0, nb, 0);
		}
		drw->nofill = 0;
	}
	drw->nofill = 1;
	if (showlayout) {
		Clr cl[3];
		cl[ColFg] = scheme[m->canvas ? SchemeSel : SchemeNorm][ColFg];
		cl[ColBg] = scheme[SchemeNorm][ColBg];
		cl[ColBorder] = scheme[SchemeNorm][ColBorder];
		drw_setscheme(drw, cl);
		x = drw_text(drw, x, 0, w, bh, lrpad / 2, layoutlabel(m), 0);
	}
	drw->nofill = 0;

	/* title, centered in the free middle */
	if (showtitle && (w = bw - rw - stw - x) > bh && m->sel) {
		int tl = TEXTW(m->sel->name), pad = tl < w ? (w - tl) / 2 + lrpad / 2 : lrpad / 2;
		drw->nofill = 1;
		drw_setscheme(drw, scheme[SchemeNorm]);
		drw_text(drw, x, 0, w, bh, pad, m->sel->name, 0);
		drw->nofill = 0;
	}
	drw_map(drw, m->barwin, 0, 0, bw, bh);
}

void
drawbars(void)
{
	Monitor *m;

	for (m = mons; m; m = m->next)
		drawbar(m);
}

void
enternotify(XEvent *e)
{
	Client *c;
	Monitor *m;
	XCrossingEvent *ev = &e->xcrossing;

	if ((ev->mode != NotifyNormal || ev->detail == NotifyInferior) && ev->window != root)
		return;
	c = wintoclient(ev->window);
	m = c ? c->mon : wintomon(ev->window);
	if (m != selmon) {
		unfocus(selmon->sel, 1);
		selmon = m;
	} else if (!c || c == selmon->sel)
		return;
	focus(c);
}

void
expose(XEvent *e)
{
	Monitor *m;
	XExposeEvent *ev = &e->xexpose;

	if (ev->count == 0 && (m = wintomon(ev->window))) {
		drawbar(m);
		if (m == selmon)
			updatesystray();
	}
}

void
focus(Client *c)
{
	shellfocus = 0;
	if (!c || !ISVISIBLE(c))
		for (c = selmon->stack; c && !ISVISIBLE(c); c = c->snext);
	if (c) { /* at most one outgoing outline: drop any still fading from earlier switches */
		Monitor *mm; Client *k;
		for (mm = mons; mm; mm = mm->next)
			for (k = mm->clients; k; k = k->next)
				if (k != c && k != selmon->sel && k->hasb && !k->bt) {
					k->hasb = 0; k->bm = 0;
					XSetWindowBorder(dpy, k->win, scheme[SchemeNorm][ColBorder].pixel);
					reborder(k);
				}
	}
	if (selmon->sel && selmon->sel != c)
		unfocus(selmon->sel, 0);
	if (c) {
		if (c->mon != selmon)
			selmon = c->mon;
		if (c->isurgent)
			seturgent(c, 0);
		detachstack(c);
		attachstack(c);
		grabbuttons(c, 1);
		setfocus(c);
	} else {
		XSetInputFocus(dpy, root, RevertToPointerRoot, CurrentTime);
		XDeleteProperty(dpy, root, netatom[NetActiveWindow]);
	}
	selmon->sel = c;
	if (c) {
		c->hasb = 1; c->bt = 1;
		if (noanim) c->bm = 1;
		XSetWindowBorder(dpy, c->win, blendpx(scheme[SchemeNorm][ColBorder].pixel,
			scheme[SchemeSel][ColBorder].pixel, ease(c->bm)));
		reborder(c);
		if (c->bm < 1) baranim = 1;
	}
	if (systray && showsystray && !systraypinning && traymon != selmon)
		updatesystray(); /* tray follows the focused monitor */
	drawbars();
}

/* there are some broken focus acquiring clients needing extra handling */
void
focusin(XEvent *e)
{
	XFocusChangeEvent *ev = &e->xfocus;

	if (shellfocus && ev->window == shellfocus)
		return;
	if (selmon->sel && ev->window != selmon->sel->win)
		setfocus(selmon->sel);
}

void
focusmon(const Arg *arg)
{
	Monitor *m;

	if (!mons->next)
		return;
	if ((m = dirtomon(arg->i)) == selmon)
		return;
	unfocus(selmon->sel, 0);
	selmon = m;
	focus(NULL);
}

void
focusstack(const Arg *arg)
{
	Client *c = NULL, *i;

	if (!selmon->sel || (selmon->sel->isfullscreen && lockfullscreen))
		return;
	if (arg->i > 0) {
		for (c = selmon->sel->next; c && !ISVISIBLE(c); c = c->next);
		if (!c)
			for (c = selmon->clients; c && !ISVISIBLE(c); c = c->next);
	} else {
		for (i = selmon->clients; i != selmon->sel; i = i->next)
			if (ISVISIBLE(i))
				c = i;
		if (!c)
			for (; i; i = i->next)
				if (ISVISIBLE(i))
					c = i;
	}
	if (c) {
		focus(c);
		restack(selmon);
	}
}

Atom
getatomprop(Client *c, Atom prop)
{
	int format;
	unsigned long nitems, dl;
	unsigned char *p = NULL;
	Atom da, atom = None;

	/* FIXME getatomprop should return the number of items and a pointer to
	 * the stored data instead of this workaround */
	Atom req = XA_ATOM;
	if (prop == xatom[XembedInfo])
		req = xatom[XembedInfo];

	if (XGetWindowProperty(dpy, c->win, prop, 0L, sizeof atom, False, req,
		&da, &format, &nitems, &dl, &p) == Success && p) {
		if (nitems > 0 && format == 32)
			atom = *(long *)p;
		if (da == xatom[XembedInfo] && nitems == 2 && format == 32)
			atom = ((long *)p)[1];
		XFree(p);
	}
	return atom;
}

unsigned int
getsystraywidth()
{
	unsigned int w = 0;
	Client *i;
	if(showsystray)
		for(i = systray->icons; i; w += i->w + systrayspacing, i = i->next) ;
	return w ? w + systrayspacing : 1;
}

int
getrootptr(int *x, int *y)
{
	int di;
	unsigned int dui;
	Window dummy;

	return XQueryPointer(dpy, root, &dummy, &dummy, x, y, &di, &di, &dui);
}

long
getstate(Window w)
{
	int format;
	long result = -1;
	unsigned char *p = NULL;
	unsigned long n, extra;
	Atom real;

	if (XGetWindowProperty(dpy, w, wmatom[WMState], 0L, 2L, False, wmatom[WMState],
		&real, &format, &n, &extra, &p) != Success)
		return -1;
	if (n != 0 && format == 32)
		result = *(long *)p;
	XFree(p);
	return result;
}

int
gettextprop(Window w, Atom atom, char *text, unsigned int size)
{
	char **list = NULL;
	int n;
	XTextProperty name;

	if (!text || size == 0)
		return 0;
	text[0] = '\0';
	if (!XGetTextProperty(dpy, w, &name, atom) || !name.nitems)
		return 0;
	if (name.encoding == XA_STRING) {
		strncpy(text, (char *)name.value, size - 1);
	} else if (XmbTextPropertyToTextList(dpy, &name, &list, &n) >= Success && n > 0 && *list) {
		strncpy(text, *list, size - 1);
		XFreeStringList(list);
	}
	text[size - 1] = '\0';
	XFree(name.value);
	return 1;
}

void
grabbuttons(Client *c, int focused)
{
	updatenumlockmask();
	{
		unsigned int i, j;
		unsigned int modifiers[] = { 0, LockMask, numlockmask, numlockmask|LockMask };
		XUngrabButton(dpy, AnyButton, AnyModifier, c->win);
		if (!focused)
			XGrabButton(dpy, AnyButton, AnyModifier, c->win, False,
				BUTTONMASK, GrabModeSync, GrabModeSync, None, None);
		for (i = 0; i < LENGTH(buttons); i++)
			if (buttons[i].click == ClkClientWin)
				for (j = 0; j < LENGTH(modifiers); j++)
					XGrabButton(dpy, buttons[i].button,
						buttons[i].mask | modifiers[j],
						c->win, False, BUTTONMASK,
						GrabModeAsync, GrabModeSync, None, None);
	}
}

void
grabkeys(void)
{
	updatenumlockmask();
	{
		unsigned int i, j, k;
		unsigned int modifiers[] = { 0, LockMask, numlockmask, numlockmask|LockMask };
		int start, end, skip;
		KeySym *syms;

		XUngrabKey(dpy, AnyKey, AnyModifier, root);
		XDisplayKeycodes(dpy, &start, &end);
		syms = XGetKeyboardMapping(dpy, start, end - start + 1, &skip);
		if (!syms)
			return;
		for (k = start; k <= end; k++)
			for (i = 0; i < ncur; i++)
				/* skip modifier codes, we do that ourselves */
				if (curkeys[i].keysym == syms[(k - start) * skip])
					for (j = 0; j < LENGTH(modifiers); j++)
						XGrabKey(dpy, k,
							 curkeys[i].mod | modifiers[j],
							 root, True,
							 GrabModeAsync, GrabModeAsync);
		XFree(syms);
	}
}

void
incnmaster(const Arg *arg)
{
	selmon->nmaster = MAX(selmon->nmaster + arg->i, 0);
	arrange(selmon);
}

#ifdef XINERAMA
static int
isuniquegeom(XineramaScreenInfo *unique, size_t n, XineramaScreenInfo *info)
{
	while (n--)
		if (unique[n].x_org == info->x_org && unique[n].y_org == info->y_org
		&& unique[n].width == info->width && unique[n].height == info->height)
			return 0;
	return 1;
}
#endif /* XINERAMA */

void
keypress(XEvent *e)
{
	unsigned int i;
	KeySym keysym;
	XKeyEvent *ev;

	ev = &e->xkey;
	keysym = XKeycodeToKeysym(dpy, (KeyCode)ev->keycode, 0);
	syncptrmon(); /* keybinds act on the monitor under the cursor */
	for (i = 0; i < ncur; i++)
		if (keysym == curkeys[i].keysym
		&& CLEANMASK(curkeys[i].mod) == CLEANMASK(ev->state)
		&& curkeys[i].func)
			curkeys[i].func(&(curkeys[i].arg));
}

void
killclient(const Arg *arg)
{
	if (!selmon->sel)
		return;

	if (!sendevent(selmon->sel->win, wmatom[WMDelete], NoEventMask, wmatom[WMDelete], CurrentTime, 0 , 0, 0)) {
		XGrabServer(dpy);
		XSetErrorHandler(xerrordummy);
		XSetCloseDownMode(dpy, DestroyAll);
		XKillClient(dpy, selmon->sel->win);
		XSync(dpy, False);
		XSetErrorHandler(xerror);
		XUngrabServer(dpy);
	}
}

void
loadxrdb()
{
  Display *display;
  char * resm;
  XrmDatabase xrdb;
  char *type;
  XrmValue value;

  display = XOpenDisplay(NULL);

  if (display != NULL) {
    resm = XResourceManagerString(display);

    if (resm != NULL) {
      xrdb = XrmGetStringDatabase(resm);

      if (xrdb != NULL) {
        XRDB_LOAD_COLOR("dwm.normbordercolor", normbordercolor);
        XRDB_LOAD_COLOR("dwm.normbgcolor", normbgcolor);
        XRDB_LOAD_COLOR("dwm.normfgcolor", normfgcolor);
        XRDB_LOAD_COLOR("dwm.selbordercolor", selbordercolor);
        XRDB_LOAD_COLOR("dwm.selbgcolor", selbgcolor);
        XRDB_LOAD_COLOR("dwm.selfgcolor", selfgcolor);
      }
    }
  }

  XCloseDisplay(display);
}

/* make the monitor under the pointer the selected one (new windows land on selmon) */
static void
syncptrmon(void)
{
	int x, y;
	Monitor *m;

	if (getrootptr(&x, &y) && (m = recttomon(x, y, 1, 1)) && m != selmon) {
		unfocus(selmon->sel, 1);
		selmon = m;
		focus(NULL);
	}
}

void
manage(Window w, XWindowAttributes *wa)
{
	Client *c, *t = NULL;
	Window trans = None;
	XWindowChanges wc;

	c = ecalloc(1, sizeof(Client));
	c->win = w;
	/* geometry */
	c->x = c->oldx = wa->x;
	c->y = c->oldy = wa->y;
	c->w = c->oldw = wa->width;
	c->h = c->oldh = wa->height;
	c->oldbw = wa->border_width;
	c->isgame = detectgame(w);

	updatetitle(c);
	if (XGetTransientForHint(dpy, w, &trans) && (t = wintoclient(trans))) {
		c->mon = t->mon;
		c->tags = t->tags;
	} else {
		syncptrmon();
		c->mon = selmon;
		applyrules(c);
	}
	{ /* tags saved by a restart */
		Atom type; int fmt; unsigned long n, after; unsigned char *p = NULL;
		Atom at = XInternAtom(dpy, "_RICE_TAGS", False);
		if (XGetWindowProperty(dpy, w, at, 0, 1, True, XA_CARDINAL, &type, &fmt, &n, &after, &p) == Success && p) {
			if (n == 1 && (*(long *)p & TAGMASK))
				c->tags = (unsigned int)(*(long *)p & TAGMASK);
			XFree(p);
		}
	}

	if (c->mon->canvas && !t) { /* canvas mode: open centred on the visible area, not at the client's own 0,0 */
		c->x = c->mon->wx + (c->mon->ww - WIDTH(c)) / 2;
		c->y = c->mon->wy + (c->mon->wh - HEIGHT(c)) / 2;
	}
	if (c->x + WIDTH(c) > c->mon->wx + c->mon->ww)
		c->x = c->mon->wx + c->mon->ww - WIDTH(c);
	if (c->y + HEIGHT(c) > c->mon->wy + c->mon->wh)
		c->y = c->mon->wy + c->mon->wh - HEIGHT(c);
	c->x = MAX(c->x, c->mon->wx);
	c->y = MAX(c->y, c->mon->wy);
	c->bw = borderpx;

	wc.border_width = c->bw;
	XConfigureWindow(dpy, w, CWBorderWidth, &wc);
	XSetWindowBorder(dpy, w, scheme[SchemeNorm][ColBorder].pixel);
	configure(c); /* propagates border_width, if size doesn't change */
	updatewindowtype(c);
	updatesizehints(c);
	updatewmhints(c);
	XSelectInput(dpy, w, EnterWindowMask|FocusChangeMask|PropertyChangeMask|StructureNotifyMask);
	grabbuttons(c, 0);
	if (!c->isfloating)
		c->isfloating = c->oldstate = trans != None || c->isfixed;
	if (c->isfloating || c->mon->canvas)
		XRaiseWindow(dpy, c->win);
	attach(c);
	attachstack(c);
	XChangeProperty(dpy, root, netatom[NetClientList], XA_WINDOW, 32, PropModeAppend,
		(unsigned char *) &(c->win), 1);
	XMoveResizeWindow(dpy, c->win, c->x + 2 * sw, c->y, c->w, c->h); /* some windows require this */
	setclientstate(c, NormalState);
	if (c->mon == selmon)
		unfocus(selmon->sel, 0);
	c->mon->sel = c;
	arrange(c->mon);
	if (!c->placed) /* floating/canvas: resize() saw no change and skipped it, so place it now */
		resizeclient(c, c->x, c->y, c->w, c->h);
	XMapWindow(dpy, c->win);
	focus(NULL);
}

void
mappingnotify(XEvent *e)
{
	XMappingEvent *ev = &e->xmapping;

	XRefreshKeyboardMapping(ev);
	if (ev->request == MappingKeyboard)
		grabkeys();
}

void
maprequest(XEvent *e)
{
	static XWindowAttributes wa;
	XMapRequestEvent *ev = &e->xmaprequest;

	Client *i;
	if ((i = wintosystrayicon(ev->window))) {
		sendevent(i->win, netatom[Xembed], StructureNotifyMask, CurrentTime, XEMBED_WINDOW_ACTIVATE, 0, systray->win, XEMBED_EMBEDDED_VERSION);
		resizebarwin(selmon);
		updatesystray();
	}

	if (!XGetWindowAttributes(dpy, ev->window, &wa) || wa.override_redirect)
		return;
	if (isshellwin(ev->window)) { /* Quickshell panels / popups: mapped as they are, never tiled */
		XMapWindow(dpy, ev->window);
		{ /* aboveWindows: false = _NET_WM_STATE_BELOW: keep it under the clients, or it eats their clicks */
			Atom da, *st = NULL, below = XInternAtom(dpy, "_NET_WM_STATE_BELOW", False);
			int di;
			unsigned long sn = 0, sl, si;
			if (XGetWindowProperty(dpy, ev->window, XInternAtom(dpy, "_NET_WM_STATE", False), 0, 16, False, XA_ATOM,
					&da, &di, &sn, &sl, (unsigned char **)&st) == Success && st) {
				for (si = 0; si < sn; si++)
					if (st[si] == below)
						XLowerWindow(dpy, ev->window);
				XFree(st);
			}
		}
		XShapeSelectInput(dpy, ev->window, ShapeNotifyMask);
		shellcheck(ev->window);
		return;
	}
	if (!wintoclient(ev->window))
		manage(ev->window, &wa);
}

static int
isshellwin(Window w)
{
	Atom da, *types = NULL, dock = XInternAtom(dpy, "_NET_WM_WINDOW_TYPE_DOCK", False),
		kde = XInternAtom(dpy, "_KDE_NET_WM_WINDOW_TYPE_OVERRIDE", False);
	int di;
	unsigned long n = 0, left, i;
	int hit = 0;

	if (XGetWindowProperty(dpy, w, netatom[NetWMWindowType], 0L, 16L, False, XA_ATOM, &da, &di, &n, &left,
			(unsigned char **)&types) == Success && types) {
		for (i = 0; i < n; i++)
			if (types[i] == dock || types[i] == kde)
				hit = 1;
		XFree(types);
	}
	return hit;
}

void
monocle(Monitor *m)
{
	unsigned int n = 0;
	Client *c;

	for (c = m->clients; c; c = c->next)
		if (ISVISIBLE(c))
			n++;
	if (n > 0) /* override layout symbol */
		snprintf(m->ltsymbol, sizeof m->ltsymbol, "[%d]", n);
	for (c = nexttiled(m->clients); c; c = nexttiled(c->next))
		resize(c, m->wx + gp(m), m->wy + gp(m), m->ww - 2 * gp(m) - 2 * c->bw, m->wh - 2 * gp(m) - 2 * c->bw, 0);
}

void
motionnotify(XEvent *e)
{
	static Monitor *mon = NULL;
	Monitor *m;
	XMotionEvent *ev = &e->xmotion;

	if (ev->window != root)
		return;
	if ((m = recttomon(ev->x_root, ev->y_root, 1, 1)) != mon && mon) {
		unfocus(selmon->sel, 1);
		selmon = m;
		focus(NULL);
	}
	mon = m;
}

void
movemouse(const Arg *arg)
{
	int x, y, ocx, ocy, nx, ny;
	Client *c;
	Monitor *m;
	XEvent ev;
	Time lasttime = 0;

	if (!(c = selmon->sel))
		return;
	if (c->isfullscreen) /* no support moving fullscreen windows by mouse */
		return;
	restack(selmon);
	ocx = c->x;
	ocy = c->y;
	if (XGrabPointer(dpy, root, False, MOUSEMASK, GrabModeAsync, GrabModeAsync,
		None, cursor[CurMove]->cursor, CurrentTime) != GrabSuccess)
		return;
	if (!getrootptr(&x, &y))
		return;
	noanim = 1;
	do {
		XMaskEvent(dpy, MOUSEMASK|ExposureMask|SubstructureRedirectMask, &ev);
		switch(ev.type) {
		case ConfigureRequest:
		case Expose:
		case MapRequest:
			handler[ev.type](&ev);
			break;
		case MotionNotify:
			if ((ev.xmotion.time - lasttime) <= (1000 / refreshrate))
				continue;
			lasttime = ev.xmotion.time;

			nx = ocx + (ev.xmotion.x - x);
			ny = ocy + (ev.xmotion.y - y);
			if (abs(selmon->wx - nx) < snap)
				nx = selmon->wx;
			else if (abs((selmon->wx + selmon->ww) - (nx + WIDTH(c))) < snap)
				nx = selmon->wx + selmon->ww - WIDTH(c);
			if (abs(selmon->wy - ny) < snap)
				ny = selmon->wy;
			else if (abs((selmon->wy + selmon->wh) - (ny + HEIGHT(c))) < snap)
				ny = selmon->wy + selmon->wh - HEIGHT(c);
			if (!c->isfloating && selmon->lt[selmon->sellt]->arrange
			&& (abs(nx - c->x) > snap || abs(ny - c->y) > snap))
				togglefloating(NULL);
			if (!selmon->lt[selmon->sellt]->arrange || c->isfloating)
				resize(c, nx, ny, c->w, c->h, 1);
			break;
		}
	} while (ev.type != ButtonRelease);
	XUngrabPointer(dpy, CurrentTime);
	noanim = 0;
	if ((m = recttomon(c->x, c->y, c->w, c->h)) != selmon) {
		sendmon(c, m);
		selmon = m;
		focus(NULL);
	}
}

Client *
nexttiled(Client *c)
{
	for (; c && (c->isfloating || !ISVISIBLE(c)); c = c->next);
	return c;
}

void
pop(Client *c)
{
	detach(c);
	attach(c);
	focus(c);
	arrange(c->mon);
}

void
propertynotify(XEvent *e)
{
	Client *c;
	Window trans;
	XPropertyEvent *ev = &e->xproperty;

	if (ev->window == root && ev->atom == ricecmd) {
		ricecmdrun();
		return;
	}
	if (ev->window == root && ev->atom == XA_RESOURCE_MANAGER) {
		xrdb(NULL); /* xrdb -merge changed colors: reload live */
		return;
	}
	if ((c = wintosystrayicon(ev->window))) {
		if (ev->atom == XA_WM_NORMAL_HINTS) {
			updatesizehints(c);
			updatesystrayicongeom(c, c->w, c->h);
		}
		else
			updatesystrayiconstate(c, ev);
		resizebarwin(selmon);
		updatesystray();
	}

	if ((ev->window == root) && (ev->atom == XA_WM_NAME))
		updatestatus();
	else if (ev->state == PropertyDelete)
		return; /* ignore */
	else if ((c = wintoclient(ev->window))) {
		switch(ev->atom) {
		default: break;
		case XA_WM_TRANSIENT_FOR:
			if (!c->isfloating && (XGetTransientForHint(dpy, c->win, &trans)) &&
				(c->isfloating = (wintoclient(trans)) != NULL))
				arrange(c->mon);
			break;
		case XA_WM_NORMAL_HINTS:
			c->hintsvalid = 0;
			break;
		case XA_WM_HINTS:
			updatewmhints(c);
			drawbars();
			break;
		}
		if (ev->atom == XA_WM_NAME || ev->atom == netatom[NetWMName]) {
			updatetitle(c);
			if (c == c->mon->sel)
				drawbar(c->mon);
		}
		if (ev->atom == netatom[NetWMWindowType])
			updatewindowtype(c);
	}
}

void
quit(const Arg *arg)
{
	if (arg && arg->i)
		restart = 1;
	running = 0;
}

void
sighup(int unused)
{
	Arg a = {.i = 1};
	quit(&a);
}

void
sigterm(int unused)
{
	Arg a = {.i = 0};
	quit(&a);
}

Monitor *
recttomon(int x, int y, int w, int h)
{
	Monitor *m, *r = selmon;
	int a, area = 0;

	for (m = mons; m; m = m->next)
		if ((a = INTERSECT(x, y, w, h, m)) > area) {
			area = a;
			r = m;
		}
	return r;
}

void
removesystrayicon(Client *i)
{
	Client **ii;

	if (!showsystray || !i)
		return;
	for (ii = &systray->icons; *ii && *ii != i; ii = &(*ii)->next);
	if (ii)
		*ii = i->next;
	free(i);
}

void
resize(Client *c, int x, int y, int w, int h, int interact)
{
	if (applysizehints(c, &x, &y, &w, &h, interact))
		resizeclient(c, x, y, w, h);
}

void
resizebarwin(Monitor *m) {
	XMoveResizeWindow(dpy, m->barwin, m->wx + spa(m), m->by, m->ww - 2 * spa(m), bh);
}

/* A game started by Steam (class steam_app_*, or SteamGameId/SteamAppId in its environment).
 * Games draw with OpenGL/Vulkan + vsync, and on NVIDIA every window RESIZE then stalls picom
 * (it rebinds the pixmap behind the game's vsync): resize easing fell to ~15 fps, moves stay smooth. */
static int
detectgame(Window w)
{
	XClassHint ch = { NULL, NULL };
	Atom type; int fmt, game = 0; unsigned long n, after; unsigned char *p = NULL;

	if (XGetClassHint(dpy, w, &ch)) {
		if ((ch.res_class && !strncasecmp(ch.res_class, "steam_app_", 10))
		|| (ch.res_name && !strncasecmp(ch.res_name, "steam_app_", 10)))
			game = 1;
		if (ch.res_class) XFree(ch.res_class);
		if (ch.res_name) XFree(ch.res_name);
	}
	if (!game && XGetWindowProperty(dpy, w, XInternAtom(dpy, "_NET_WM_PID", False), 0, 1, False,
	    XA_CARDINAL, &type, &fmt, &n, &after, &p) == Success && p) {
		if (n == 1 && fmt == 32) {
			char path[64], buf[65536];
			FILE *f;
			size_t len, i;
			snprintf(path, sizeof path, "/proc/%lu/environ", *(unsigned long *)p);
			if ((f = fopen(path, "r"))) {
				len = fread(buf, 1, sizeof buf - 1, f);
				fclose(f);
				for (i = 0; i < len && !game; i += strlen(buf + i) + 1) {
					buf[len] = '\0';
					if (!strncmp(buf + i, "SteamGameId=", 12) || !strncmp(buf + i, "SteamAppId=", 11))
						game = 1;
				}
			}
		}
		XFree(p);
	}
	return game;
}

static int
gamerunning(void)
{
	Monitor *m;
	Client *c;

	for (m = mons; m; m = m->next)
		for (c = m->clients; c; c = c->next)
			if (c->isgame)
				return 1;
	return 0;
}

void
resizeclient(Client *c, int x, int y, int w, int h)
{
	c->oldx = c->x; c->x = x;
	c->oldy = c->y; c->y = y;
	c->oldw = c->w; c->w = w;
	c->oldh = c->h; c->h = h;
	if (noanim || companim) {
		c->anim = 0; c->park = 0; c->placed = 1;
		c->ax = x; c->ay = y; c->aw = w; c->ah = h;
		applygeom(c);
		configure(c);
		if (panning) XFlush(dpy); else XSync(dpy, False);
		return;
	}
	if (!c->placed) { /* new window: open at its final size. Resizing a new terminal from a tiny
	                   * strip made the shell see a few columns and garbled the prompt; picom
	                   * does the fade/scale-in instead. */
		c->placed = 1;
		c->anim = 0;
		c->ax = x; c->ay = y; c->aw = w; c->ah = h;
		applygeom(c);
		configure(c);
		return;
	}
	configure(c);
	if (!c->anim && (int)(c->ax + 0.5f) == x && (int)(c->ay + 0.5f) == y
	&& (int)(c->aw + 0.5f) == w && (int)(c->ah + 0.5f) == h)
		return;
	if (gamerunning() && ((int)(c->aw + 0.5f) != w || (int)(c->ah + 0.5f) != h)) {
		/* a game is open: final size at once (one resize), only the position eases */
		c->aw = w; c->ah = h;
		applygeom(c);
	}
	c->fx = c->ax; c->fy = c->ay; c->fw = c->aw; c->fh = c->ah;
	c->tx = x; c->ty = y; c->tw = w; c->th = h;
	c->t0 = nowsec();
	c->anim = 1; c->park = 0;
	baranim = 1;
}

void
resizerequest(XEvent *e)
{
	XResizeRequestEvent *ev = &e->xresizerequest;
	Client *i;

	if ((i = wintosystrayicon(ev->window))) {
		updatesystrayicongeom(i, ev->width, ev->height);
		resizebarwin(selmon);
		updatesystray();
	}
}

void
resizemouse(const Arg *arg)
{
	int ocx, ocy, nw, nh;
	Client *c;
	Monitor *m;
	XEvent ev;
	Time lasttime = 0;

	if (!(c = selmon->sel))
		return;
	if (c->isfullscreen) /* no support resizing fullscreen windows by mouse */
		return;
	restack(selmon);
	ocx = c->x;
	ocy = c->y;
	if (XGrabPointer(dpy, root, False, MOUSEMASK, GrabModeAsync, GrabModeAsync,
		None, cursor[CurResize]->cursor, CurrentTime) != GrabSuccess)
		return;
	XWarpPointer(dpy, None, c->win, 0, 0, 0, 0, c->w + c->bw - 1, c->h + c->bw - 1);
	noanim = 1;
	do {
		XMaskEvent(dpy, MOUSEMASK|ExposureMask|SubstructureRedirectMask, &ev);
		switch(ev.type) {
		case ConfigureRequest:
		case Expose:
		case MapRequest:
			handler[ev.type](&ev);
			break;
		case MotionNotify:
			if ((ev.xmotion.time - lasttime) <= (1000 / refreshrate))
				continue;
			lasttime = ev.xmotion.time;

			nw = MAX(ev.xmotion.x - ocx - 2 * c->bw + 1, 1);
			nh = MAX(ev.xmotion.y - ocy - 2 * c->bw + 1, 1);
			if (c->mon->wx + nw >= selmon->wx && c->mon->wx + nw <= selmon->wx + selmon->ww
			&& c->mon->wy + nh >= selmon->wy && c->mon->wy + nh <= selmon->wy + selmon->wh)
			{
				if (!c->isfloating && selmon->lt[selmon->sellt]->arrange
				&& (abs(nw - c->w) > snap || abs(nh - c->h) > snap))
					togglefloating(NULL);
			}
			if (!selmon->lt[selmon->sellt]->arrange || c->isfloating)
				resize(c, c->x, c->y, nw, nh, 1);
			break;
		}
	} while (ev.type != ButtonRelease);
	XWarpPointer(dpy, None, c->win, 0, 0, 0, 0, c->w + c->bw - 1, c->h + c->bw - 1);
	XUngrabPointer(dpy, CurrentTime);
	noanim = 0;
	while (XCheckMaskEvent(dpy, EnterWindowMask, &ev));
	if ((m = recttomon(c->x, c->y, c->w, c->h)) != selmon) {
		sendmon(c, m);
		selmon = m;
		focus(NULL);
	}
}

void
restack(Monitor *m)
{
	Client *c;
	XEvent ev;
	XWindowChanges wc;

	drawbar(m);
	if (!m->sel)
		return;
	if (m->sel->isfloating || !m->lt[m->sellt]->arrange)
		XRaiseWindow(dpy, m->sel->win);
	if (m->lt[m->sellt]->arrange) {
		wc.stack_mode = Below;
		wc.sibling = m->barwin;
		for (c = m->stack; c; c = c->snext)
			if (!c->isfloating && ISVISIBLE(c)) {
				XConfigureWindow(dpy, c->win, CWSibling|CWStackMode, &wc);
				wc.sibling = c->win;
			}
	}
	raiseshell();
	XSync(dpy, False);
	while (XCheckMaskEvent(dpy, EnterWindowMask, &ev));
}

/* Keep the Quickshell ABOVE windows (the dock) over every window, floating ones included, except on a monitor whose
 * selected client is fullscreen (a game): there the fullscreen window stays on top. */
static void
raiseshell(void)
{
	int i, j;
	XWindowAttributes wa;
	Monitor *m;

	for (i = 0; i < nshellabove; i++) {
		if (!XGetWindowAttributes(dpy, shellabove[i], &wa)) { /* gone: forget it */
			for (j = i; j < nshellabove - 1; j++)
				shellabove[j] = shellabove[j + 1];
			nshellabove--; i--;
			continue;
		}
		if (wa.map_state != IsViewable)
			continue;
		m = recttomon(wa.x, wa.y, wa.width, wa.height);
		if (m && m->sel && m->sel->isfullscreen && ISVISIBLE(m->sel))
			continue;
		XRaiseWindow(dpy, shellabove[i]);
	}
}

/* A Quickshell menu / launcher / panel is open when its ABOVE window has a big visible shape (the shell masks the window to its
 * card while open and to nothing while closed). Qt never asks for the keyboard on X11, so give the open one the X focus
 * (typing, Esc) and hand it back to the client when the shape goes away. */
static void
shellcheck(Window w)
{
	Atom da, *st = NULL, above = XInternAtom(dpy, "_NET_WM_STATE_ABOVE", False);
	int di, ab = 0, bounding = 0, xb, yb, xc, yc;
	unsigned int wb, hb, wc, hc;
	unsigned long sn = 0, sl, si;
	Bool bs, cs;

	if (wintoclient(w))
		return;
	if (XGetWindowProperty(dpy, w, XInternAtom(dpy, "_NET_WM_STATE", False), 0, 16, False, XA_ATOM,
			&da, &di, &sn, &sl, (unsigned char **)&st) == Success && st) {
		for (si = 0; si < sn; si++)
			if (st[si] == above)
				ab = 1;
		XFree(st);
	}
	if (!ab)
		return;
	for (si = 0; si < (unsigned long)nshellabove && shellabove[si] != w; si++);
	if (si == (unsigned long)nshellabove && nshellabove < MAXSHELLABOVE)
		shellabove[nshellabove++] = w;
	if (XShapeQueryExtents(dpy, w, &bs, &xb, &yb, &wb, &hb, &cs, &xc, &yc, &wc, &hc))
		bounding = bs && wb >= 300 && hb >= 300;
	if (bounding) {
		XSetInputFocus(dpy, w, RevertToPointerRoot, CurrentTime);
		shellfocus = w;
	} else if (shellfocus == w) {
		shellfocus = 0;
		focus(NULL);
	}
}

void
run(void)
{
	XEvent ev;
	/* main event loop */
	XSync(dpy, False);
	while (running) {
		if (baranim && !XPending(dpy)) {
			fd_set fds;
			struct timeval tv = { 0, 8000 };
			FD_ZERO(&fds);
			FD_SET(ConnectionNumber(dpy), &fds);
			if (select(ConnectionNumber(dpy) + 1, &fds, NULL, NULL, &tv) == 0) {
				animstep();
				continue;
			}
		}
		if (traytemp && nowsec() - traytemp_t > 0.9) { /* put the tray back on its own bar */
			traytemp = NULL;
			updatesystray();
			drawbars();
		}
		if (!baranim && !XPending(dpy) && (traytemp || (systray && systray->icons && MIRRORCOND))) {
			fd_set fds;
			struct timeval tv = { 0, 300000 };
			FD_ZERO(&fds);
			FD_SET(ConnectionNumber(dpy), &fds);
			if (select(ConnectionNumber(dpy) + 1, &fds, NULL, NULL, &tv) == 0) {
				Monitor *tm;
				for (tm = mons; tm; tm = tm->next)
					if (MIRRORTM)
						drawbar(tm); /* icons repaint on their own: keep the mirrors fresh */
				continue;
			}
		}
		if (XNextEvent(dpy, &ev))
			break;
		if (shapeev >= 0 && ev.type == shapeev) {
			shellcheck(((XShapeEvent *)&ev)->window);
			continue;
		}
		if (ev.type < LASTEvent && handler[ev.type])
			handler[ev.type](&ev); /* call handler */
	}
}

void
scan(void)
{
	unsigned int i, num;
	Window d1, d2, *wins = NULL;
	XWindowAttributes wa;

	if (XQueryTree(dpy, root, &d1, &d2, &wins, &num)) {
		for (i = 0; i < num; i++) {
			if (!XGetWindowAttributes(dpy, wins[i], &wa)
			|| wa.override_redirect || XGetTransientForHint(dpy, wins[i], &d1))
				continue;
			if (isshellwin(wins[i])) { /* Quickshell windows that were already up (dwm restart): never manage them */
				XShapeSelectInput(dpy, wins[i], ShapeNotifyMask);
				shellcheck(wins[i]);
				continue;
			}
			if (wa.map_state == IsViewable || getstate(wins[i]) == IconicState)
				manage(wins[i], &wa);
		}
		for (i = 0; i < num; i++) { /* now the transients */
			if (!XGetWindowAttributes(dpy, wins[i], &wa))
				continue;
			if (XGetTransientForHint(dpy, wins[i], &d1)
			&& (wa.map_state == IsViewable || getstate(wins[i]) == IconicState))
				manage(wins[i], &wa);
		}
		if (wins)
			XFree(wins);
	}
}

void
sendmon(Client *c, Monitor *m)
{
	if (c->mon == m)
		return;
	unfocus(c, 1);
	detach(c);
	detachstack(c);
	c->mon = m;
	c->tags = m->tagset[m->seltags]; /* assign tags of target monitor */
	attach(c);
	attachstack(c);
	if (c->isfullscreen)
		resizeclient(c, m->mx, m->my, m->mw, m->mh);
	focus(NULL);
	arrange(NULL);
}

void
setclientstate(Client *c, long state)
{
	long data[] = { state, None };

	XChangeProperty(dpy, c->win, wmatom[WMState], wmatom[WMState], 32,
		PropModeReplace, (unsigned char *)data, 2);
}

int
sendevent(Window w, Atom proto, int mask, long d0, long d1, long d2, long d3, long d4)
{
	int n;
	Atom *protocols, mt;
	int exists = 0;
	XEvent ev;

	if (proto == wmatom[WMTakeFocus] || proto == wmatom[WMDelete]) {
		mt = wmatom[WMProtocols];
		if (XGetWMProtocols(dpy, w, &protocols, &n)) {
			while (!exists && n--)
				exists = protocols[n] == proto;
			XFree(protocols);
		}
	}
	else {
		exists = True;
		mt = proto;
	}

	if (exists) {
		ev.type = ClientMessage;
		ev.xclient.window = w;
		ev.xclient.message_type = mt;
		ev.xclient.format = 32;
		ev.xclient.data.l[0] = d0;
		ev.xclient.data.l[1] = d1;
		ev.xclient.data.l[2] = d2;
		ev.xclient.data.l[3] = d3;
		ev.xclient.data.l[4] = d4;
		XSendEvent(dpy, w, False, mask, &ev);
	}
	return exists;
}

void
setfocus(Client *c)
{
	if (!c->neverfocus)
		XSetInputFocus(dpy, c->win, RevertToPointerRoot, CurrentTime);
	XChangeProperty(dpy, root, netatom[NetActiveWindow], XA_WINDOW, 32,
		PropModeReplace, (unsigned char *)&c->win, 1);
	sendevent(c->win, wmatom[WMTakeFocus], NoEventMask, wmatom[WMTakeFocus], CurrentTime, 0, 0, 0);
}

void
setfullscreen(Client *c, int fullscreen)
{
	if (fullscreen && !c->isfullscreen) {
		XChangeProperty(dpy, c->win, netatom[NetWMState], XA_ATOM, 32,
			PropModeReplace, (unsigned char*)&netatom[NetWMFullscreen], 1);
		c->isfullscreen = 1;
		c->oldstate = c->isfloating;
		c->oldbw = c->bw;
		c->bw = 0;
		c->isfloating = 1;
		resizeclient(c, c->mon->mx, c->mon->my, c->mon->mw, c->mon->mh);
		XRaiseWindow(dpy, c->win);
	} else if (!fullscreen && c->isfullscreen){
		XChangeProperty(dpy, c->win, netatom[NetWMState], XA_ATOM, 32,
			PropModeReplace, (unsigned char*)0, 0);
		c->isfullscreen = 0;
		c->isfloating = c->oldstate;
		c->bw = c->oldbw;
		c->x = c->oldx;
		c->y = c->oldy;
		c->w = c->oldw;
		c->h = c->oldh;
		resizeclient(c, c->x, c->y, c->w, c->h);
		arrange(c->mon);
	}
}

void
setlayout(const Arg *arg)
{
	if (!arg || !arg->v || arg->v != selmon->lt[selmon->sellt])
		selmon->sellt ^= 1;
	if (arg && arg->v)
		selmon->lt[selmon->sellt] = (Layout *)arg->v;
	strncpy(selmon->ltsymbol, selmon->lt[selmon->sellt]->symbol, sizeof selmon->ltsymbol);
	if (selmon->sel)
		arrange(selmon);
	else
		drawbar(selmon);
}

/* arg > 1.0 will set mfact absolutely */
void
setmfact(const Arg *arg)
{
	float f;

	if (!arg || !selmon->lt[selmon->sellt]->arrange)
		return;
	f = arg->f < 1.0 ? arg->f + selmon->mfact : arg->f - 1.0;
	if (f < 0.05 || f > 0.95)
		return;
	selmon->mfact = f;
	arrange(selmon);
}

void
setup(void)
{
	int i;
	XSetWindowAttributes wa;
	Atom utf8string;
	struct sigaction sa;

	{ int eb, er; if (XShapeQueryExtension(dpy, &eb, &er)) shapeev = eb + ShapeNotify; }
	/* do not transform children into zombies when they terminate */
	sigemptyset(&sa.sa_mask);
	sa.sa_flags = SA_NOCLDSTOP | SA_NOCLDWAIT | SA_RESTART;
	sa.sa_handler = SIG_IGN;
	sigaction(SIGCHLD, &sa, NULL);

	/* clean up any zombies (inherited from .xinitrc etc) immediately */
	while (waitpid(-1, NULL, WNOHANG) > 0);

	/* init screen */
	screen = DefaultScreen(dpy);
	sw = DisplayWidth(dpy, screen);
	sh = DisplayHeight(dpy, screen);
	root = RootWindow(dpy, screen);
	drw = drw_create(dpy, screen, root, sw, sh);
	if (!drw_fontset_create(drw, fonts, LENGTH(fonts)))
		die("no fonts could be loaded.");
	lrpad = drw->fonts->h;
	bh = drw->fonts->h + 2 + barpad;
	updategeom();
	/* init atoms */
	utf8string = XInternAtom(dpy, "UTF8_STRING", False);
	wmatom[WMProtocols] = XInternAtom(dpy, "WM_PROTOCOLS", False);
	wmatom[WMDelete] = XInternAtom(dpy, "WM_DELETE_WINDOW", False);
	wmatom[WMState] = XInternAtom(dpy, "WM_STATE", False);
	wmatom[WMTakeFocus] = XInternAtom(dpy, "WM_TAKE_FOCUS", False);
	netatom[NetActiveWindow] = XInternAtom(dpy, "_NET_ACTIVE_WINDOW", False);
	ricecmd = XInternAtom(dpy, "_RICE_CMD", False);
	netatom[NetSupported] = XInternAtom(dpy, "_NET_SUPPORTED", False);
	netatom[NetSystemTray] = XInternAtom(dpy, "_NET_SYSTEM_TRAY_S0", False);
	netatom[NetSystemTrayOP] = XInternAtom(dpy, "_NET_SYSTEM_TRAY_OPCODE", False);
	netatom[NetSystemTrayOrientation] = XInternAtom(dpy, "_NET_SYSTEM_TRAY_ORIENTATION", False);
	netatom[NetSystemTrayOrientationHorz] = XInternAtom(dpy, "_NET_SYSTEM_TRAY_ORIENTATION_HORZ", False);
	netatom[NetWMName] = XInternAtom(dpy, "_NET_WM_NAME", False);
	netatom[NetWMState] = XInternAtom(dpy, "_NET_WM_STATE", False);
	netatom[NetWMCheck] = XInternAtom(dpy, "_NET_SUPPORTING_WM_CHECK", False);
	netatom[NetWMFullscreen] = XInternAtom(dpy, "_NET_WM_STATE_FULLSCREEN", False);
	netatom[NetWMWindowType] = XInternAtom(dpy, "_NET_WM_WINDOW_TYPE", False);
	netatom[NetWMWindowTypeDialog] = XInternAtom(dpy, "_NET_WM_WINDOW_TYPE_DIALOG", False);
	netatom[NetClientList] = XInternAtom(dpy, "_NET_CLIENT_LIST", False);
	xatom[Manager] = XInternAtom(dpy, "MANAGER", False);
	xatom[Xembed] = XInternAtom(dpy, "_XEMBED", False);
	xatom[XembedInfo] = XInternAtom(dpy, "_XEMBED_INFO", False);
	/* init cursors */
	cursor[CurNormal] = drw_cur_create(drw, XC_left_ptr);
	cursor[CurResize] = drw_cur_create(drw, XC_sizing);
	cursor[CurMove] = drw_cur_create(drw, XC_fleur);
	/* init appearance */
	scheme = ecalloc(LENGTH(colors), sizeof(Clr *));
	for (i = 0; i < LENGTH(colors); i++)
		scheme[i] = drw_scm_create(drw, colors[i], 3);
	/* init system tray */
	updatesystray();
	/* init bars */
	updatebars();
	updatestatus();
	/* supporting window for NetWMCheck */
	wmcheckwin = XCreateSimpleWindow(dpy, root, 0, 0, 1, 1, 0, 0, 0);
	XChangeProperty(dpy, wmcheckwin, netatom[NetWMCheck], XA_WINDOW, 32,
		PropModeReplace, (unsigned char *) &wmcheckwin, 1);
	XChangeProperty(dpy, wmcheckwin, netatom[NetWMName], utf8string, 8,
		PropModeReplace, (unsigned char *) "mwm", 3);
	XChangeProperty(dpy, root, netatom[NetWMCheck], XA_WINDOW, 32,
		PropModeReplace, (unsigned char *) &wmcheckwin, 1);
	/* EWMH support per view */
	XChangeProperty(dpy, root, netatom[NetSupported], XA_ATOM, 32,
		PropModeReplace, (unsigned char *) netatom, NetLast);
	XDeleteProperty(dpy, root, netatom[NetClientList]);
	/* select events */
	wa.cursor = cursor[CurNormal]->cursor;
	wa.event_mask = SubstructureRedirectMask|SubstructureNotifyMask
		|ButtonPressMask|PointerMotionMask|EnterWindowMask
		|LeaveWindowMask|StructureNotifyMask|PropertyChangeMask;
	XChangeWindowAttributes(dpy, root, CWEventMask|CWCursor, &wa);
	XSelectInput(dpy, root, wa.event_mask);
	grabkeys();
	focus(NULL);
}

void
seturgent(Client *c, int urg)
{
	XWMHints *wmh;

	c->isurgent = urg;
	if (!(wmh = XGetWMHints(dpy, c->win)))
		return;
	wmh->flags = urg ? (wmh->flags | XUrgencyHint) : (wmh->flags & ~XUrgencyHint);
	XSetWMHints(dpy, c->win, wmh);
	XFree(wmh);
}

static int
noslide(void)
{ /* ~/.config/rice/noslide exists: tag switches snap instead of sliding (the slide stutters on big windows) */
	static char path[512];
	if (!path[0])
		snprintf(path, sizeof path, "%s/.config/rice/noslide", getenv("HOME") ? getenv("HOME") : "");
	return access(path, F_OK) == 0;
}

void
showhide(Client *c)
{
	if (!c)
		return;
	if (ISVISIBLE(c)) {
		if (c->parked) { /* coming back from a hidden tag: slide in when switching */
			c->parked = 0;
			c->placed = 1;
			c->ax = c->x + (!companim && swipedir && !c->isfullscreen && c->mon == swipemon ? swipedir * c->mon->ww : 0);
			c->ay = c->y; c->aw = c->w; c->ah = c->h;
			applygeom(c); /* companim: picom slides it in from where it was parked */
			if (!companim && swipedir && !c->isfullscreen && c->mon == swipemon) {
				c->fx = c->ax; c->fy = c->ay; c->fw = c->aw; c->fh = c->ah;
				c->tx = c->x; c->ty = c->y; c->tw = c->w; c->th = c->h;
				c->t0 = nowsec();
				c->anim = 1;
				baranim = 1;
			} else
				c->ax = c->x;
		}
		if (c->park) { /* was still sliding out: turn it around, resize() may see no change */
			c->park = 0;
			c->fx = c->ax; c->fy = c->ay; c->fw = c->aw; c->fh = c->ah;
			c->tx = c->x; c->ty = c->y; c->tw = c->w; c->th = c->h;
			c->t0 = nowsec();
			c->anim = 1;
			baranim = 1;
		}
		if ((!c->mon->lt[c->mon->sellt]->arrange || c->isfloating) && !c->isfullscreen)
			resize(c, c->x, c->y, c->w, c->h, 0);
		showhide(c->snext);
	} else {
		showhide(c->snext);
		if (c->parked || c->park)
			return;
		if (companim) { /* park one monitor width to the side; picom animates the move */
			c->ax = c->x - (swipedir && c->mon == swipemon ? swipedir * c->mon->mw : 2 * (c->x + WIDTH(c)));
			c->ay = c->y; c->aw = c->w; c->ah = c->h;
			applygeom(c);
			c->parked = 1; c->anim = 0;
		} else if (swipedir && !c->isfullscreen && c->mon == swipemon && c->placed) { /* slide out */
			c->fx = c->ax; c->fy = c->ay; c->fw = c->aw; c->fh = c->ah;
			c->tx = c->ax - swipedir * c->mon->ww; c->ty = c->ay; c->tw = c->aw; c->th = c->ah;
			c->t0 = nowsec();
			c->anim = 1; c->park = 1;
			baranim = 1;
		} else {
			XMoveWindow(dpy, c->win, WIDTH(c) * -2, c->y);
			c->parked = 1; c->anim = 0;
		}
	}
}

void
spawn(const Arg *arg)
{
	syncptrmon();
	struct sigaction sa;

	if (arg->v == dmenucmd)
		dmenumon[0] = '0' + selmon->num;
	if (fork() == 0) {
		if (dpy)
			close(ConnectionNumber(dpy));
		setsid();

		sigemptyset(&sa.sa_mask);
		sa.sa_flags = 0;
		sa.sa_handler = SIG_DFL;
		sigaction(SIGCHLD, &sa, NULL);

		execvp(((char **)arg->v)[0], (char **)arg->v);
		die("dwm: execvp '%s' failed:", ((char **)arg->v)[0]);
	}
}

void
tag(const Arg *arg)
{
	if (selmon->sel && arg->ui & TAGMASK) {
		selmon->sel->tags = arg->ui & TAGMASK;
		focus(NULL);
		arrange(selmon);
	}
}

void
tagmon(const Arg *arg)
{
	if (!selmon->sel || !mons->next)
		return;
	sendmon(selmon->sel, dirtomon(arg->i));
}

void
tile(Monitor *m)
{
	unsigned int i, n, h, mw, my, ty, g = gp(m);
	Client *c;

	for (n = 0, c = nexttiled(m->clients); c; c = nexttiled(c->next), n++);
	if (n == 0)
		return;

	if (n > m->nmaster)
		mw = m->nmaster ? (m->ww - 2 * g - g) * m->mfact : 0;
	else
		mw = m->ww - 2 * g;
	for (i = my = ty = 0, c = nexttiled(m->clients); c; c = nexttiled(c->next), i++)
		if (i < m->nmaster) {
			h = (m->wh - 2 * g - my) / (MIN(n, m->nmaster) - i) - (i + 1 < MIN(n, m->nmaster) ? g : 0);
			resize(c, m->wx + g, m->wy + g + my, mw - (2*c->bw), h - (2*c->bw), 0);
			if (my + HEIGHT(c) + g < m->wh - 2 * g)
				my += HEIGHT(c) + g;
		} else {
			h = (m->wh - 2 * g - ty) / (n - i) - (i + 1 < n ? g : 0);
			resize(c, m->wx + g + mw + g, m->wy + g + ty, m->ww - mw - 3 * g - (2*c->bw), h - (2*c->bw), 0);
			if (ty + HEIGHT(c) + g < m->wh - 2 * g)
				ty += HEIGHT(c) + g;
		}
}



/* "[]= tile  default": symbol, layout name, and a marker when it is the default layout */
const char *
layoutlabel(Monitor *m)
{
	static char buf[64];
	long idx = m->lt[m->sellt] - layouts;
	const char *name = (idx >= 0 && idx < (long)LENGTH(layoutnames)) ? layoutnames[idx] : "";

	static char cname[24];

	if (m->canvas) {
		name = "canvas";
		if (m->cz != 1) {
			snprintf(cname, sizeof cname, "canvas %d%%", (int)(m->cz * 100 + 0.5f));
			name = cname;
		}
	}
	snprintf(buf, sizeof buf, "%s %s%s", m->ltsymbol, name, (!m->canvas && idx == 0) ? "  default" : "");
	return buf;
}

void
resetlayout(const Arg *arg)
{
	Arg a = {.v = &layouts[0]};

	if (selmon->canvas)
		togglecanvas(NULL);
	setlayout(&a);
}

/* ---- runtime keybinds: ~/.config/rice/binds.conf replaces the compiled key table ---- */
typedef struct { const char *name; void (*fn)(const Arg *); char t; } Action;

static const Action actions[] = {
	{ "spawn", spawn, 's' }, { "view", view, 'u' }, { "toggleview", toggleview, 'u' }, { "tag", tag, 'u' },
	{ "toggletag", toggletag, 'u' }, { "killclient", killclient, 'n' }, { "focusstack", focusstack, 'i' },
	{ "zoom", zoom, 'n' }, { "setlayout", setlayout, 'l' }, { "cyclelayout", cyclelayout, 'i' },
	{ "resetlayout", resetlayout, 'n' }, { "togglefloating", togglefloating, 'n' }, { "togglebar", togglebar, 'n' },
	{ "setgaps", setgaps, 'i' }, { "focusmon", focusmon, 'i' }, { "tagmon", tagmon, 'i' }, { "snapwin", snapwin, 'i' },
	{ "movewin", movewin, 'i' }, { "sizewin", sizewin, 'i' }, { "togglecanvas", togglecanvas, 'n' }, { "canvaszoomreset", canvaszoomreset, 'n' },
	{ "quit", quit, 'i' }, { "xrdb", xrdb, 'n' }, { "incnmaster", incnmaster, 'i' }, { "setmfact", setmfact, 'f' },
	{ "movestack", movestack, 'i' },
};

static const struct { const char *n; unsigned int m; } modnames[] = {
	{ "Mod", Mod1Mask }, { "Alt", Mod1Mask }, { "Shift", ShiftMask }, { "Ctrl", ControlMask }, { "Super", Mod4Mask },
};

static const Action *
findaction(void (*fn)(const Arg *))
{
	unsigned int i;
	for (i = 0; i < LENGTH(actions); i++)
		if (actions[i].fn == fn)
			return &actions[i];
	return NULL;
}

void
loadkeys(void)
{
	char path[512], line[1024], *p, *eq, *tok, *save, *rest, *word;
	FILE *f;
	const char *home = getenv("HOME");
	unsigned int i, cap = 0;
	DKey k;

	ncur = 0;
	free(curkeys);
	curkeys = NULL;
	snprintf(path, sizeof path, "%s/.config/rice/binds.conf", home ? home : "");
	f = fopen(path, "r");
	if (!f) { /* no override file: the compiled table */
		curkeys = ecalloc(LENGTH(keys), sizeof(DKey));
		for (i = 0; i < LENGTH(keys); i++) {
			curkeys[i].mod = keys[i].mod; curkeys[i].keysym = keys[i].keysym;
			curkeys[i].func = keys[i].func; curkeys[i].arg = keys[i].arg;
		}
		ncur = LENGTH(keys);
		return;
	}
	while (fgets(line, sizeof line, f)) {
		if ((p = strchr(line, '#')))
			*p = 0;
		if ((p = strchr(line, '\n')))
			*p = 0;
		if (!(eq = strchr(line, '=')))
			continue;
		*eq = 0;
		rest = eq + 1;
		memset(&k, 0, sizeof k);
		/* combo: Mod+Shift+t */
		p = line;
		while (*p == ' ' || *p == '\t') p++;
		{
			char *e = p + strlen(p);
			while (e > p && (e[-1] == ' ' || e[-1] == '\t')) *--e = 0;
		}
		for (tok = strtok_r(p, "+", &save); tok; tok = strtok_r(NULL, "+", &save)) {
			char *peek = save && *save ? save : NULL;
			int ismod = 0;
			if (peek)
				for (i = 0; i < LENGTH(modnames); i++)
					if (!strcmp(tok, modnames[i].n)) { k.mod |= modnames[i].m; ismod = 1; }
			if (!peek && !ismod)
				k.keysym = XStringToKeysym(tok);
		}
		if (!k.keysym)
			continue;
		while (*rest == ' ' || *rest == '\t') rest++;
		word = rest;
		while (*rest && *rest != ' ' && *rest != '\t') rest++;
		if (*rest) *rest++ = 0;
		while (*rest == ' ' || *rest == '\t') rest++;
		for (i = 0; i < LENGTH(actions) && strcmp(actions[i].name, word); i++);
		if (i >= LENGTH(actions))
			continue;
		k.func = actions[i].fn;
		switch (actions[i].t) {
		case 's': {
			const char **argv = ecalloc(4, sizeof(char *));
			argv[0] = "/bin/sh"; argv[1] = "-c"; argv[2] = strdup(rest);
			k.arg.v = argv;
			break;
		}
		case 'u':
			if (!strcmp(rest, "all")) k.arg.ui = ~0;
			else if (!strcmp(rest, "prev") || !*rest) k.arg.ui = 0;
			else k.arg.ui = 1u << (atoi(rest) - 1);
			break;
		case 'i': k.arg.i = atoi(rest); break;
		case 'f': k.arg.f = (float)atof(rest); break;
		case 'l':
			if (*rest && strcmp(rest, "toggle") && (unsigned)atoi(rest) < LENGTH(layouts))
				k.arg.v = &layouts[atoi(rest)];
			break;
		}
		if (ncur == cap) {
			cap = cap ? cap * 2 : 64;
			curkeys = realloc(curkeys, cap * sizeof(DKey));
			if (!curkeys) die("realloc failed");
		}
		curkeys[ncur++] = k;
	}
	fclose(f);
}

/* dwm --dump-binds: the compiled table in binds.conf format (the settings app seeds the file from this) */
void
dumpkeys(void)
{
	unsigned int i, j;
	const Action *a;
	char mods[64];

	printf("# dwm keybinds: <Mod+Shift+key> = <action> [argument]   (Mod = Alt)\n");
	for (i = 0; i < LENGTH(keys); i++) {
		if (!(a = findaction(keys[i].func)) || !keys[i].keysym)
			continue;
		mods[0] = 0;
		for (j = 0; j < LENGTH(modnames); j++)
			if (j != 1 && (keys[i].mod & modnames[j].m))
				snprintf(mods + strlen(mods), sizeof mods - strlen(mods), "%s+", modnames[j].n);
		printf("%s%s = %s", mods, XKeysymToString(keys[i].keysym), a->name);
		switch (a->t) {
		case 's': {
			const char **v = (const char **)keys[i].arg.v;
			if (v && v[0] && v[1] && !strcmp(v[1], "-c") && v[2])
				printf(" %s", v[2]);
			else
				for (j = 0; v && v[j]; j++)
					printf(" %s", v[j]);
			break;
		}
		case 'u':
			if (keys[i].arg.ui == ~0u) printf(" all");
			else if (keys[i].arg.ui == 0) printf(" prev");
			else for (j = 0; j < 32; j++) if (keys[i].arg.ui == 1u << j) { printf(" %u", j + 1); break; }
			break;
		case 'i': printf(" %d", keys[i].arg.i); break;
		case 'f': printf(" %g", keys[i].arg.f); break;
		case 'l':
			if (keys[i].arg.v)
				printf(" %ld", (const Layout *)keys[i].arg.v - layouts);
			break;
		}
		printf("\n");
	}
}

/* ---- rice layouts ---- */
#define PLACE(c, x, y, w, h) resize(c, (x), (y), (w) - 2 * (c)->bw, (h) - 2 * (c)->bw, 0)

static unsigned int
tiledcount(Monitor *m, Client ***list)
{
	unsigned int n = 0;
	Client *c, **l;

	for (c = nexttiled(m->clients); c; c = nexttiled(c->next))
		n++;
	if (!n) { *list = NULL; return 0; }
	l = ecalloc(n, sizeof(Client *));
	for (n = 0, c = nexttiled(m->clients); c; c = nexttiled(c->next))
		l[n++] = c;
	*list = l;
	return n;
}

/* cnt clients stacked top to bottom / left to right inside the box */
static void
vbox(Client **cs, int cnt, int x, int y, int w, int h, int g)
{
	int i, hh, yy = y;

	for (i = 0; i < cnt; i++) {
		hh = (h - yy + y) / (cnt - i) - (i + 1 < cnt ? g : 0);
		PLACE(cs[i], x, yy, w, hh);
		yy += hh + g;
	}
}

/* bento: a hero window on the left, the rest in an uneven grid on the right.
 *   right area = one big tile on top, below it two columns (58/42) of stacked tiles */
void
bento(Monitor *m)
{
	Client **cs;
	unsigned int n = tiledcount(m, &cs), g = gp(m), r, lc;
	int x = m->wx + g, y = m->wy + g, w = m->ww - 2 * g, h = m->wh - 2 * g;
	int hw, rx, rw, th, by, bh, lw;

	if (!n) return;
	if (n == 1) {
		PLACE(cs[0], x, y, w, h);
		free(cs);
		return;
	}
	hw = (w - g) * m->mfact;
	PLACE(cs[0], x, y, hw, h);
	rx = x + hw + g; rw = w - hw - g;
	if (n == 2) {
		PLACE(cs[1], rx, y, rw, h);
	} else {
		th = (h - g) * 0.52;
		PLACE(cs[1], rx, y, rw, th);
		by = y + th + g; bh = h - th - g;
		r = n - 2;
		if (r == 1) {
			PLACE(cs[2], rx, by, rw, bh);
		} else {
			lc = (r + 1) / 2;
			lw = (rw - g) * 0.58;
			vbox(cs + 2, lc, rx, by, lw, bh, g);
			vbox(cs + 2 + lc, r - lc, rx + lw + g, by, rw - lw - g, bh, g);
		}
	}
	free(cs);
}

/* dock: narrow sidebar window on the left, main window in the middle, the rest stacked as a
 * widget column on the right. Window order: 1st = main, 2nd = sidebar, others = right column. */
void
dock(Monitor *m)
{
	Client **cs;
	unsigned int n = tiledcount(m, &cs), g = gp(m);
	int x = m->wx + g, y = m->wy + g, w = m->ww - 2 * g, h = m->wh - 2 * g;
	int free_ = (w - 2 * g) * (1.0f - m->mfact), lw, rw, mw;

	if (!n) return;
	if (n == 1) {
		PLACE(cs[0], x, y, w, h);
		free(cs);
		return;
	}
	if (n == 2) {
		lw = (w - g) * (1.0f - m->mfact) * 0.55f;
		PLACE(cs[1], x, y, lw, h);
		PLACE(cs[0], x + lw + g, y, w - lw - g, h);
		free(cs);
		return;
	}
	lw = free_ * 0.4f; rw = free_ - lw; mw = w - 2 * g - lw - rw;
	PLACE(cs[1], x, y, lw, h);
	PLACE(cs[0], x + lw + g, y, mw, h);
	vbox(cs + 2, n - 2, x + lw + g + mw + g, y, rw, h, g);
	free(cs);
}

/* mosaic: staggered rows, every row split unevenly and the split flips on the next row
 * (brick pattern), row heights alternate slightly. */
void
mosaic(Monitor *m)
{
	Client **cs;
	unsigned int n = tiledcount(m, &cs), g = gp(m), rows, i, r, k, per, extra, idx = 0;
	int x = m->wx + g, y = m->wy + g, w = m->ww - 2 * g, h = m->wh - 2 * g;
	float hs = 0, ws;

	if (!n) return;
	rows = n <= 2 ? 1 : n <= 6 ? 2 : 3;
	if (rows > n) rows = n;
	for (r = 0; r < rows; r++)
		hs += (r % 2) ? 0.85f : 1.15f;
	per = n / rows; extra = n % rows;
	for (r = 0; r < rows; r++) {
		int rh = (int)((h - (int)(rows - 1) * (int)g) * ((r % 2) ? 0.85f : 1.15f) / hs);
		int xx = x;
		k = per + (r < extra ? 1 : 0);
		ws = 0;
		for (i = 0; i < k; i++)
			ws += 1.0f + 0.7f * ((r + i) % 2);
		for (i = 0; i < k; i++) {
			int cw = (int)((w - (int)(k - 1) * (int)g) * (1.0f + 0.7f * ((r + i) % 2)) / ws);
			if (i == k - 1)
				cw = x + w - xx;
			{ Client *cc = cs[idx++]; PLACE(cc, xx, y, cw, rh); }
			xx += cw + g;
		}
		y += rh + g;
	}
	free(cs);
}


/* next / previous layout in config.h */
void
cyclelayout(const Arg *arg)
{
	int i, n = (int)LENGTH(layouts), cur = 0;
	Arg a;

	if (selmon->canvas) {      /* first press leaves canvas mode (back to the layout it came from) */
		togglecanvas(NULL);
		return;
	}

	for (i = 0; i < n; i++)
		if (&layouts[i] == selmon->lt[selmon->sellt])
			cur = i;
	cur = (cur + (arg->i >= 0 ? 1 : n - 1)) % n;
	a.v = &layouts[cur];
	setlayout(&a);
}

/* swap the focused tiled window with the next / previous one in the stack order */
void
movestack(const Arg *arg)
{
	Client *c = NULL, *p = NULL, *pc = NULL, *i;

	if (!selmon->sel || selmon->sel->isfloating)
		return;
	if (arg->i > 0) {
		for (c = selmon->sel->next; c && (!ISVISIBLE(c) || c->isfloating); c = c->next);
		if (!c)
			for (c = selmon->clients; c && (!ISVISIBLE(c) || c->isfloating); c = c->next);
	} else {
		for (i = selmon->clients; i != selmon->sel; i = i->next)
			if (ISVISIBLE(i) && !i->isfloating)
				c = i;
		if (!c)
			for (; i; i = i->next)
				if (ISVISIBLE(i) && !i->isfloating)
					c = i;
	}
	for (i = selmon->clients; i && (!p || !pc); i = i->next) {
		if (i->next == selmon->sel)
			p = i;
		if (i->next == c)
			pc = i;
	}
	if (c && c != selmon->sel) {
		Client *temp = selmon->sel->next == c ? selmon->sel : selmon->sel->next;
		selmon->sel->next = c->next == selmon->sel ? c : c->next;
		c->next = temp;
		if (p && p != c)
			p->next = c;
		if (pc && pc != selmon->sel)
			pc->next = selmon->sel;
		if (selmon->sel == selmon->clients)
			selmon->clients = c;
		else if (c == selmon->clients)
			selmon->clients = selmon->sel;
		arrange(selmon);
	}
}

void
togglebar(const Arg *arg)
{
	selmon->showbar = !selmon->showbar;
	updatebarpos(selmon);
	resizebarwin(selmon);
	if (showsystray) {
		XWindowChanges wc;
		if (!selmon->showbar)
			wc.y = -bh;
		else if (selmon->showbar) {
			wc.y = 0;
			if (!selmon->topbar)
				wc.y = selmon->mh - bh;
		}
		XConfigureWindow(dpy, systray->win, CWY, &wc);
	}
	arrange(selmon);
}

void
togglefloating(const Arg *arg)
{
	if (!selmon->sel)
		return;
	if (selmon->sel->isfullscreen) /* no support for fullscreen windows */
		return;
	selmon->sel->isfloating = !selmon->sel->isfloating || selmon->sel->isfixed;
	if (selmon->sel->isfloating)
		resize(selmon->sel, selmon->sel->x, selmon->sel->y,
			selmon->sel->w, selmon->sel->h, 0);
	arrange(selmon);
}

void
toggletag(const Arg *arg)
{
	unsigned int newtags;

	if (!selmon->sel)
		return;
	newtags = selmon->sel->tags ^ (arg->ui & TAGMASK);
	if (newtags) {
		selmon->sel->tags = newtags;
		focus(NULL);
		arrange(selmon);
	}
}

void
toggleview(const Arg *arg)
{
	unsigned int newtagset = selmon->tagset[selmon->seltags] ^ (arg->ui & TAGMASK);

	if (newtagset) {
		selmon->tagset[selmon->seltags] = newtagset;
		focus(NULL);
		arrange(selmon);
	}
}

void
unfocus(Client *c, int setfocus)
{
	if (!c)
		return;
	grabbuttons(c, 0);
	c->bt = 0;
	if (noanim || c->bm <= 0 || !c->hasb) {
		XSetWindowBorder(dpy, c->win, scheme[SchemeNorm][ColBorder].pixel);
		c->hasb = 0; c->bm = 0;
		reborder(c);
	} else
		baranim = 1;   /* animstep fades the outline out, then drops the border */
	if (setfocus) {
		XSetInputFocus(dpy, root, RevertToPointerRoot, CurrentTime);
		XDeleteProperty(dpy, root, netatom[NetActiveWindow]);
	}
}

void
unmanage(Client *c, int destroyed)
{
	Monitor *m = c->mon;
	XWindowChanges wc;

	detach(c);
	detachstack(c);
	if (!destroyed) {
		wc.border_width = c->oldbw;
		XGrabServer(dpy); /* avoid race conditions */
		XSetErrorHandler(xerrordummy);
		XSelectInput(dpy, c->win, NoEventMask);
		XConfigureWindow(dpy, c->win, CWBorderWidth, &wc); /* restore border */
		XUngrabButton(dpy, AnyButton, AnyModifier, c->win);
		setclientstate(c, WithdrawnState);
		XSync(dpy, False);
		XSetErrorHandler(xerror);
		XUngrabServer(dpy);
	}
	free(c);
	focus(NULL);
	updateclientlist();
	arrange(m);
}

void
unmapnotify(XEvent *e)
{
	Client *c;
	XUnmapEvent *ev = &e->xunmap;

	if ((c = wintoclient(ev->window))) {
		if (ev->send_event)
			setclientstate(c, WithdrawnState);
		else
			unmanage(c, 0);
	}
	else if (shellfocus && ev->window == shellfocus) {
		shellfocus = 0;
		focus(NULL);
	}
	else if ((c = wintosystrayicon(ev->window))) {
		/* KLUDGE! sometimes icons occasionally unmap their windows, but do
		 * _not_ destroy them. We map those windows back */
		XMapRaised(dpy, c->win);
		updatesystray();
	}
}

void
updatebars(void)
{
	unsigned int w;
	Monitor *m;
	XSetWindowAttributes wa = {
		.override_redirect = True,
		.background_pixmap = ParentRelative,
		.event_mask = ButtonPressMask|ExposureMask
	};
	XClassHint ch = {"dwm", "dwm"};
	for (m = mons; m; m = m->next) {
		if (m->barwin)
			continue;
		w = m->ww - 2 * spa(m);
		m->barwin = XCreateWindow(dpy, root, m->wx + spa(m), m->by, w, bh, 0, DefaultDepth(dpy, screen),
				CopyFromParent, DefaultVisual(dpy, screen),
				CWOverrideRedirect|CWBackPixmap|CWEventMask, &wa);
		XDefineCursor(dpy, m->barwin, cursor[CurNormal]->cursor);
		if (showsystray && m == systraytomon(m))
			XMapRaised(dpy, systray->win);
		XMapRaised(dpy, m->barwin);
		XSetClassHint(dpy, m->barwin, &ch);
	}
}

void
updatebarpos(Monitor *m)
{
	m->wy = m->my;
	m->wh = m->mh;
	if (m->showbar) {
		m->wh -= bh + vp(m);
		m->by = m->topbar ? m->wy + vpa(m) : m->wy + m->wh;
		m->wy = m->topbar ? m->wy + bh + vp(m) : m->wy;
	} else
		m->by = -bh;
}

void
updateclientlist(void)
{
	Client *c;
	Monitor *m;

	XDeleteProperty(dpy, root, netatom[NetClientList]);
	for (m = mons; m; m = m->next)
		for (c = m->clients; c; c = c->next)
			XChangeProperty(dpy, root, netatom[NetClientList],
				XA_WINDOW, 32, PropModeAppend,
				(unsigned char *) &(c->win), 1);
}

int
updategeom(void)
{
	int dirty = 0;

#ifdef XINERAMA
	if (XineramaIsActive(dpy)) {
		int i, j, n, nn;
		Client *c;
		Monitor *m;
		XineramaScreenInfo *info = XineramaQueryScreens(dpy, &nn);
		XineramaScreenInfo *unique = NULL;

		for (n = 0, m = mons; m; m = m->next, n++);
		/* only consider unique geometries as separate screens */
		unique = ecalloc(nn, sizeof(XineramaScreenInfo));
		for (i = 0, j = 0; i < nn; i++)
			if (isuniquegeom(unique, j, &info[i]))
				memcpy(&unique[j++], &info[i], sizeof(XineramaScreenInfo));
		XFree(info);
		nn = j;

		/* new monitors if nn > n */
		for (i = n; i < nn; i++) {
			for (m = mons; m && m->next; m = m->next);
			if (m)
				m->next = createmon();
			else
				mons = createmon();
		}
		for (i = 0, m = mons; i < nn && m; m = m->next, i++)
			if (i >= n
			|| unique[i].x_org != m->mx || unique[i].y_org != m->my
			|| unique[i].width != m->mw || unique[i].height != m->mh)
			{
				dirty = 1;
				m->num = i;
				m->mx = m->wx = unique[i].x_org;
				m->my = m->wy = unique[i].y_org;
				m->mw = m->ww = unique[i].width;
				m->mh = m->wh = unique[i].height;
				updatebarpos(m);
			}
		/* removed monitors if n > nn */
		for (i = nn; i < n; i++) {
			for (m = mons; m && m->next; m = m->next);
			while ((c = m->clients)) {
				dirty = 1;
				m->clients = c->next;
				detachstack(c);
				c->mon = mons;
				attach(c);
				attachstack(c);
			}
			if (m == selmon)
				selmon = mons;
			cleanupmon(m);
		}
		free(unique);
	} else
#endif /* XINERAMA */
	{ /* default monitor setup */
		if (!mons)
			mons = createmon();
		if (mons->mw != sw || mons->mh != sh) {
			dirty = 1;
			mons->mw = mons->ww = sw;
			mons->mh = mons->wh = sh;
			updatebarpos(mons);
		}
	}
	if (dirty) {
		selmon = mons;
		selmon = wintomon(root);
	}
	return dirty;
}

void
updatenumlockmask(void)
{
	unsigned int i, j;
	XModifierKeymap *modmap;

	numlockmask = 0;
	modmap = XGetModifierMapping(dpy);
	for (i = 0; i < 8; i++)
		for (j = 0; j < modmap->max_keypermod; j++)
			if (modmap->modifiermap[i * modmap->max_keypermod + j]
				== XKeysymToKeycode(dpy, XK_Num_Lock))
				numlockmask = (1 << i);
	XFreeModifiermap(modmap);
}

void
updatesizehints(Client *c)
{
	long msize;
	XSizeHints size;

	if (!XGetWMNormalHints(dpy, c->win, &size, &msize))
		/* size is uninitialized, ensure that size.flags aren't used */
		size.flags = PSize;
	if (size.flags & PBaseSize) {
		c->basew = size.base_width;
		c->baseh = size.base_height;
	} else if (size.flags & PMinSize) {
		c->basew = size.min_width;
		c->baseh = size.min_height;
	} else
		c->basew = c->baseh = 0;
	if (size.flags & PResizeInc) {
		c->incw = size.width_inc;
		c->inch = size.height_inc;
	} else
		c->incw = c->inch = 0;
	if (size.flags & PMaxSize) {
		c->maxw = size.max_width;
		c->maxh = size.max_height;
	} else
		c->maxw = c->maxh = 0;
	if (size.flags & PMinSize) {
		c->minw = size.min_width;
		c->minh = size.min_height;
	} else if (size.flags & PBaseSize) {
		c->minw = size.base_width;
		c->minh = size.base_height;
	} else
		c->minw = c->minh = 0;
	if (size.flags & PAspect) {
		c->mina = (float)size.min_aspect.y / size.min_aspect.x;
		c->maxa = (float)size.max_aspect.x / size.max_aspect.y;
	} else
		c->maxa = c->mina = 0.0;
	c->isfixed = (c->maxw && c->maxh && c->maxw == c->minw && c->maxh == c->minh);
	c->hintsvalid = 1;
}

void
updatestatus(void)
{
	if (!gettextprop(root, XA_WM_NAME, stext, sizeof(stext)))
		strcpy(stext, "mwm-"VERSION);
	drawbars();
	updatesystray();
}


void
updatesystrayicongeom(Client *i, int w, int h)
{
	if (i) {
		i->h = bh;
		if (w == h)
			i->w = bh;
		else if (h == bh)
			i->w = w;
		else
			i->w = (int) ((float)bh * ((float)w / (float)h));
		applysizehints(i, &(i->x), &(i->y), &(i->w), &(i->h), False);
		/* force icons into the systray dimensions if they don't want to */
		if (i->h > bh) {
			if (i->w == i->h)
				i->w = bh;
			else
				i->w = (int) ((float)bh * ((float)i->w / (float)i->h));
			i->h = bh;
		}
	}
}

void
updatesystrayiconstate(Client *i, XPropertyEvent *ev)
{
	long flags;
	int code = 0;

	if (!showsystray || !i || ev->atom != xatom[XembedInfo] ||
			!(flags = getatomprop(i, xatom[XembedInfo])))
		return;

	if (flags & XEMBED_MAPPED && !i->tags) {
		i->tags = 1;
		code = XEMBED_WINDOW_ACTIVATE;
		XMapRaised(dpy, i->win);
		setclientstate(i, NormalState);
	}
	else if (!(flags & XEMBED_MAPPED) && i->tags) {
		i->tags = 0;
		code = XEMBED_WINDOW_DEACTIVATE;
		XUnmapWindow(dpy, i->win);
		setclientstate(i, WithdrawnState);
	}
	else
		return;
	sendevent(i->win, xatom[Xembed], StructureNotifyMask, CurrentTime, code, 0,
			systray->win, XEMBED_EMBEDDED_VERSION);
}

void
updatesystray(void)
{
	XSetWindowAttributes wa;
	XWindowChanges wc;
	Client *i;
	Monitor *m = systraytomon(NULL);
	unsigned int x;
	traymon = m;
	x = m->wx + m->ww - spa(m) - rwidth();
	unsigned int sw = TEXTW(stext) - lrpad + systrayspacing;
	unsigned int w = 1;

	if (!showsystray)
		return;
	if (systrayonleft)
		x -= sw + lrpad / 2;
	if (!systray) {
		/* init systray */
		if (!(systray = (Systray *)calloc(1, sizeof(Systray))))
			die("fatal: could not malloc() %u bytes\n", sizeof(Systray));
		systray->win = XCreateSimpleWindow(dpy, root, x, m->by, w, bh, 0, 0, scheme[SchemeSel][ColBg].pixel);
		wa.event_mask        = ButtonPressMask | ExposureMask;
		wa.override_redirect = True;
		wa.background_pixel  = scheme[SchemeNorm][ColBg].pixel;
		XSelectInput(dpy, systray->win, SubstructureNotifyMask);
		XChangeProperty(dpy, systray->win, netatom[NetSystemTrayOrientation], XA_CARDINAL, 32,
				PropModeReplace, (unsigned char *)&netatom[NetSystemTrayOrientationHorz], 1);
		XChangeWindowAttributes(dpy, systray->win, CWEventMask|CWOverrideRedirect|CWBackPixel, &wa);
		{ XClassHint ch = { "dwmtray", "dwmtray" }; XSetClassHint(dpy, systray->win, &ch); } /* lets picom skip it */
		XMapRaised(dpy, systray->win);
		XSetSelectionOwner(dpy, netatom[NetSystemTray], systray->win, CurrentTime);
		if (XGetSelectionOwner(dpy, netatom[NetSystemTray]) == systray->win) {
			sendevent(root, xatom[Manager], StructureNotifyMask, CurrentTime, netatom[NetSystemTray], systray->win, 0, 0);
			XSync(dpy, False);
		}
		else {
			fprintf(stderr, "dwm: unable to obtain system tray.\n");
			free(systray);
			systray = NULL;
			return;
		}
	}
	for (w = 0, i = systray->icons; i; i = i->next) {
		/* make sure the background color stays the same */
		wa.background_pixel  = scheme[SchemeNorm][ColBg].pixel;
		XChangeWindowAttributes(dpy, i->win, CWBackPixel, &wa);
		XMapRaised(dpy, i->win);
		w += systrayspacing;
		i->x = w;
		XMoveResizeWindow(dpy, i->win, i->x, 0, i->w, i->h);
		w += i->w;
		if (i->mon != m)
			i->mon = m;
	}
	w = w ? w + systrayspacing : 1;
	x -= w;
	XMoveResizeWindow(dpy, systray->win, x, m->by, w, bh);
	wc.x = x; wc.y = m->by; wc.width = w; wc.height = bh;
	wc.stack_mode = Above; wc.sibling = m->barwin;
	XConfigureWindow(dpy, systray->win, CWX|CWY|CWWidth|CWHeight|CWSibling|CWStackMode, &wc);
	XMapWindow(dpy, systray->win);
	XMapSubwindows(dpy, systray->win);
	/* redraw background */
	XSetForeground(dpy, drw->gc, scheme[SchemeNorm][ColBg].pixel);
	XFillRectangle(dpy, systray->win, drw->gc, 0, 0, w, bh);
	XSync(dpy, False);
}

void
updatetitle(Client *c)
{
	if (!gettextprop(c->win, netatom[NetWMName], c->name, sizeof c->name))
		gettextprop(c->win, XA_WM_NAME, c->name, sizeof c->name);
	if (c->name[0] == '\0') /* hack to mark broken clients */
		strcpy(c->name, broken);
}

void
updatewindowtype(Client *c)
{
	Atom state = getatomprop(c, netatom[NetWMState]);
	Atom wtype = getatomprop(c, netatom[NetWMWindowType]);

	if (state == netatom[NetWMFullscreen])
		setfullscreen(c, 1);
	if (wtype == netatom[NetWMWindowTypeDialog])
		c->isfloating = 1;
}

void
updatewmhints(Client *c)
{
	XWMHints *wmh;

	if ((wmh = XGetWMHints(dpy, c->win))) {
		if (c == selmon->sel && wmh->flags & XUrgencyHint) {
			wmh->flags &= ~XUrgencyHint;
			XSetWMHints(dpy, c->win, wmh);
		} else
			c->isurgent = (wmh->flags & XUrgencyHint) ? 1 : 0;
		if (wmh->flags & InputHint)
			c->neverfocus = !wmh->input;
		else
			c->neverfocus = 0;
		XFree(wmh);
	}
}

void
view(const Arg *arg)
{
	if ((arg->ui & TAGMASK) == selmon->tagset[selmon->seltags])
		return;
	int oldi = ffs(selmon->tagset[selmon->seltags]), newi;
	selmon->seltags ^= 1; /* toggle sel tagset */
	if (arg->ui & TAGMASK)
		selmon->tagset[selmon->seltags] = arg->ui & TAGMASK;
	newi = ffs(selmon->tagset[selmon->seltags]);
	swipedir = newi > oldi ? 1 : newi < oldi ? -1 : 0;
	if (noslide())
		swipedir = 0;
	swipemon = selmon;
	focus(NULL);
	arrange(selmon);
	swipedir = 0;
}

Client *
wintoclient(Window w)
{
	Client *c;
	Monitor *m;

	for (m = mons; m; m = m->next)
		for (c = m->clients; c; c = c->next)
			if (c->win == w)
				return c;
	return NULL;
}

Client *
wintosystrayicon(Window w) {
	Client *i = NULL;

	if (!showsystray || !w)
		return i;
	for (i = systray->icons; i && i->win != w; i = i->next) ;
	return i;
}

Monitor *
wintomon(Window w)
{
	int x, y;
	Client *c;
	Monitor *m;

	if (w == root && getrootptr(&x, &y))
		return recttomon(x, y, 1, 1);
	for (m = mons; m; m = m->next)
		if (w == m->barwin)
			return m;
	if ((c = wintoclient(w)))
		return c->mon;
	return selmon;
}

/* There's no way to check accesses to destroyed windows, thus those cases are
 * ignored (especially on UnmapNotify's). Other types of errors call Xlibs
 * default error handler, which may call exit. */
int
xerror(Display *dpy, XErrorEvent *ee)
{
	if (ee->error_code == BadWindow
	|| (ee->request_code == X_SetInputFocus && ee->error_code == BadMatch)
	|| (ee->request_code == X_PolyText8 && ee->error_code == BadDrawable)
	|| (ee->request_code == X_PolyFillRectangle && ee->error_code == BadDrawable)
	|| (ee->request_code == X_PolySegment && ee->error_code == BadDrawable)
	|| (ee->request_code == X_ConfigureWindow && ee->error_code == BadMatch)
	|| (ee->request_code == X_GrabButton && ee->error_code == BadAccess)
	|| (ee->request_code == X_GrabKey && ee->error_code == BadAccess)
	|| (ee->request_code == X_CopyArea && ee->error_code == BadDrawable))
		return 0;
	fprintf(stderr, "dwm: fatal error: request code=%d, error code=%d\n",
		ee->request_code, ee->error_code);
	return xerrorxlib(dpy, ee); /* may call exit */
}

int
xerrordummy(Display *dpy, XErrorEvent *ee)
{
	return 0;
}

/* Startup Error handler to check if another window manager
 * is already running. */
int
xerrorstart(Display *dpy, XErrorEvent *ee)
{
	die("mwm: another window manager is already running");
	return -1;
}

void
xrdb(const Arg *arg)
{
  loadxrdb();
  int i;
  for (i = 0; i < LENGTH(colors); i++)
                scheme[i] = drw_scm_create(drw, colors[i], 3);
  focus(NULL);
  arrange(NULL);
}

Monitor *
systraytomon(Monitor *m) {
	Monitor *t;
	int i, n;
	if (traytemp)
		return traytemp;
	if(!systraypinning) {
		if(!m)
			return selmon;
		return m == selmon ? m : NULL;
	}
	for(n = 1, t = mons; t && t->next; n++, t = t->next) ;
	for(i = 1, t = mons; t && t->next && i < systraypinning; i++, t = t->next) ;
	if(systraypinningfailfirst && n < systraypinning)
		return mons;
	return t;
}

void
zoom(const Arg *arg)
{
	Client *c = selmon->sel;

	if (!selmon->lt[selmon->sellt]->arrange || !c || c->isfloating)
		return;
	if (c == nexttiled(selmon->clients) && !(c = nexttiled(c->next)))
		return;
	pop(c);
}

int
main(int argc, char *argv[])
{
	if (argc == 2 && !strcmp("-v", argv[1]))
		die("mwm-"VERSION);
	else if (argc == 2 && !strcmp("--dump-binds", argv[1])) {
		dumpkeys();
		return EXIT_SUCCESS;
	} else if (argc != 1)
		die("usage: dwm [-v | --dump-binds]");
	if (!setlocale(LC_CTYPE, "") || !XSupportsLocale())
		fputs("warning: no locale support\n", stderr);
	if (!(dpy = XOpenDisplay(NULL)))
		die("mwm: cannot open display");
	checkotherwm();
        XrmInitialize();
        loadxrdb();
	setup();
#ifdef __OpenBSD__
	if (pledge("stdio rpath proc exec", NULL) == -1)
		die("pledge");
#endif /* __OpenBSD__ */
	restartargv = argv;
	loadkeys();
	grabkeys();
	signal(SIGHUP, sighup);
	signal(SIGTERM, sigterm);
	scan();
	{ /* restored view after a restart */
		Atom type; int fmt; unsigned long n, after; unsigned char *p = NULL;
		if (XGetWindowProperty(dpy, root, XInternAtom(dpy, "_RICE_VIEW", False), 0, 1, True, XA_CARDINAL, &type, &fmt, &n, &after, &p) == Success && p) {
			if (n == 1 && (*(long *)p & TAGMASK)) {
				Arg va = {.ui = (unsigned int)(*(long *)p & TAGMASK)};
				swipedir = 0;
				view(&va);
			}
			XFree(p);
		}
	}
	run();
	cleanup();
	XCloseDisplay(dpy);
	if (restart)
		execvp(restartargv[0], restartargv);
	return EXIT_SUCCESS;
}

/* ---- rice additions: popups at click, canvas drag mode, keyboard snapping ---- */
void
spawnat(const Arg *arg)
{
	static char xs[16], ys[16];
	const char **argv = (const char **)arg->v, *out[16];
	struct sigaction sa;
	int n = 0;

	snprintf(xs, sizeof xs, "%d", clickx);
	snprintf(ys, sizeof ys, "%d", clicky);
	while (argv[n] && n < 12) { out[n] = argv[n]; n++; }
	out[n++] = "--at"; out[n++] = xs; out[n++] = ys; out[n] = NULL;
	if (fork() == 0) {
		if (dpy)
			close(ConnectionNumber(dpy));
		setsid();
		sigemptyset(&sa.sa_mask);
		sa.sa_flags = 0;
		sa.sa_handler = SIG_DFL;
		sigaction(SIGCHLD, &sa, NULL);
		execvp(out[0], (char *const *)out);
		die("dwm: execvp '%s' failed:", out[0]);
	}
}

/* canvas mode needs a layout with no arrange function: windows then keep the geometry they have.
 * (It used to borrow layouts[1], which is bento since Session 4, so opening a window or any arrange()
 * re-tiled everything and undid panning.) */
static const Layout canvaslayout = { "><>", NULL };

/* ---- canvas zoom: real windows are moved AND resized about the pointer (no compositor scaling exists, so the
 * contents re-layout instead of stretching). Each window keeps a zoom-1 geometry (bx..) so zooming back is exact;
 * a window the user moved or resized in between is re-based from where it is (lx.. differs from x..). ---- */
static void
canvaspan(Monitor *m, int dx, int dy)
{
	Client *c;

	m->cpx += dx; m->cpy += dy;
	for (c = m->clients; c; c = c->next)
		if (ISVISIBLE(c) && !c->isfullscreen) {
			resizeclient(c, c->x + dx, c->y + dy, c->w, c->h);
			if (c->lvalid) { c->lx += dx; c->ly += dy; }
		}
}

static void
canvaszoom(Monitor *m, int cx, int cy, float f)
{
	Client *c;
	float z = m->cz > 0 ? m->cz : 1, nz = z * f;
	int saved = noanim, nx, ny, nw, nh;

	if (!m->canvas)
		return;
	if (nz < 0.25f) nz = 0.25f;
	if (nz > 2.0f) nz = 2.0f;
	if (nz > 0.97f && nz < 1.03f) nz = 1.0f;
	if (nz == z)
		return;
	for (c = m->clients; c; c = c->next)
		if (ISVISIBLE(c) && !c->isfullscreen && (!c->lvalid || c->x != c->lx || c->y != c->ly || c->w != c->lw || c->h != c->lh)) {
			c->bx = (c->x - m->cpx) / z; c->by = (c->y - m->cpy) / z;
			c->bw0 = c->w / z; c->bh0 = c->h / z;
		}
	m->cpx = cx - (cx - m->cpx) * nz / z;
	m->cpy = cy - (cy - m->cpy) * nz / z;
	m->cz = nz;
	noanim = 1;
	for (c = m->clients; c; c = c->next)
		if (ISVISIBLE(c) && !c->isfullscreen) {
			nx = (int)(c->bx * nz + m->cpx + (c->bx * nz + m->cpx < 0 ? -0.5f : 0.5f));
			ny = (int)(c->by * nz + m->cpy + (c->by * nz + m->cpy < 0 ? -0.5f : 0.5f));
			nw = MAX(100, (int)(c->bw0 * nz + 0.5f));
			nh = MAX(60, (int)(c->bh0 * nz + 0.5f));
			resizeclient(c, nx, ny, nw, nh);
			c->lx = c->x; c->ly = c->y; c->lw = c->w; c->lh = c->h; c->lvalid = 1;
		}
	noanim = saved;
	drawbar(m);
}

static void
canvaswheel(const Arg *arg)
{
	int x, y;

	if (getrootptr(&x, &y))
		canvaszoom(recttomon(x, y, 1, 1), x, y, arg->i > 0 ? 1.15f : 1 / 1.15f);
}

static void
canvaszoomreset(const Arg *arg)
{
	Monitor *m = selmon;

	if (m->canvas && m->cz != 1)
		canvaszoom(m, m->wx + m->ww / 2, m->wy + m->wh / 2, 1.0f / m->cz);
}

void
togglecanvas(const Arg *arg)
{
	Monitor *m = selmon;

	Client *zc;

	m->canvas = !m->canvas;
	m->cz = 1; m->cpx = m->cpy = 0;
	for (zc = m->clients; zc; zc = zc->next)
		zc->lvalid = 0;
	if (m->canvas) {
		m->canvaslt = m->lt[m->sellt];
		m->lt[m->sellt] = (Layout *)&canvaslayout;
	} else
		m->lt[m->sellt] = m->canvaslt ? m->canvaslt : &layouts[0];
	arrange(m);
	drawbar(m);
}

void
panmouse(const Arg *arg)
{
	int x, y, lx, ly;
	XEvent ev;
	Time lasttime = 0;

	if (!selmon->canvas)
		return;
	if (XGrabPointer(dpy, root, False, MOUSEMASK, GrabModeAsync, GrabModeAsync,
		None, cursor[CurMove]->cursor, CurrentTime) != GrabSuccess)
		return;
	if (!getrootptr(&x, &y)) {
		XUngrabPointer(dpy, CurrentTime);
		return;
	}
	lx = x; ly = y;
	noanim = 1; panning = 1;
	do {
		XMaskEvent(dpy, MOUSEMASK|ExposureMask|SubstructureRedirectMask, &ev);
		switch (ev.type) {
		case ConfigureRequest:
		case Expose:
		case MapRequest:
			handler[ev.type](&ev);
			break;
		case MotionNotify:
			if ((ev.xmotion.time - lasttime) <= (1000 / refreshrate))
				continue;
			lasttime = ev.xmotion.time;
			canvaspan(selmon, ev.xmotion.x - lx, ev.xmotion.y - ly);
			lx = ev.xmotion.x; ly = ev.xmotion.y;
			break;
		}
	} while (ev.type != ButtonRelease);
	XUngrabPointer(dpy, CurrentTime);
	noanim = 0; panning = 0;
	XSync(dpy, False);
}

static void
snaprect(Monitor *m, int sx, int sy, int *x, int *y, int *w, int *h)
{
	int g = (int)gappx;
	*x = m->wx + g; *y = m->wy + g; *w = m->ww - 2 * g; *h = m->wh - 2 * g;
	if (sx < 0) *w = (*w - g) / 2;
	else if (sx > 0) { *w = (*w - g) / 2; *x = m->wx + m->ww - g - *w; }
	if (sy < 0) *h = (*h - g) / 2;
	else if (sy > 0) { *h = (*h - g) / 2; *y = m->wy + m->wh - g - *h; }
}

/* Alt+arrows: snap to halves/quarters; undoing both axes returns the window to the tiling */
void
snapwin(const Arg *arg)
{
	Client *c = selmon->sel;
	int x, y, w, h;

	if (!c || c->isfullscreen)
		return;
	if (!c->isfloating) c->snapx = c->snapy = 0;
	switch (arg->i) {
	case 0: c->snapx = c->snapx == 1 ? 0 : -1; break;
	case 1: c->snapx = c->snapx == -1 ? 0 : 1; break;
	case 2: c->snapy = c->snapy == 1 ? 0 : -1; break;
	case 3: c->snapy = c->snapy == -1 ? 0 : 1; break;
	}
	if (!c->snapx && !c->snapy) {
		if (selmon->lt[selmon->sellt]->arrange) {
			c->isfloating = 0;
			arrange(selmon);
		} else {
			snaprect(selmon, 0, 0, &x, &y, &w, &h);
			resize(c, x + w / 8, y + h / 8, w * 3 / 4 - 2 * c->bw, h * 3 / 4 - 2 * c->bw, 0);
		}
		return;
	}
	c->isfloating = 1;
	snaprect(selmon, c->snapx, c->snapy, &x, &y, &w, &h);
	resize(c, x, y, w - 2 * c->bw, h - 2 * c->bw, 0);
	arrange(selmon);
}

static void
floatnow(Client *c)
{
	if (!c->isfloating && selmon->lt[selmon->sellt]->arrange) {
		c->isfloating = 1;
		c->snapx = c->snapy = 2; /* free-form */
	}
}

void
movewin(const Arg *arg)
{
	Client *c = selmon->sel;
	int dx = 0, dy = 0, st = 48;

	if (!c || c->isfullscreen)
		return;
	floatnow(c);
	switch (arg->i) { case 0: dx = -st; break; case 1: dx = st; break; case 2: dy = -st; break; case 3: dy = st; break; }
	resize(c, c->x + dx, c->y + dy, c->w, c->h, 1);
	arrange(selmon);
}

void
sizewin(const Arg *arg)
{
	Client *c = selmon->sel;
	int dw = 0, dh = 0, st = 48;

	if (!c || c->isfullscreen)
		return;
	floatnow(c);
	switch (arg->i) { case 0: dw = -st; break; case 1: dw = st; break; case 2: dh = -st; break; case 3: dh = st; break; }
	resize(c, c->x, c->y, MAX(120, c->w + dw), MAX(90, c->h + dh), 1);
	arrange(selmon);
}

static Monitor *
mapmon(long *v, unsigned long n, int xi)
{
	int px, py;

	if (n >= (unsigned long)xi + 2)
		return recttomon((int)v[xi], (int)v[xi + 1], 1, 1);
	return getrootptr(&px, &py) ? recttomon(px, py, 1, 1) : selmon;
}

/* xprop -root -f _RICE_CMD 32c -set _RICE_CMD "1, X, Y": cmd 1 = go to the first empty tag on the monitor at X,Y
   (tile layout, focus moved there) so a scene of apps can be launched into it */
void
ricecmdrun(void)
{
	Atom type;
	int fmt;
	unsigned long n, after;
	unsigned char *p = NULL;
	long *v;

	if (XGetWindowProperty(dpy, root, ricecmd, 0, 8, False, XA_CARDINAL, &type, &fmt, &n, &after, &p) != Success || !p)
		return;
	v = (long *)p;
	if (n >= 1 && v[0] == 5) {   /* 5 = reload ~/.config/rice/binds.conf */
		loadkeys();
		grabkeys();
	}
	if (n >= 2 && v[0] >= 2 && v[0] <= 4) {   /* 2 = gap, 3 = gap above bar, 4 = bar side gap (pixels) */
		long x = v[1] < 0 ? 0 : v[1] > 80 ? 80 : v[1];
		if (v[0] == 2) gappx = (unsigned int)x;
		else if (v[0] == 3) vertpad = (unsigned int)x;
		else sidepad = (unsigned int)x;
		arrange(NULL);
	}
	if (n >= 1 && v[0] == 6) {   /* 6 = dump windows of the monitor under the pointer into root _RICE_MAP */
		Monitor *m = mapmon(v, n, 1);   /* 6,0 = pointer monitor; 6,X,Y = monitor at X,Y */
		Client *c;
		long out[512];
		char an[24];
		int k = 0, cnt = 0;

		out[k++] = m->mx; out[k++] = m->my; out[k++] = m->mw; out[k++] = m->mh;
		out[k++] = m->wx; out[k++] = m->wy; out[k++] = m->ww; out[k++] = m->wh;
		out[k++] = m->canvas; k++;
		for (c = m->clients; c && k + 6 <= 500; c = c->next)
			if (ISVISIBLE(c)) {
				out[k++] = (long)c->win; out[k++] = c->x; out[k++] = c->y;
				out[k++] = c->w; out[k++] = c->h; out[k++] = (c == m->sel);
				cnt++;
			}
		out[9] = cnt;
		snprintf(an, sizeof an, "_RICE_MAP_%d_%d", m->mx, m->my);
		XChangeProperty(dpy, root, XInternAtom(dpy, an, False), XA_CARDINAL, 32,
			PropModeReplace, (unsigned char *)out, k);
		XFlush(dpy);
	}
	if (n >= 3 && v[0] == 11) {   /* 11, key, value: 1 tag style (0 dots 1 numbers 2 dashes 3 pill only), 2 title, 3 layout label */
		if (v[1] == 1 && v[2] >= 0 && v[2] <= 3) tagstyle = (int)v[2];
		else if (v[1] == 2) showtitle = v[2] != 0;
		else if (v[1] == 3) showlayout = v[2] != 0;
		arrange(NULL);
		drawbars();
	}
	if (n >= 3 && v[0] == 7) {   /* 7, dx, dy = pan every visible window on the pointer's monitor (canvas mode) */
		Monitor *m;
		int dx = (int)v[1], dy = (int)v[2];

		m = mapmon(v, n, 3);   /* 7,dx,dy[,X,Y] */
		canvaspan(m, dx, dy);
	}
	if (n >= 3 && v[0] == 8) {   /* 8, dx, dy = same but at once, no easing (live drag in the map) */
		Monitor *m;
		int dx = (int)v[1], dy = (int)v[2];

		m = mapmon(v, n, 3);
		noanim = 1;
		canvaspan(m, dx, dy);
		noanim = 0;
	}
	if (n >= 4 && v[0] == 10) {   /* 10, win, x, y = put that window at x,y at once (drag in the map) */
		Client *c = wintoclient((Window)v[1]);

		if (c && !c->isfullscreen) {
			noanim = 1;
			resizeclient(c, (int)v[2], (int)v[3], c->w, c->h);
			noanim = 0;
		}
	}
	if (n >= 2 && v[0] == 9) {   /* 9, win = focus that window (and its monitor) */
		Client *c = wintoclient((Window)v[1]);

		if (c) {
			if (c->mon != selmon) {
				unfocus(selmon->sel, 0);
				selmon = c->mon;
			}
			if (!ISVISIBLE(c)) {   /* dock click on a window on a hidden tag: go to its tag first */
				Arg a = {.ui = c->tags & TAGMASK};
				view(&a);
			}
			focus(c);
			restack(selmon);
		}
	}
	if (n >= 3 && v[0] == 1) {
		Monitor *m = recttomon((int)v[1], (int)v[2], 1, 1);
		unsigned int i, used = 0;
		Client *c;
		Arg a;

		if (m != selmon) {
			unfocus(selmon->sel, 0);
			selmon = m;
		}
		if (m->canvas)
			togglecanvas(NULL);
		for (c = m->clients; c; c = c->next)
			used |= c->tags;
		for (i = 0; i < LENGTH(tags) && (used & 1 << i); i++);
		if (i >= LENGTH(tags))
			i = LENGTH(tags) - 1;
		m->lt[m->sellt] = &layouts[0];
		a.ui = 1 << i;
		view(&a);
		focus(NULL);
	}
	XFree(p);
}
