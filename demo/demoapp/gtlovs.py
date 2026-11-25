"""Cascading LOVs of the dynamic actions demo: country -> province -> canton.

Plain lists, to show that a LOV does not need a model; a queryset works the
same way.
"""

from djgentelella.lov import register_lov

COUNTRIES = [('cr', 'Costa Rica'), ('pa', 'Panamá')]

PROVINCES = {
    'cr': [('sj', 'San José'), ('al', 'Alajuela'), ('ca', 'Cartago')],
    'pa': [('pp', 'Panamá'), ('ch', 'Chiriquí')],
}

CANTONS = {
    'sj': [('sj-01', 'San José'), ('sj-02', 'Escazú'), ('sj-03', 'Desamparados')],
    'al': [('al-01', 'Alajuela'), ('al-02', 'San Ramón')],
    'ca': [('ca-01', 'Cartago'), ('ca-02', 'Paraíso')],
    'pp': [('pp-01', 'Panamá Centro'), ('pp-02', 'San Miguelito')],
    'ch': [('ch-01', 'David'), ('ch-02', 'Boquete')],
}


def _search(rows, q):
    q = (q or '').lower()
    return [row for row in rows if q in row[1].lower()]


@register_lov('demo_countries')
def countries(request, q=''):
    return _search(COUNTRIES, q)


@register_lov('demo_provinces', depends_on=['country'])
def provinces(request, country=None, q=''):
    return _search(PROVINCES.get(country, []), q)


@register_lov('demo_cantons', depends_on=['province'])
def cantons(request, province=None, q=''):
    return _search(CANTONS.get(province, []), q)


#: A list too long for a dropdown: the popup LOV of /formwidgets/.
PRODUCTS = [('p%03d' % number, 'Producto %03d' % number)
            for number in range(1, 251)]


@register_lov('demo_products', page_size=10)
def products(request, q=''):
    return _search(PRODUCTS, q)
