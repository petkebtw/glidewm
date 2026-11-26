/* dwm-status: the dwm bar status, root WM_NAME = "<vol level>\x01<Day dd Mon  HH:MM>". Level: m muted, 1..3
 * (2 when wpctl does not answer). Refreshes every 10 s, on SIGRTMIN+10 (pkill -RTMIN+10 -x dwm-status, from the
 * volume tools) and on every PipeWire sink/server change (a `pactl subscribe` child; restarted 5 s after it ends,
 * and once a day). C rewrite of the bash version (2026-11-26: bash x3 + grep + timeout ~3 MB -> ~0.3 MB);
 * every wpctl call still has a 2 s limit (a hung PipeWire makes wpctl block forever). */
#define _GNU_SOURCE
#include <fcntl.h>
#include <locale.h>
#include <poll.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/prctl.h>
#include <sys/signalfd.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>
#include <X11/Xlib.h>

static pid_t spawn_pipe(char *const argv[], int *rd)
{
	int p[2];
	pid_t pid;
	if (pipe2(p, O_CLOEXEC)) return -1;
	if ((pid = fork()) == 0) {
		sigset_t none;
		sigemptyset(&none);
		sigprocmask(SIG_SETMASK, &none, NULL);
		prctl(PR_SET_PDEATHSIG, SIGTERM);   /* pactl/wpctl end with dwm-status */
		dup2(p[1], 1);
		int nul = open("/dev/null", O_RDWR);
		if (nul >= 0) { dup2(nul, 0); dup2(nul, 2); }
		execvp(argv[0], argv);
		_exit(127);
	}
	close(p[1]);
	if (pid < 0) { close(p[0]); return -1; }
	*rd = p[0];
	return pid;
}

/* timeout 2 wpctl get-volume @DEFAULT_AUDIO_SINK@ -> m, 1, 2, 3 */
static char level(void)
{
	char *argv[] = { "wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@", NULL };
	char out[256] = "";
	size_t n = 0;
	int fd, st, ok = 0;
	struct timespec t0, t;
	pid_t pid = spawn_pipe(argv, &fd);
	if (pid < 0) return '2';
	clock_gettime(CLOCK_MONOTONIC, &t0);
	for (;;) {
		struct pollfd p = { fd, POLLIN, 0 };
		long left;
		ssize_t r;
		clock_gettime(CLOCK_MONOTONIC, &t);
		left = 2000 - ((t.tv_sec - t0.tv_sec) * 1000 + (t.tv_nsec - t0.tv_nsec) / 1000000);
		if (left <= 0 || poll(&p, 1, (int)left) <= 0) { kill(pid, SIGKILL); break; }
		r = read(fd, out + n, sizeof out - 1 - n);
		if (r <= 0) { ok = 1; break; }
		n += r;
		if (n >= sizeof out - 1) { ok = 1; break; }
	}
	close(fd);
	waitpid(pid, &st, 0);
	out[n] = 0;
	if (!ok || !WIFEXITED(st) || WEXITSTATUS(st)) return '2';
	if (strstr(out, "MUTED")) return 'm';
	{
		char *v = strstr(out, "Volume:");
		double f;
		int pct;
		if (!v || sscanf(v + 7, "%lf", &f) != 1) return '2';
		pct = (int)(f * 100 + 0.5);
		return pct == 0 ? 'm' : pct < 34 ? '1' : pct < 67 ? '2' : '3';
	}
}

static void draw(Display *dpy)
{
	char s[128], d[64], h[16];
	time_t now = time(NULL);
	struct tm *tm = localtime(&now);
	strftime(d, sizeof d, "%a %d %b", tm);
	strftime(h, sizeof h, "%H:%M", tm);
	snprintf(s, sizeof s, "%c\x01%s  %s", level(), d, h);
	XStoreName(dpy, DefaultRootWindow(dpy), s);
	XFlush(dpy);
}

int main(void)
{
	Display *dpy;
	sigset_t set;
	int sfd, sub = -1;
	pid_t subpid = -1;
	time_t sub_started = 0, sub_retry = 0;
	char buf[4096];
	size_t blen = 0;

	setlocale(LC_TIME, "");
	if (!(dpy = XOpenDisplay(NULL))) return 1;
	sigemptyset(&set);
	sigaddset(&set, SIGRTMIN + 10);
	sigaddset(&set, SIGCHLD);
	sigprocmask(SIG_BLOCK, &set, NULL);
	sfd = signalfd(-1, &set, SFD_CLOEXEC);
	for (;;) {
		struct pollfd p[2];
		time_t deadline;
		int dirty = 0;

		draw(dpy);
		deadline = time(NULL) + 10;
		while (!dirty) {
			time_t now = time(NULL);
			int np = 1, timeout;
			/* pactl subscribe: (re)started when missing, 5 s after it ended; restarted daily */
			if (subpid < 0 && now >= sub_retry) {
				char *argv[] = { "pactl", "subscribe", NULL };
				if ((subpid = spawn_pipe(argv, &sub)) < 0) sub_retry = now + 5;
				else { sub_started = now; blen = 0; }
			}
			if (subpid > 0 && now - sub_started >= 86400) kill(subpid, SIGTERM);
			if (now >= deadline) break;
			p[0] = (struct pollfd){ sfd, POLLIN, 0 };
			if (sub >= 0) { p[1] = (struct pollfd){ sub, POLLIN, 0 }; np = 2; }
			timeout = (int)(deadline - now) * 1000;
			if (subpid < 0 && sub_retry > now && (sub_retry - now) * 1000 < timeout) timeout = (int)(sub_retry - now) * 1000;
			if (poll(p, np, timeout) <= 0) continue;
			if (p[0].revents & POLLIN) {
				struct signalfd_siginfo si;
				while (read(sfd, &si, sizeof si) == sizeof si) {
					if ((int)si.ssi_signo == SIGRTMIN + 10) dirty = 1;
					if (si.ssi_signo == SIGCHLD) {
						int st;
						pid_t c;
						while ((c = waitpid(-1, &st, WNOHANG)) > 0)
							if (c == subpid) subpid = -1, sub_retry = time(NULL) + 5;
					}
					break;
				}
			}
			if (np == 2 && p[1].revents) {
				ssize_t r = read(sub, buf + blen, sizeof buf - 1 - blen);
				char *nl;
				if (r <= 0) { close(sub); sub = -1; continue; }
				blen += r;
				buf[blen] = 0;
				while ((nl = memchr(buf, '\n', blen))) {
					*nl = 0;
					if (strstr(buf, "sink") || strstr(buf, "server")) dirty = 1;
					blen -= nl + 1 - buf;
					memmove(buf, nl + 1, blen);
				}
				if (blen == sizeof buf - 1) blen = 0;
			}
		}
	}
}
