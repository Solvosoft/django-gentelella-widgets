"""Turns ``out/startup.json`` and ``out/runtime.json`` into ``out/report.md``.

Usage::

    python scripts/memprofile/report.py [--startup F] [--runtime F] [--out F]
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from memprofile import _measure as m  # noqa: E402

# Modules that import a package only if it happens to be installed.
OPPORTUNISTIC_IMPORTERS = {
    'rest_framework.compat', 'django.contrib.admindocs.utils',
    'requests', 'requests.compat', 'requests.adapters', 'requests.packages',
    'requests.certs', 'urllib3.contrib.socks',
}


def mb(kb):
    return f'{kb / 1024:.1f}'


def kb(b):
    return f'{b / 1024:,.0f}'


def table(headers, rows):
    out = ['| ' + ' | '.join(headers) + ' |',
           '|' + '|'.join('---' for _ in headers) + '|']
    out += ['| ' + ' | '.join(str(c) for c in r) + ' |' for r in rows]
    return '\n'.join(out)


def group_costs(modules):
    groups = defaultdict(lambda: {'own_n': 0, 'own': 0, 'tp_n': 0, 'tp': 0,
                                  'std': 0, 'ms': 0.0, 'tp_pkgs': defaultdict(int)})
    for name, r in modules.items():
        g = groups[r['group']]
        g['ms'] += r['self_ms']
        if r['own']:
            g['own_n'] += 1
            g['own'] += r['self_bytes']
        elif r['stdlib']:
            g['std'] += r['self_bytes']
        else:
            g['tp_n'] += 1
            g['tp'] += r['self_bytes']
            g['tp_pkgs'][m.top_package(name)] += r['self_bytes']
    return groups


def startup_section(data):
    sc = data['scenarios']
    lines = ['## 1. Arranque: `django.setup()` + URLconf\n',
             f"Python {data['python']}. RSS/USS: mediana de los arranques limpios "
             '(sin tracemalloc). USS = memoria privada, lo que cuesta cada worker '
             'extra. "traced" = memoria Python asignada durante los imports '
             '(arranque perfilado).\n']
    base = sc.get('baseline', {}).get('phases', [{}])[-1]
    mini = sc.get('minimal', {}).get('phases', [{}])[-1]
    rows = []
    for name, s in sc.items():
        last = s['phases'][-1]
        d_base = (f"+{mb(last['rss_kb'] - base['rss_kb'])}" if base else '')
        d_min = (f"+{mb(last['rss_kb'] - mini['rss_kb'])}"
                 if mini and name.startswith('+') else '')
        rows.append([f'`{name}`', mb(last['rss_kb']), mb(last['uss_kb']), d_base,
                     d_min, last['modules'], last['gt_modules'],
                     mb(s['traced_total'] / 1024)])
    lines.append(table(['escenario', 'RSS MB', 'USS MB', 'Δ RSS vs baseline',
                        'Δ RSS vs minimal', 'módulos', 'de djgentelella',
                        'traced MB'], rows))

    if 'demo' in sc:
        lines.append('\n### Fases del demo\n')
        prev = None
        rows = []
        for p in sc['demo']['phases']:
            delta = f"+{mb(p['rss_kb'] - prev['rss_kb'])}" if prev else ''
            rows.append([p['phase'], mb(p['rss_kb']), delta, p['modules']])
            prev = p
        lines.append(table(['fase', 'RSS MB', 'Δ', 'módulos'], rows))

    for name in ('minimal', 'demo'):
        if name not in sc:
            continue
        groups = group_costs(sc[name]['modules'])
        rows = []
        ordered = sorted(groups.items(), key=lambda kv: -(kv[1]['own'] + kv[1]['tp']))
        for g, c in ordered[:30]:
            top = sorted(c['tp_pkgs'].items(), key=lambda kv: -kv[1])[:4]
            rows.append([f'`{g}`', c['own_n'], kb(c['own']), c['tp_n'], kb(c['tp']),
                         kb(c['std']), f"{c['ms']:.0f}",
                         ', '.join(f'{p} {kb(b)}' for p, b in top)])
        lines.append(f'\n### Quién carga qué — escenario `{name}`\n')
        lines.append('Cada módulo de terceros se le cobra al frame de proyecto más '
                     'cercano en la pila de llamadas que lo importó primero. '
                     '`(framework)` = lo cargó Django sin pasar por código del '
                     'proyecto.\n')
        lines.append(table(['grupo', 'módulos propios', 'KB propios',
                            'módulos 3ros arrastrados', 'KB 3ros', 'KB stdlib',
                            'ms import', 'principales 3ros (KB)'], rows))

    if 'demo' in sc:
        mods = sc['demo']['modules']
        own = sorted(((n, r) for n, r in mods.items() if n.startswith('djgentelella')),
                     key=lambda kv: -kv[1]['self_bytes'])[:20]
        lines.append('\n### Los 20 módulos de djgentelella más pesados (demo)\n')
        lines.append(table(['módulo', 'KB propios', 'ms'],
                           [[f'`{n}`', kb(r['self_bytes']), f"{r['self_ms']:.1f}"]
                            for n, r in own]))
        lines.append(third_party_section(mods, data['static_imports']))
    return '\n'.join(lines)


def third_party_section(mods, static):
    pkgs = defaultdict(lambda: {'bytes': 0, 'n': 0, 'blame': defaultdict(int),
                                'entry': set()})
    for name, r in mods.items():
        if r['own'] or r['stdlib']:
            continue
        p = pkgs[m.top_package(name)]
        p['bytes'] += r['self_bytes']
        p['n'] += 1
        p['blame'][r['group']] += r['self_bytes']
        importer = r.get('importer') or '?'
        if m.top_package(importer) != m.top_package(name):
            p['entry'].add(importer)
    rows = []
    for pkg, p in sorted(pkgs.items(), key=lambda kv: -kv[1]['bytes'])[:30]:
        blame = sorted(p['blame'].items(), key=lambda kv: -kv[1])[:3]
        st = static.get(pkg, {'module': {}, 'function': {}})
        entry = sorted(p['entry'])
        more = f' (+{len(entry) - 3})' if len(entry) > 3 else ''
        entry = ', '.join(entry[:3]) + more
        rows.append([f'`{pkg}`', kb(p['bytes']), p['n'], entry,
                     ', '.join(f'{g}' for g, _ in blame),
                     ', '.join(sorted(st['module'])) or '—',
                     ', '.join(sorted(st['function'])) or '—'])
    optional = {pkg: p for pkg, p in pkgs.items()
                if p['entry'] and p['entry'] <= OPPORTUNISTIC_IMPORTERS}
    note = ''
    if optional:
        total = sum(p['bytes'] for p in optional.values())
        note = ('\n\n**Cargados solo porque están instalados en este entorno** '
                f'({kb(total)} KB): {", ".join(f"`{k}`" for k in sorted(optional))}. '
                'Los importa DRF (`rest_framework.compat`) o Django (`admindocs`, vía '
                '`rest_framework.schemas`) si encuentra el paquete; ningún archivo de '
                'djgentelella los pide. En un entorno de producción sin ellos, no '
                'cuestan nada. `requests` es la excepción si se usa `[firmador]` o '
                '`[asr-remote]`.')
    return ('\n### Dependencias de terceros cargadas en el demo\n\n'
            '"Importado a nivel de módulo por": grupos de djgentelella con un '
            '`import` de ese paquete fuera de funciones (análisis estático). Un '
            'paquete pesado que solo importa un grupo a nivel de módulo es '
            'candidato a import perezoso.\n\n'
            + table(['paquete', 'KB', 'módulos', 'importador directo',
                     'cargado primero por (proyecto)',
                     'importado a nivel de módulo por', 'importado en funciones por'],
                    rows) + note)


def runtime_section(data):
    block = data['block']
    lines = ['\n## 2. En ejecución: requests sobre el demo\n',
             f"Peticiones directas a un `WSGIHandler` con sesión de superusuario. Cada "
             f"URL: {data['warmup']} peticiones de calentamiento sin trazar y luego "
             f"tres bloques de {block} peticiones. Django y CPython llenan cachés "
             'acotadas en las primeras decenas de peticiones, así que una URL se marca '
             f"solo si crece más de {data['leak_bytes'] // 1024} KB en el bloque 2 "
             '**y** en el 3. RSS inflado por tracemalloc a partir de la fase '
             '`blocks`.\n']
    lines.append(table(['fase', 'RSS MB', 'módulos'],
                       [[p['phase'], mb(p['rss_kb']), p['modules']]
                        for p in data['phases']]))

    statuses = data['statuses']
    bad = defaultdict(list)
    for url, st in statuses.items():
        if st != 200:
            bad[st].append(url)
    rest = '; '.join(f'{st}: {len(u)}' for st, u in sorted(bad.items()))
    lines.append(f"\n{len(statuses)} URLs sin parámetros descubiertas, "
                 f"{len(data['per_url'])} respondieron 200 y se midieron. "
                 f"El resto: {rest or 'ninguno'}.\n")
    if 500 in bad:
        lines.append('URLs con 500 (no se midieron): '
                     + ', '.join(f'`{u}`' for u in bad[500]) + '\n')

    flagged = [r for r in data['per_url'] if r['flagged']]
    lines.append('\n### URLs que siguen creciendo\n')
    if not flagged:
        lines.append('Ninguna.')
    for r in flagged:
        lines.append(f"\n#### `{r['url']}`\n\nBloques 1/2/3/4: "
                     + ' / '.join(kb(r[f'block{n}']) for n in (1, 2, 3, 4))
                     + f" KB ({r['block3'] / block / 1024:.1f} KB por petición en el "
                     'bloque 3).\n')
        lines.append(table(['ubicación (frame de proyecto más cercano)', 'KB',
                            'bloques'],
                           [[f"`{g['where']}`", kb(g['size_diff']), g['count_diff']]
                            for g in r['growth']]))

    lines.append('\n### Top 15 por crecimiento en bloques 2 + 3\n')
    top = sorted(data['per_url'], key=lambda r: -(r['block2'] + r['block3']))[:15]
    lines.append(table(['URL', 'bloque 1 KB', 'bloque 2 KB', 'bloque 3 KB',
                        'ms/petición (sin trazar)'],
                       [[f"`{r['url']}`", kb(r['block1']), kb(r['block2']),
                         kb(r['block3']), r['ms']] for r in top]))

    lines.append('\n### Las 10 URLs más lentas (sin trazar)\n')
    slow = sorted(data['per_url'], key=lambda r: -r['ms'])[:10]
    lines.append(table(['URL', 'ms/petición'],
                       [[f"`{r['url']}`", r['ms']] for r in slow]))

    ch = data['containers_changed']
    lines.append('\n### Contenedores de módulo y `lru_cache` que cambiaron de tamaño\n')
    if ch:
        ordered = sorted(ch.items(),
                         key=lambda kv: -(kv[1]['size'] - (kv[1]['before'] or 0)))
        lines.append(table(['objeto', 'tipo', 'antes', 'después'],
                           [[f'`{k}`', v['kind'], v['before'], v['size']]
                            for k, v in ordered]))
    else:
        lines.append('Ninguno.')
    lines.append('\n### `lru_cache` del proyecto\n')
    lines.append(table(['función', 'tamaño', 'maxsize'],
                       [[f'`{k}`', v['size'], v['maxsize']]
                        for k, v in sorted(data['lru_caches'].items())]))
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--startup', default=str(m.OUT / 'startup.json'))
    parser.add_argument('--runtime', default=str(m.OUT / 'runtime.json'))
    parser.add_argument('--out', default=str(m.OUT / 'report.md'))
    args = parser.parse_args()

    parts = ['# Uso de memoria de djgentelella\n']
    for path, section in ((args.startup, startup_section),
                          (args.runtime, runtime_section)):
        if Path(path).exists():
            parts.append(section(json.loads(Path(path).read_text())))
        else:
            parts.append(f'\n_(sin datos: falta `{path}`)_\n')
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text('\n'.join(parts) + '\n')
    print(f'[report] wrote {args.out}', file=sys.stderr)


if __name__ == '__main__':
    main()
