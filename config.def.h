/* See LICENSE file for copyright and license details. */
#include <X11/XF86keysym.h>

/* gemini bullshit */
static const unsigned int systrayspacing = 2;   /* systray spacing */
static const unsigned int systraypinning = 1;   /* 0: sloppy systray follows selected monitor, >0: pin systray to monitor X */
static const unsigned int systraypinningfailfirst = 1; /* 1: if pinning fails, display systray on the first monitor, False: display systray on the last monitor*/
static const int showsystray        = 1;     /* 0 means no systray */
static const int systrayonleft      = 0;     /* 0: systray in the right corner, >0: systray on left of status text */

/* appearance */
static const unsigned int borderpx  = 2;        /* border pixel of windows */
static const unsigned int snap      = 32;       /* snap pixel */
static unsigned int gappx           = 10;       /* gap between windows and screen edge */
static const unsigned int barpad    = 8;        /* extra bar height */
static unsigned int vertpad   = 10;       /* gap above bar */
static unsigned int sidepad   = 12;       /* gap left/right of bar */
static const unsigned int ulh       = 2;        /* tag underline height */
static const int showbar            = 1;        /* 0 means no bar */
static const int topbar             = 1;        /* 0 means bottom bar */
static const char *fonts[]          = { "JetBrains Mono:style=Bold:size=10", "Symbols Nerd Font:size=12" };
static const char dmenufont[]       = "monospace:size=10";
/* THEME_COLORS_START */
static char normbgcolor[]       = "#282a36";
static char normbordercolor[]       = "#44475a";
static char normfgcolor[]       = "#8a8ea8";
static char selfgcolor[]       = "#282a36";
static char selbgcolor[]      = "#bd93f9";
static char selbordercolor[]  = "#bd93f9";
/* THEME_COLORS_END */
static char *colors[][3]      = {
	/*               fg         bg         border   */
	[SchemeNorm] = { normfgcolor, normbgcolor, normbordercolor },
	[SchemeSel]  = { selfgcolor, selbgcolor, selbordercolor  },
};

/* tagging */
static const char *tags[] = { "", "", "", "", "", "", "", "", "" };

static const Rule rules[] = {
	/* xprop(1):
	 *	WM_CLASS(STRING) = instance, class
	 *	WM_NAME(STRING) = title
	 */
	/* class      instance    title       tags mask     isfloating   monitor */
	{ "Gimp",     NULL,       NULL,       0,            1,           -1 },
	{ "RiceAuth", NULL,       NULL,       0,            1,           -1 },
	{ "SCGlass",  NULL,       NULL,       0,            1,           -1 },
	{ "Firefox",  NULL,       NULL,       1 << 8,       0,           -1 },
};

/* layout(s) */
static const float mfact     = 0.55; /* factor of master area size [0.05..0.95] */
static const int nmaster     = 1;    /* number of clients in master area */
static const int resizehints = 1;    /* 1 means respect size hints in tiled resizals */
static const int lockfullscreen = 1; /* 1 will force focus on the fullscreen window */
static const int refreshrate = 120;  /* refresh rate (per second) for client move/resize */

static const char *layoutnames[] = { "tile", "bento", "dock", "mosaic" };

static const Layout layouts[] = {
	/* symbol     arrange function */
	{ "[]=",      tile },    /* first entry is default */
	{ "[B]",      bento },         /* hero left, uneven grid right */
	{ "[D]",      dock },          /* sidebar, main, widget column */
	{ "[#]",      mosaic },        /* staggered brick rows */
};

/* key definitions */
#define MODKEY Mod1Mask
#define TAGKEYS(KEY,TAG) \
	{ MODKEY,                       KEY,      view,           {.ui = 1 << TAG} }, \
	{ MODKEY|ControlMask,           KEY,      toggleview,     {.ui = 1 << TAG} }, \
	{ MODKEY|ShiftMask,             KEY,      tag,            {.ui = 1 << TAG} }, \
	{ MODKEY|ControlMask|ShiftMask, KEY,      toggletag,      {.ui = 1 << TAG} },

/* helper for spawning shell commands in the pre dwm-5.0 fashion */
#define SHCMD(cmd) { .v = (const char*[]){ "/bin/sh", "-c", cmd, NULL } }

/* commands */
static char dmenumon[2] = "0"; /* component of dmenucmd, manipulated in spawn() */
static const char *dmenucmd[] = { "rofi-launcher", NULL };
static const char *clipcmd[]   = { "clip-pick", NULL };
static const char *mediacmd[]  = { "rice-media", "toggle", NULL };
static const char *mediapp[]   = { "rice-media", "play-pause", NULL };
static const char *medianext[] = { "rice-media", "next", NULL };
static const char *mediaprev[] = { "rice-media", "prev", NULL };
static const char *themecmd[]  = { "theme-switch", NULL };
static const char *toolscmd[]  = { "rice-tools", NULL };
static const char *mapcmd[]    = { "rice-map", NULL };
static const char *setcmd[]    = { "rice-settings", NULL };
static const char *searchcmd[] = { "rice-search", NULL };
static const char *shotcmd[]   = { "screenshot.sh", NULL };
static const char *termcmd[]  = { "konsole", NULL };
static const char *volup[]  = { "dwm-volume", "up", NULL };
static const char *voldown[]  = { "dwm-volume", "down", NULL };
static const char *volmute[]  = { "dwm-volume", "mute", NULL };
static const char *volmenu[]  = { "rice-volume", NULL };
static const char *powermenu[] = { "rice-power", NULL };
static const char *lockcmd[]  = { "rice-lock", NULL };
static const char *reccmd[]   = { "rice-record", NULL };

static const Key keys[] = {
	/* modifier                     key        function        argument */
	{ MODKEY,                       XK_p,      spawn,          {.v = dmenucmd } },
	{ MODKEY,                       XK_n,      spawn,          SHCMD("rice-center") },
	{ MODKEY,                       XK_e,      spawn,          SHCMD("rice-desk --edit") },
	{ MODKEY|ShiftMask,             XK_e,      spawn,          SHCMD("rice-desk --add") },
	{ MODKEY,                       XK_g,      spawn,          SHCMD("rice-gamebar") },
	{ 0,                            XK_Print,  spawn,          SHCMD("~/.local/bin/screenshot.sh") },
	{ MODKEY|ShiftMask,             XK_Return, spawn,          {.v = termcmd } },
	{ 0,                            XF86XK_AudioRaiseVolume, spawn, {.v = volup } },
	{ 0,                            XF86XK_AudioLowerVolume, spawn, {.v = voldown } },
	{ 0,                            XF86XK_AudioMute,        spawn, {.v = volmute } },
	{ MODKEY,                       XK_b,      togglebar,      {0} },
	{ MODKEY,                       XK_minus,  setgaps,        {.i = -2 } },
	{ MODKEY,                       XK_equal,  setgaps,        {.i = +2 } },
	{ MODKEY|ShiftMask,             XK_equal,  setgaps,        {.i = 0 } },
	{ MODKEY|ShiftMask,             XK_t,      spawn,          {.v = themecmd } },
	{ MODKEY|ShiftMask,             XK_o,      spawn,          {.v = toolscmd } },
	{ MODKEY,                       XK_z,      spawn,          {.v = mapcmd } },
	{ MODKEY|ControlMask,           XK_0,      canvaszoomreset, {0} },
	{ MODKEY,                       XK_o,      spawn,          {.v = setcmd } },
	{ MODKEY,                       XK_s,      spawn,          {.v = searchcmd } },
	{ MODKEY,                       XK_v,      spawn,          {.v = clipcmd } },
	{ MODKEY|ShiftMask,             XK_m,      spawn,          {.v = mediacmd } },
	{ MODKEY|ShiftMask,             XK_s,      spawn,          {.v = shotcmd } },
	{ 0,                            XF86XK_AudioPlay,        spawn, {.v = mediapp } },
	{ 0,                            XF86XK_AudioNext,        spawn, {.v = medianext } },
	{ 0,                            XF86XK_AudioPrev,        spawn, {.v = mediaprev } },
	{ MODKEY,                       XK_j,      focusstack,     {.i = +1 } },
	{ MODKEY,                       XK_k,      focusstack,     {.i = -1 } },
	{ MODKEY,                       XK_i,      incnmaster,     {.i = +1 } },
	{ MODKEY,                       XK_d,      incnmaster,     {.i = -1 } },
	{ MODKEY,                       XK_h,      setmfact,       {.f = -0.05} },
	{ MODKEY,                       XK_l,      setmfact,       {.f = +0.05} },
	{ MODKEY,                       XK_Return, zoom,           {0} },
	{ MODKEY,                       XK_Tab,    view,           {0} },
	{ MODKEY|ShiftMask,             XK_c,      killclient,     {0} },
	{ MODKEY,                       XK_t,      setlayout,      {.v = &layouts[0]} },
	{ MODKEY,                       XK_space,  cyclelayout,    {.i = +1} },   /* one key through every layout */
	{ MODKEY|ControlMask,           XK_space,  resetlayout,    {0} },         /* back to the default (tile) */
	{ MODKEY|ShiftMask,             XK_space,  togglefloating, {0} },
	{ MODKEY,                       XK_0,      view,           {.ui = ~0 } },
	{ MODKEY|ShiftMask,             XK_0,      tag,            {.ui = ~0 } },
	{ MODKEY,                       XK_comma,  focusmon,       {.i = -1 } },
	{ MODKEY,                       XK_period, focusmon,       {.i = +1 } },
	{ MODKEY|ShiftMask,             XK_comma,  tagmon,         {.i = -1 } },
	{ MODKEY|ShiftMask,             XK_period, tagmon,         {.i = +1 } },
	{ MODKEY,                       XK_F5,     xrdb,           {.v = NULL } },
	TAGKEYS(                        XK_1,                      0)
	TAGKEYS(                        XK_2,                      1)
	TAGKEYS(                        XK_3,                      2)
	TAGKEYS(                        XK_4,                      3)
	TAGKEYS(                        XK_5,                      4)
	TAGKEYS(                        XK_6,                      5)
	TAGKEYS(                        XK_7,                      6)
	TAGKEYS(                        XK_8,                      7)
	TAGKEYS(                        XK_9,                      8)
	{ MODKEY|ShiftMask,             XK_g,      togglecanvas,   {0} },
	{ MODKEY|ShiftMask,             XK_l,      spawn,          {.v = lockcmd } },
	{ MODKEY|ShiftMask,             XK_r,      spawn,          {.v = reccmd } },
	{ MODKEY,                       XK_Left,   snapwin,        {.i = 0 } },
	{ MODKEY,                       XK_Right,  snapwin,        {.i = 1 } },
	{ MODKEY,                       XK_Up,     snapwin,        {.i = 2 } },
	{ MODKEY,                       XK_Down,   snapwin,        {.i = 3 } },
	{ MODKEY|ShiftMask,             XK_Left,   movewin,        {.i = 0 } },
	{ MODKEY|ShiftMask,             XK_Right,  movewin,        {.i = 1 } },
	{ MODKEY|ShiftMask,             XK_Up,     movewin,        {.i = 2 } },
	{ MODKEY|ShiftMask,             XK_Down,   movewin,        {.i = 3 } },
	{ MODKEY|ControlMask,           XK_Left,   sizewin,        {.i = 0 } },
	{ MODKEY|ControlMask,           XK_Right,  sizewin,        {.i = 1 } },
	{ MODKEY|ControlMask,           XK_Up,     sizewin,        {.i = 2 } },
	{ MODKEY|ControlMask,           XK_Down,   sizewin,        {.i = 3 } },
	{ MODKEY|ShiftMask,             XK_q,      quit,           {0} },
	{ MODKEY|ControlMask|ShiftMask, XK_q,      quit,           {.i = 1} },  /* restart dwm, keep windows */
	{ MODKEY|ShiftMask,             XK_j,      movestack,      {.i = +1} },
	{ MODKEY|ShiftMask,             XK_k,      movestack,      {.i = -1} },
};
/* button definitions */
/* click can be ClkTagBar, ClkLtSymbol, ClkStatusText, ClkWinTitle, ClkClientWin, or ClkRootWin */
static const Button buttons[] = {
	/* click                event mask      button          function        argument */
	{ ClkLtSymbol,          0,              Button1,        cyclelayout,    {.i = +1} },
	{ ClkLtSymbol,          0,              Button3,        resetlayout,    {0} },
	{ ClkWinTitle,          0,              Button2,        zoom,           {0} },
	{ ClkStatusText,        0,              Button1,        spawnat,        {.v = volmenu } },
	{ ClkAccount,           0,              Button1,        spawnat,        {.v = powermenu } },
	{ ClkRootWin,           0,              Button1,        panmouse,       {0} },
	{ ClkClientWin,         MODKEY|ShiftMask, Button1,      panmouse,       {0} },
	{ ClkStatusText,        0,              Button2,        spawn,          {.v = volmute } },
	{ ClkStatusText,        0,              Button4,        spawn,          {.v = volup } },
	{ ClkStatusText,        0,              Button5,        spawn,          {.v = voldown } },
	{ ClkClientWin,           MODKEY,         Button4,        canvaswheel,    {.i = +1} },
	{ ClkClientWin,           MODKEY,         Button5,        canvaswheel,    {.i = -1} },
	{ ClkRootWin,             MODKEY,         Button4,        canvaswheel,    {.i = +1} },
	{ ClkRootWin,             MODKEY,         Button5,        canvaswheel,    {.i = -1} },
	{ ClkClientWin,         MODKEY,         Button1,        movemouse,      {0} },
	{ ClkClientWin,         MODKEY,         Button2,        togglefloating, {0} },
	{ ClkClientWin,         MODKEY,         Button3,        resizemouse,    {0} },
	{ ClkTagBar,            0,              Button1,        view,           {0} },
	{ ClkTagBar,            0,              Button3,        toggleview,     {0} },
	{ ClkTagBar,            MODKEY,         Button1,        tag,            {0} },
	{ ClkTagBar,            MODKEY,         Button3,        toggletag,      {0} },
};
