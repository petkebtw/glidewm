/* rice-supervise CMD [ARGS...]: run a long-lived helper and restart it if it dies (logged to
 * ~/.cache/rice/crash.log). Exit 0 / SIGTERM (143) = stopped on purpose; X gone = session ending; 5 quick crashes
 * in a row (each within 20 s) = give up. C rewrite of the sh version (2026-11-26: ~0.4 MB -> ~0.1 MB each). */
#include <fcntl.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

/* xprop -root -len 0 _NET_SUPPORTED: is X still there (run only after a crash) */
static int x_alive(void)
{
	pid_t p = fork();
	int st;
	if (p == 0) {
		int nul = open("/dev/null", O_WRONLY);
		if (nul >= 0) { dup2(nul, 1); dup2(nul, 2); }
		execlp("xprop", "xprop", "-root", "-len", "0", "_NET_SUPPORTED", (char *)NULL);
		_exit(127);
	}
	if (p < 0) return 1;
	waitpid(p, &st, 0);
	return WIFEXITED(st) && WEXITSTATUS(st) == 0;
}

int main(int argc, char **argv)
{
	const char *home = getenv("HOME");
	char dir[4096], log[4200];
	int n = 0;

	if (argc < 2) { fputs("usage: rice-supervise CMD [ARGS...]\n", stderr); return 2; }
	snprintf(dir, sizeof dir, "%s/.cache", home ? home : ".");
	mkdir(dir, 0755);
	snprintf(dir, sizeof dir, "%s/.cache/rice", home ? home : ".");
	mkdir(dir, 0755);
	snprintf(log, sizeof log, "%s/crash.log", dir);
	for (;;) {
		time_t t0 = time(NULL);
		pid_t p = fork();
		int st, rc;
		if (p == 0) {
			execvp(argv[1], argv + 1);
			_exit(127);
		}
		if (p < 0) return 1;
		while (waitpid(p, &st, 0) < 0) ;
		rc = WIFEXITED(st) ? WEXITSTATUS(st) : 128 + WTERMSIG(st);   /* as sh reports it */
		if (rc == 0 || rc == 143) return 0;
		if (!x_alive()) return 0;
		{
			FILE *f = fopen(log, "a");
			if (f) {
				char ts[32];
				time_t now = time(NULL);
				strftime(ts, sizeof ts, "%F %T", localtime(&now));
				fprintf(f, "\n=== %s supervise: %s exited with %d\n", ts, argv[1], rc);
				fclose(f);
			}
		}
		n = time(NULL) - t0 < 20 ? n + 1 : 0;
		if (n >= 5) return 1;
		sleep(2);
	}
}
