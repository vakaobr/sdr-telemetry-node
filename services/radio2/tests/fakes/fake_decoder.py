#!/usr/bin/env python3
"""Scripted fake decoder for proc/supervisor integration tests (P7.3).

Behaviour via $FAKE_MODE — exercises the REAL spawn/SIGTERM/SIGKILL/heartbeat
path (the plan mandates scripted executables, not Python mocks):
  run    (default) heartbeat lines forever; exits 0 on SIGTERM
  fail   prints one line, exits non-zero immediately (start failure)
  silent stays alive but emits NO heartbeats after the first (watchdog bait)
  hang   ignores SIGTERM and never stops → forces SIGKILL escalation
"""

import os
import signal
import sys
import time

mode = os.environ.get("FAKE_MODE", "run")

if mode == "fail":
    print("fake: failing to start", flush=True)
    sys.exit(3)

_running = True


def _on_term(_sig, _frm):
    global _running
    if mode != "hang":
        _running = False


signal.signal(signal.SIGTERM, _on_term)

print(f"fake decoder up mode={mode} argv={sys.argv[1:]}", flush=True)

first = True
while _running:
    if mode == "silent":
        if first:
            first = False
        # after the first line, go quiet but stay alive
    else:
        print("heartbeat", flush=True)
    time.sleep(0.05)

print("fake decoder exiting", flush=True)
sys.exit(0)
