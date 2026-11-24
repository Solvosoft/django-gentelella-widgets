"""Memory while serving requests: does anything keep growing?

1. Builds a throwaway demo database (migrate + createdemo + demomenu) once.
2. In a fresh interpreter, opens a superuser session with ``django.test.Client``
   and then sends every request straight to a ``WSGIHandler``, like a real
   worker. (The Client itself disconnects and reconnects
   ``close_old_connections`` on every request, and each ``connect()`` leaves a
   ``weakref.finalize`` behind: growth that would be the Client's own.)
3. Discovers every URL without parameters, minus the excluded ones.
   Warm-up, untraced: each URL ``--warmup`` times; only those answering 200
   go on.
4. Per URL, three blocks of ``--block`` requests traced with one frame
   (cheap), ``gc.collect()`` around each. Django and CPython fill bounded
   caches during the first few dozen requests (compiled SQL, the type
   attribute cache...), so a URL is flagged only when it grows in blocks 2
   *and* 3: a leak or a cache without a bound.
5. Each flagged URL runs one more block traced with ``--frames`` frames; the
   diff is located at the nearest djgentelella/demo frame.
6. Every module-level dict/list/set and ``lru_cache`` of the project whose
   size changed during the run.

Usage::

    python scripts/memprofile/runtime.py [--block 20] [--rebuild] [--match flows]
"""
import argparse
import gc
import os
import re
import subprocess
import sys
import time
import tracemalloc
from pathlib import Path
from wsgiref.util import setup_testing_defaults

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from memprofile import _measure as m  # noqa: E402

SETTINGS = 'memprofile.settings_runtime'
DB = m.OUT / 'runtime' / 'runtime.sqlite3'
EXCLUDE = re.compile(
    r'logout|delete|remove|upload|voice|sign|transcribe|media/|static/'
    r'|^/admin/|password_reset|unsubscribe|process|send|export',
    re.I)
REGEX_META = re.compile(r'[\[\]()*+?{}|]')
LEAK_BYTES = 4 * 1024  # growth per block, in blocks 2 and 3, worth flagging


# ------------------------------------------------------------ database

def build_db(rebuild):
    if DB.exists() and not rebuild:
        return
    DB.parent.mkdir(parents=True, exist_ok=True)
    for p in DB.parent.glob('runtime.sqlite3*'):
        p.unlink()
    env = dict(os.environ, MEMPROFILE_DB=str(DB),
               PYTHONPATH=os.pathsep.join([str(m.SCRIPTS), str(m.REPO)]))
    env.pop('DJANGO_SETTINGS_MODULE', None)
    steps = [['migrate', '--noinput'], ['createdemo'], ['demomenu'],
             ['shell', '-c',
              'from django.contrib.auth.models import User;'
              "User.objects.filter(username='memprofile').exists() or "
              "User.objects.create_superuser('memprofile', 'm@example.com', 'x')"]]
    for step in steps:
        print(f'[runtime] manage.py {step[0]}', file=sys.stderr)
        subprocess.run([sys.executable, 'manage.py', *step, f'--settings={SETTINGS}'],
                       cwd=m.DEMO, env=env, check=True,
                       stdout=subprocess.DEVNULL)


# ------------------------------------------------------------ child side

def discover_urls(patterns=None, prefix=''):
    from django.urls import URLPattern, URLResolver, get_resolver  # noqa: PLC0415 -- after setup
    if patterns is None:
        patterns = get_resolver().url_patterns
    found = []
    for p in patterns:
        route = getattr(p.pattern, '_route', None)
        if route is None:
            route = p.pattern._regex.lstrip('^').rstrip('$')
            if p.pattern.regex.groups or REGEX_META.search(route.replace('\\.', '')):
                continue
            route = re.sub(r'\\(.)', r'\1', route)
        elif '<' in route:
            continue
        path = prefix + route
        if isinstance(p, URLResolver):
            found += discover_urls(p.url_patterns, path)
        elif isinstance(p, URLPattern):
            found.append('/' + path)
    return sorted({u for u in found if not EXCLUDE.search(u)})


def project_containers():
    """Size of every module-level container and lru_cache of the project."""
    sizes = {}
    for name, mod in list(sys.modules.items()):
        if mod is None or not m.is_project(name) or name.startswith('memprofile'):
            continue
        for attr, val in list(vars(mod).items()):
            if attr.startswith('__'):
                continue
            key = f'{name}.{attr}'
            if hasattr(val, 'cache_info') and getattr(val, '__module__', '') == name:
                info = val.cache_info()
                sizes[key] = {'kind': 'lru_cache', 'size': info.currsize,
                              'maxsize': info.maxsize}
            elif type(val) in (dict, list, set):
                sizes[key] = {'kind': type(val).__name__, 'size': len(val)}
    return sizes


def project_frame(traceback):
    """Most recent frame inside djgentelella or the demo, else the newest one."""
    repo, own = str(m.REPO), str(m.SCRIPTS / 'memprofile')
    for frame in reversed(traceback):  # oldest first, so newest first here
        if frame.filename.startswith(repo) and not frame.filename.startswith(own):
            return f'{os.path.relpath(frame.filename, repo)}:{frame.lineno}'
    frame = traceback[-1]
    return f'{frame.filename}:{frame.lineno}'


def locate_growth(snap_a, snap_b, limit=10):
    # Newest frame only: drops what this script allocates (its own rows).
    filters = [tracemalloc.Filter(False, tracemalloc.__file__),
               tracemalloc.Filter(False, '<frozen importlib._bootstrap*>'),
               tracemalloc.Filter(False, str(m.SCRIPTS / 'memprofile' / '*'))]
    diff = snap_b.filter_traces(filters).compare_to(
        snap_a.filter_traces(filters), 'traceback')
    growth = {}
    for stat in diff:
        if stat.size_diff <= 0:
            continue
        entry = growth.setdefault(project_frame(stat.traceback),
                                  {'size_diff': 0, 'count_diff': 0})
        entry['size_diff'] += stat.size_diff
        entry['count_diff'] += stat.count_diff
    return sorted(({'where': k, **v} for k, v in growth.items()),
                  key=lambda r: -r['size_diff'])[:limit]


def make_client():
    from django.conf import settings  # noqa: PLC0415 -- after setup
    from django.contrib.auth.models import User  # noqa: PLC0415 -- after setup
    from django.core.handlers.wsgi import WSGIHandler  # noqa: PLC0415 -- after setup
    from django.test import Client  # noqa: PLC0415 -- after setup

    login = Client()
    login.force_login(User.objects.get(username='memprofile'))
    cookie = f'{settings.SESSION_COOKIE_NAME}={login.session.session_key}'
    handler = WSGIHandler()

    def get(url):
        environ = {}
        setup_testing_defaults(environ)
        environ.update(PATH_INFO=url, HTTP_HOST='testserver',
                       SERVER_NAME='testserver', HTTP_COOKIE=cookie)
        status = []
        t0 = time.perf_counter()
        resp = handler(environ, lambda st, headers, exc=None: status.append(st))
        for _ in resp:
            pass
        resp.close()
        return int(status[0].split()[0]), time.perf_counter() - t0
    return get


def traced_block(get, url, block):
    gc.collect()
    mem0, rss0 = tracemalloc.get_traced_memory()[0], m.rss_kb()
    for _ in range(block):
        get(url)
    gc.collect()
    return tracemalloc.get_traced_memory()[0] - mem0, m.rss_kb() - rss0


def run_child(args):
    m.bootstrap(SETTINGS)
    os.environ['MEMPROFILE_DB'] = str(DB)
    import django  # noqa: PLC0415 -- after bootstrap
    django.setup()
    phases = [m.snapshot_process('django.setup')]
    get = make_client()
    urls = [u for u in discover_urls() if not args.match or re.search(args.match, u)]

    print(f'[runtime] warm-up of {len(urls)} URLs', file=sys.stderr, flush=True)
    statuses, warm_ms = {}, {}
    for url in urls:
        for _ in range(args.warmup):
            statuses[url], secs = get(url)
        warm_ms[url] = round(secs * 1000, 1)
    ok = [u for u in urls if statuses[u] == 200]
    gc.collect()
    phases.append(m.snapshot_process('warm-up'))
    containers_a = project_containers()
    print(f'[runtime] {len(ok)}/{len(urls)} URLs answer 200', file=sys.stderr)

    tracemalloc.start(1)
    per_url = []
    for i, url in enumerate(ok, 1):
        if i % 10 == 0:
            print(f'[runtime] {i}/{len(ok)}', file=sys.stderr, flush=True)
        row = {'url': url, 'ms': warm_ms[url]}
        for n in (1, 2, 3):
            row[f'block{n}'], row[f'block{n}_rss_kb'] = traced_block(get, url,
                                                                     args.block)
        row['flagged'] = min(row['block2'], row['block3']) > LEAK_BYTES
        per_url.append(row)
    tracemalloc.stop()
    gc.collect()
    phases.append(m.snapshot_process('blocks'))

    flagged = [r for r in per_url if r['flagged']]
    print(f'[runtime] {len(flagged)} URLs keep growing; locating',
          file=sys.stderr, flush=True)
    for row in flagged:
        tracemalloc.start(args.frames)
        gc.collect()
        snap_a = tracemalloc.take_snapshot()
        row['block4'] = traced_block(get, row['url'], args.block)[0]
        snap_b = tracemalloc.take_snapshot()
        tracemalloc.stop()
        row['growth'] = locate_growth(snap_a, snap_b)

    containers_b = project_containers()
    changed = {k: {'before': containers_a.get(k, {}).get('size'), **v}
               for k, v in containers_b.items()
               if containers_a.get(k, {}).get('size') != v['size']}
    m.write_json(args.out, {
        'block': args.block, 'warmup': args.warmup, 'leak_bytes': LEAK_BYTES,
        'phases': phases, 'statuses': statuses, 'per_url': per_url,
        'containers_changed': changed,
        'lru_caches': {k: v for k, v in containers_b.items()
                       if v['kind'] == 'lru_cache'},
    })


# ----------------------------------------------------------- parent side

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--child', action='store_true')
    parser.add_argument('--block', type=int, default=20,
                        help='requests per measuring block (three per URL)')
    parser.add_argument('--warmup', type=int, default=3)
    parser.add_argument('--match', help='only URLs matching this regex')
    parser.add_argument('--frames', type=int, default=25,
                        help='traceback depth to locate the growth of flagged URLs')
    parser.add_argument('--rebuild', action='store_true')
    parser.add_argument('--out', default=str(m.OUT / 'runtime.json'))
    args = parser.parse_args()

    if args.child:
        run_child(args)
        return

    build_db(args.rebuild)
    out = str(Path(args.out).resolve())  # the child runs from demo/
    cmd = [sys.executable, '-I', __file__, '--child', '--block', str(args.block),
           '--warmup', str(args.warmup), '--frames', str(args.frames), '--out', out]
    if args.match:
        cmd += ['--match', args.match]
    print('[runtime] serving requests', file=sys.stderr)
    proc = subprocess.run(cmd, env=dict(os.environ, MEMPROFILE_DB=str(DB)))
    if proc.returncode:
        sys.exit(f'[runtime] child failed with {proc.returncode}')
    print(f'[runtime] wrote {out}', file=sys.stderr)


if __name__ == '__main__':
    main()
