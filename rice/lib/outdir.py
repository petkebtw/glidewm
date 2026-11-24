"""Per-tool output folder, stored in settings.json under sys (out_shot, out_convert, out_dl)."""
import os, subprocess
import settings
from gi.repository import GLib

HOME = os.path.expanduser("~")


def get(kind, default=None):
    d = settings.sget("out_" + kind) or default
    d = os.path.expanduser(d) if d else d
    return d


def show(d, none="next to source"):
    return d.replace(HOME, "~") if d else none


def choose(kind, default, cb, none=None, title="Choose folder", before=None, after=None):
    """Open rice-folder; cb(path_or_None) runs on the main loop. before/after run around it (release/regrab grabs)."""
    cur = get(kind, default) or HOME
    cmd = ["rice-folder", cur, "--title", title] + (["--none", none] if none else [])
    if before:
        before()
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True, start_new_session=True)

    def done(pid, status):
        out = p.stdout.read().strip("\n") if p.stdout else ""
        ok = os.WIFEXITED(status) and os.WEXITSTATUS(status) == 0
        if ok:
            settings.sput("out_" + kind, out or None)
        if after:
            after()
        cb((out or None) if ok else False)
    GLib.child_watch_add(GLib.PRIORITY_DEFAULT, p.pid, done)
