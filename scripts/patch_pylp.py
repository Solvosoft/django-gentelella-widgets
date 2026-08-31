#!/usr/bin/env python3
"""
Patch pylp 0.2.10's runner so asyncio.wait() receives Tasks, not bare
coroutines: some Python 3.11/3.12+ builds raise TypeError for the latter
(the exact cutoff moved around between patch releases), and there is no
upstream fix released (https://github.com/pylp/pylp, last release 0.2.10).
Wrapping in asyncio.create_task is a no-op on unaffected versions, so this
always applies the patch rather than guessing a version cutoff.

Idempotent: no-ops on an already-patched install.
"""
import sys
from pathlib import Path

OLD = "await asyncio.wait(map(lambda runner: runner.future, running))"
NEW = "await asyncio.wait(map(lambda runner: asyncio.create_task(runner.future), running))"


def main():
    try:
        import pylp.cli.run as _run_module
    except ModuleNotFoundError:
        print(
            "patch_pylp: pylp is not installed -- run "
            "'pip install -r test_requirements.txt' first",
            file=sys.stderr,
        )
        return 1

    target = Path(_run_module.__file__)
    src = target.read_text()

    if NEW in src:
        print(f"pylp already patched: {target}")
        return 0

    if OLD not in src:
        print(
            f"patch_pylp: expected line not found in {target} -- "
            "pylp version may have changed, patch manually",
            file=sys.stderr,
        )
        return 1

    target.write_text(src.replace(OLD, NEW))
    print(f"patched {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
