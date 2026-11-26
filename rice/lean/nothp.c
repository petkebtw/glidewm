/* nothp: run a program with transparent huge pages off for it and every child (prctl PR_SET_THP_DISABLE is
 * inherited across fork and exec). The kernel default here is THP "always", which backs every large heap
 * region in 2 MB pages; the desktop shell and picom held ~250 MB of mostly empty huge pages at login. */
#include <stdio.h>
#include <sys/prctl.h>
#include <unistd.h>
int main(int argc, char **argv) {
	if (argc < 2) { fprintf(stderr, "usage: nothp command [args...]\n"); return 2; }
	prctl(PR_SET_THP_DISABLE, 1, 0, 0, 0);
	execvp(argv[1], argv + 1);
	perror(argv[1]);
	return 127;
}
