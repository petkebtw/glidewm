/* rice-cava [small]: the music for the visualizer (cava), as numbers on stdout. Listens to what the speakers or
 * headphones play (the monitor of the default output), never to the microphone, and starts cava again when the
 * default output or Settings > Desktop > Frame rate ("fps" in ~/.config/rice/desktop.json; 0 = 144) changes.
 * small: 12 levels, 30 a second (the moving wallpapers, rice-scene).
 * C rewrite of the bash version (2026-11-26: ~1 MB of bash -> ~0.1 MB), same config file, same checks every 3 s;
 * ends with the Quickshell that started it, and cava with it. */
#define _GNU_SOURCE
#include <ctype.h>
#include <fcntl.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/prctl.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <unistd.h>

static int small;
static char cfg[4200], logf[4200], desk[4200];
static volatile pid_t cava = -1;

static void stop(int s)
{
	(void)s;
	if (cava > 0) kill(cava, SIGTERM);
	_exit(0);
}

/* stdout of a command (first line), "" if it fails */
static void run(char *const argv[], char *out, size_t len)
{
	int p[2], st;
	pid_t pid;
	size_t n = 0;
	ssize_t r;
	out[0] = 0;
	if (pipe2(p, O_CLOEXEC)) return;
	if ((pid = fork()) == 0) {
		int nul = open("/dev/null", O_RDWR);
		dup2(p[1], 1);
		if (nul >= 0) { dup2(nul, 0); dup2(nul, 2); }
		execvp(argv[0], argv);
		_exit(127);
	}
	close(p[1]);
	if (pid < 0) { close(p[0]); return; }
	while (n < len - 1 && (r = read(p[0], out + n, len - 1 - n)) > 0) n += r;
	close(p[0]);
	waitpid(pid, &st, 0);
	out[n] = 0;
	if (!WIFEXITED(st) || WEXITSTATUS(st)) { out[0] = 0; return; }
	out[strcspn(out, "\n")] = 0;
}

static int have(const char *cmd)
{
	const char *path = getenv("PATH");
	char buf[4096], *dirs, *d, *save;
	int ok = 0;
	if (!path) return 0;
	dirs = strdup(path);
	for (d = strtok_r(dirs, ":", &save); d && !ok; d = strtok_r(NULL, ":", &save)) {
		snprintf(buf, sizeof buf, "%s/%s", d, cmd);
		ok = access(buf, X_OK) == 0;
	}
	free(dirs);
	return ok;
}

/* pactl get-default-sink, else wpctl's node.name */
static void sink(char *s, size_t len)
{
	char *pa[] = { "pactl", "get-default-sink", NULL };
	char *wp[] = { "wpctl", "inspect", "@DEFAULT_AUDIO_SINK@", NULL };
	char buf[16384], *p, *q;
	run(pa, s, len);
	if (*s) return;
	/* wpctl inspect: the whole output (run() keeps only the first line) */
	{
		int pp[2], st;
		pid_t pid;
		size_t n = 0;
		ssize_t r;
		buf[0] = 0;
		if (pipe2(pp, O_CLOEXEC)) return;
		if ((pid = fork()) == 0) {
			int nul = open("/dev/null", O_RDWR);
			dup2(pp[1], 1);
			if (nul >= 0) dup2(nul, 2);
			execvp(wp[0], wp);
			_exit(127);
		}
		close(pp[1]);
		while (n < sizeof buf - 1 && (r = read(pp[0], buf + n, sizeof buf - 1 - n)) > 0) n += r;
		close(pp[0]);
		if (pid > 0) waitpid(pid, &st, 0);
		buf[n] = 0;
	}
	if ((p = strstr(buf, "node.name = \"")) && (q = strchr(p + 13, '"'))) {
		*q = 0;
		snprintf(s, len, "%s", p + 13);
	}
}

/* the frame rate from desktop.json, as the sed did: the first line with "fps":, its last match */
static int fps(void)
{
	FILE *f = fopen(desk, "r");
	char line[8192];
	int v = 60, found = 0;
	if (f) {
		while (!found && fgets(line, sizeof line, f)) {
			char *p = line, *hit = NULL, *q;
			while ((p = strstr(p, "\"fps\":"))) { hit = p; p++; }
			if (!hit) continue;
			found = 1;
			q = hit + 6;
			while (*q == ' ') q++;
			if (isdigit((unsigned char)*q)) v = atoi(q);
			else v = 60;   /* empty: the default */
		}
		fclose(f);
	}
	if (v == 0) v = 144;
	if (v > 240) v = 240;
	return small ? 30 : v;
}

static int write_cfg(void)
{
	char s[512];
	const char *method = "pipewire";
	char source[600] = "auto";
	int bars = small ? 12 : 64, fr = fps();
	FILE *f;
	sink(s, sizeof s);
	if (*s && have("pactl")) { method = "pulse"; snprintf(source, sizeof source, "%s.monitor", s); }
	if (!(f = fopen(cfg, "w"))) return fr;
	fprintf(f, "[general]\nbars = %d\nframerate = %d\n"
	           "# silence for 2 s: cava rests (no frames, almost no CPU) until the music comes back\n"
	           "sleep_timer = 2\nautosens = 1\nsensitivity = 120\nlower_cutoff_freq = 40\nhigher_cutoff_freq = 12000\n"
	           "[input]\nmethod = %s\nsource = %s\n"
	           "[output]\nmethod = raw\nraw_target = /dev/stdout\ndata_format = ascii\nascii_max_range = 100\n"
	           "bar_delimiter = 59\nframe_delimiter = 10\n[smoothing]\nmonstercat = 0\nnoise_reduction = 45\n",
	        bars, fr, method, source);
	fclose(f);
	return fr;
}

int main(int argc, char **argv)
{
	const char *home = getenv("HOME");
	char dir[4096];
	pid_t parent = getppid();
	struct sigaction sa = { 0 };

	small = argc > 1 && !strcmp(argv[1], "small");
	snprintf(dir, sizeof dir, "%s/.cache/rice", home ? home : ".");
	snprintf(cfg, sizeof cfg, "%s/cava-%s.conf", dir, small ? "small" : "widget");
	snprintf(logf, sizeof logf, "%s/cava-%s.log", dir, small ? "small" : "widget");
	snprintf(desk, sizeof desk, "%s/.config/rice/desktop.json", home ? home : ".");
	{
		char c[4096];
		snprintf(c, sizeof c, "%s/.cache", home ? home : ".");
		mkdir(c, 0755);
		mkdir(dir, 0755);
	}
	sa.sa_handler = stop;
	sigaction(SIGTERM, &sa, NULL);
	sigaction(SIGINT, &sa, NULL);
	sigaction(SIGHUP, &sa, NULL);
	prctl(PR_SET_PDEATHSIG, SIGTERM);   /* the shell that started it is gone: stop() ends cava too */
	signal(SIGPIPE, SIG_DFL);
	for (;;) {
		char cur[512], now[512];
		int curfps = write_cfg(), st;
		pid_t c;
		sink(cur, sizeof cur);
		if ((c = fork()) == 0) {
			int l = open(logf, O_WRONLY | O_CREAT | O_APPEND, 0644);
			if (l >= 0) dup2(l, 2);
			prctl(PR_SET_PDEATHSIG, SIGTERM);
			execlp("cava", "cava", "-p", cfg, (char *)NULL);
			_exit(127);
		}
		cava = c;
		for (;;) {
			sleep(3);
			if (waitpid(c, &st, WNOHANG) == c) { cava = -1; break; }   /* cava ended */
			if (kill(parent, 0) != 0 || getppid() != parent) stop(0);
			sink(now, sizeof now);
			if (strcmp(now, cur) || fps() != curfps) {   /* a new output, or a new frame rate */
				kill(c, SIGTERM);
				waitpid(c, &st, 0);
				cava = -1;
				break;
			}
		}
		sleep(1);
	}
}
