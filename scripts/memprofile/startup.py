"""Startup footprint of djgentelella, scenario by scenario.

Every scenario runs in a fresh interpreter, twice over:

* clean (``--repeat`` times, median kept): no tracemalloc, no hooks. RSS/USS
  and module counts come from here, since tracing inflates RSS.
* profiled (once): tracemalloc + ``ImportProfiler``, for per-module attribution.

Usage::

    python scripts/memprofile/startup.py [--repeat 3] [--only demo,minimal]
"""
import argparse
import ast
import gc
import json
import statistics
import subprocess
import sys
import tracemalloc
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from memprofile import _measure as m  # noqa: E402

OPTIONAL_APPS = [
    'djgentelella.blog',
    'djgentelella.async_notification',
    'djgentelella.datasources',
    'djgentelella.designs',
    'djgentelella.flows',
]

# name -> (settings module, environment)
SCENARIOS = {
    'baseline': ('memprofile.settings_minimal', {'MEMPROFILE_NO_GT': '1'}),
    'minimal': ('memprofile.settings_minimal', {}),
    **{
        '+' + app.split('.')[-1]: ('memprofile.settings_minimal',
                                   {'MEMPROFILE_APPS': app})
        for app in OPTIONAL_APPS
    },
    'all-optional': ('memprofile.settings_minimal',
                     {'MEMPROFILE_APPS': ','.join(OPTIONAL_APPS)}),
    'demo': ('demo.settings', {}),
}


# --------------------------------------------------------------- child side

def run_child(settings_module, profile):
    m.bootstrap(settings_module)
    profiler = None
    phases = [m.snapshot_process('python')]
    if profile:
        tracemalloc.start(1)
        profiler = m.ImportProfiler()
        profiler.install()

    import django  # noqa: PLC0415 -- the import is what is being measured
    phases.append(m.snapshot_process('import django'))
    django.setup()
    phases.append(m.snapshot_process('django.setup'))

    from django.conf import settings  # noqa: PLC0415 -- needs DJANGO_SETTINGS_MODULE
    from django.urls import get_resolver  # noqa: PLC0415 -- same
    __import__(settings.ROOT_URLCONF)
    get_resolver().url_patterns  # noqa: B018 -- forces the lazy URLconf
    gc.collect()
    phases.append(m.snapshot_process('urlconf'))

    out = {'phases': phases, 'apps': list(settings.INSTALLED_APPS)}
    if profiler:
        profiler.uninstall()
        out['modules'] = profiler.records
        out['traced_total'] = tracemalloc.get_traced_memory()[0]
    json.dump(out, sys.stdout)


# -------------------------------------------------------------- parent side

def spawn(settings_module, env_extra, profile):
    import os  # noqa: PLC0415 -- parent only
    env = dict(os.environ, **env_extra)
    env.pop('DJANGO_SETTINGS_MODULE', None)
    cmd = [sys.executable, '-I', __file__, '--child', settings_module]
    if profile:
        cmd.append('--profile')
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if proc.returncode:
        raise RuntimeError(f'{settings_module} {env_extra} failed:\n{proc.stderr}')
    return json.loads(proc.stdout)


def median_phases(runs):
    merged = []
    for i, phase in enumerate(runs[0]['phases']):
        row = {'phase': phase['phase']}
        for key in ('rss_kb', 'uss_kb', 'modules', 'gt_modules'):
            row[key] = int(statistics.median(r['phases'][i][key] for r in runs))
        merged.append(row)
    return merged


def static_imports():
    """Third-party packages imported by each djgentelella group, by placement.

    ``module`` = imported at module level (paid by everyone who imports that
    file), ``function`` = inside a function (paid on first call).
    """
    root = m.REPO / 'djgentelella'
    result = {}
    for path in root.rglob('*.py'):
        rel = path.relative_to(m.REPO).with_suffix('')
        if {'tests', 'migrations'} & set(rel.parts):
            continue
        modname = '.'.join(rel.parts).removesuffix('.__init__')
        try:
            tree = ast.parse(path.read_text(), str(path))
        except SyntaxError:
            continue
        toplevel = {id(n) for n in tree.body}
        # Imports guarded by `if`/`try` at module level are still module level.
        for node in tree.body:
            if isinstance(node, (ast.If, ast.Try)):
                toplevel |= {id(n) for n in ast.walk(node)}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module]
            else:
                continue
            where = 'module' if id(node) in toplevel else 'function'
            for name in names:
                top = m.top_package(name)
                if m.is_stdlib(top) or top in m.PROJECT_PREFIXES:
                    continue
                entry = result.setdefault(top, {'module': {}, 'function': {}})
                entry[where].setdefault(m.group_of(modname), set()).add(modname)
    return {top: {w: {g: sorted(v) for g, v in d.items()} for w, d in e.items()}
            for top, e in result.items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--child')
    parser.add_argument('--profile', action='store_true')
    parser.add_argument('--repeat', type=int, default=3)
    parser.add_argument('--only', help='comma separated scenario names')
    parser.add_argument('--out', default=str(m.OUT / 'startup.json'))
    args = parser.parse_args()

    if args.child:
        run_child(args.child, args.profile)
        return

    names = args.only.split(',') if args.only else list(SCENARIOS)
    data = {'python': sys.version.split()[0], 'scenarios': {},
            'static_imports': static_imports()}
    for name in names:
        settings_module, env = SCENARIOS[name]
        print(f'[startup] {name}: clean x{args.repeat}', file=sys.stderr)
        clean = [spawn(settings_module, env, False) for _ in range(args.repeat)]
        print(f'[startup] {name}: profiled', file=sys.stderr)
        prof = spawn(settings_module, env, True)
        data['scenarios'][name] = {
            'settings': settings_module, 'env': env, 'apps': clean[0]['apps'],
            'phases': median_phases(clean),
            'rss_runs_kb': [r['phases'][-1]['rss_kb'] for r in clean],
            'modules': prof['modules'], 'traced_total': prof['traced_total'],
        }
    m.write_json(args.out, data)
    print(f'[startup] wrote {args.out}', file=sys.stderr)


if __name__ == '__main__':
    main()
