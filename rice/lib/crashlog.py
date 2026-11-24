"""Crash log for the rice scripts: Python exceptions (also in threads) and hard crashes (faulthandler) go to
   ~/.cache/rice/crash.log with the script name, so a script that vanishes leaves a trace."""
import os, sys, time, threading, traceback, faulthandler

_P = os.path.expanduser("~/.cache/rice/crash.log")
NAME = os.path.basename(sys.argv[0]) if sys.argv and sys.argv[0] else "?"
try:
    os.makedirs(os.path.dirname(_P), exist_ok=True)
    if os.path.exists(_P) and os.path.getsize(_P) > 200_000:        # keep it small
        os.replace(_P, _P + ".old")
    _f = open(_P, "a", buffering=1)
    faulthandler.enable(file=_f, all_threads=True)
except Exception:
    _f = None


def _log(kind, text):
    try:
        with open(_P, "a") as f:
            f.write(f"\n=== {time.strftime('%Y-%m-%d %H:%M:%S')} {NAME} pid {os.getpid()} {kind}\n{text}")
    except Exception:
        pass


_old = sys.excepthook


def _hook(t, v, tb):
    _log("uncaught", "".join(traceback.format_exception(t, v, tb)))
    _old(t, v, tb)


sys.excepthook = _hook
threading.excepthook = lambda a: _log("thread " + (a.thread.name if a.thread else "?"), "".join(traceback.format_exception(a.exc_type, a.exc_value, a.exc_traceback)))
