#!/usr/bin/env python3
"""
Patch pylp 0.2.10 (the last release, https://github.com/pylp/pylp) for the
asyncio of Python 3.11+.

``asyncio.wait()`` refuses bare coroutines since Python 3.11, and pylp hands
it ``runner.future``, which is a ``Future`` for a task without dependencies
and a *coroutine* for a task with them (``Runner.start_deps``). The fix is
``asyncio.ensure_future(runner.future)``, which takes both: wrapping it in
``asyncio.create_task()`` instead -- what this script did before, and what
the ``sed`` of CLAUDE.md does -- breaks the plain ``Future`` case with
``TypeError: a coroutine was expected, got <Future ...>`` (seen on Python
3.13.5).

Patched, in the installed pylp:

* ``pylp/cli/run.py``: ``wait_and_quit`` (the tasks still running);
* ``pylp/lib/runner.py``: ``Runner.start_deps`` (the dependencies).

pylp also calls ``asyncio.get_event_loop()`` outside a running loop, after
creating its futures on that implicit loop: it warns on 3.12+ and will fail
on 3.14, and is left alone here (replacing the loop there orphans the
futures and hangs the run).

Idempotent: no-ops on an already-patched install, and repairs one patched
with ``create_task``.
"""
import importlib
import sys
from pathlib import Path

WAIT = "await asyncio.wait(map(lambda runner: {}, {}))"


def wait_patch(name):
    """``(old variants, new)`` of the ``asyncio.wait`` call over ``name``."""
    return ([WAIT.format('runner.future', name),
             WAIT.format('asyncio.create_task(runner.future)', name)],
            WAIT.format('asyncio.ensure_future(runner.future)', name))


PATCHES = {
    'pylp.cli.run': [wait_patch('running')],
    'pylp.lib.runner': [wait_patch('runners')],
}


def patch_module(module_name, patches):
    """0 when the module is (now) patched, 1 when a line was not found."""
    target = Path(importlib.import_module(module_name).__file__)
    src = original = target.read_text()
    for olds, new in patches:
        if new in src:
            continue
        found = next((old for old in olds if old in src), None)
        if found is None:
            print(f"patch_pylp: expected line not found in {target} -- "
                  "pylp version may have changed, patch manually",
                  file=sys.stderr)
            return 1
        src = src.replace(found, new)
    if src == original:
        print(f"pylp already patched: {target}")
    else:
        target.write_text(src)
        print(f"patched {target}")
    return 0


def main():
    try:
        importlib.import_module('pylp.cli.run')
    except ModuleNotFoundError:
        print(
            "patch_pylp: pylp is not installed -- run "
            "'pip install -r test_requirements.txt' first",
            file=sys.stderr,
        )
        return 1
    result = 0
    for module_name, patches in PATCHES.items():
        result |= patch_module(module_name, patches)
    return result


if __name__ == "__main__":
    sys.exit(main())
