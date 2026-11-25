"""Geocoders: from an address to points, for ``GeocodedAddressInput``.

Off by default. A project turns it on with the dotted path of a class::

    GT_GEOCODER = 'djgentelella.geocoding.NominatimGeocoder'
    GT_GEOCODER_OPTIONS = {'url': 'https://nominatim.example.org/search',
                           'user_agent': 'my-project/1.0 (admin@example.org)',
                           'countrycodes': 'cr,pa'}

``GT_GEOCODER_OPTIONS`` are the keyword arguments of the class. Any class
with a ``search(query, limit)`` that returns :class:`Place` objects works:
a commercial service, a local gazetteer, or a fake in tests. The browser
never calls the geocoder: it asks ``gtapis/geocode/`` (login required), so
the service, its key and its usage policy stay on the server.

``GT_GEOCODER`` can also name a function -- or be one -- that takes the
request and returns the geocoder for it, or ``None`` (none for that
request): a geocoder per Site, with the key of the service read from the
credentials of the Site, and no global state::

    def site_geocoder(request):
        key = credentials_of(get_current_site(request)).get('geocoder')
        return MyGeocoder(api_key=key) if key else None

    GT_GEOCODER = 'myproject.geocoding.site_geocoder'
"""

import json
from dataclasses import asdict, dataclass
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string


class GeocoderError(Exception):
    """The geocoder could not answer now (network, quota, bad reply)."""


@dataclass
class Place:
    label: str
    lat: float
    lng: float

    @property
    def point(self):
        """The ``"lat,lng"`` string of ``GTPointField``."""
        return '%.6f,%.6f' % (self.lat, self.lng)

    def as_dict(self):
        return {**asdict(self), 'point': self.point}


class Geocoder:
    """Base class: ``search`` returns at most ``limit`` places for ``query``."""

    def search(self, query, limit=5):
        raise NotImplementedError


class NominatimGeocoder(Geocoder):
    """OpenStreetMap's Nominatim, or any server with its API.

    The public instance allows one request per second and asks for a
    ``user_agent`` that identifies the application: for real traffic, run
    your own or use a paid service.

    ``extra_params`` are added to the query string of every search (the
    ``key`` of a compatible service such as LocationIQ, an ``email``,
    ``viewbox``...), ``extra_headers`` to its headers (an API key sent as a
    header); neither can replace ``q``, ``format`` or ``limit``.
    """

    #: What a search always sends itself.
    RESERVED_PARAMS = ('q', 'format', 'limit')

    def __init__(self, url='https://nominatim.openstreetmap.org/search',
                 user_agent='djgentelella', timeout=5, countrycodes=None,
                 language=None, extra_params=None, extra_headers=None):
        self.url = url
        self.user_agent = user_agent
        self.timeout = timeout
        self.countrycodes = countrycodes
        self.language = language
        self.extra_params = {name: value for name, value in
                             dict(extra_params or {}).items()
                             if name not in self.RESERVED_PARAMS}
        self.extra_headers = dict(extra_headers or {})

    def search(self, query, limit=5):
        params = dict(self.extra_params)
        params.update({'q': query, 'format': 'jsonv2', 'limit': limit})
        if self.countrycodes:
            params['countrycodes'] = self.countrycodes
        headers = dict(self.extra_headers)
        headers['User-Agent'] = self.user_agent
        if self.language:
            headers['Accept-Language'] = self.language
        request = Request('%s?%s' % (self.url, urlencode(params)), headers=headers)
        try:
            with urlopen(request, timeout=self.timeout) as response:
                rows = json.loads(response.read().decode('utf-8'))
        except (URLError, OSError, ValueError) as error:
            raise GeocoderError(str(error)) from error
        places = []
        for row in rows if isinstance(rows, list) else []:
            try:
                places.append(Place(str(row['display_name']), float(row['lat']),
                                    float(row['lon'])))
            except (KeyError, TypeError, ValueError):
                continue
        return places[:limit]


def geocoder_setting():
    """What ``GT_GEOCODER`` names: a :class:`Geocoder` class, a function
    ``request -> Geocoder | None``, or ``None`` when it is not set (the
    default). A dotted path that does not import is ``ImproperlyConfigured``.
    """
    value = getattr(settings, 'GT_GEOCODER', None)
    if not value:
        return None
    if isinstance(value, str):
        try:
            value = import_string(value)
        except ImportError as error:
            raise ImproperlyConfigured('GT_GEOCODER: %s' % error) from error
    if not callable(value):
        raise ImproperlyConfigured('GT_GEOCODER is neither a Geocoder class nor a '
                                   'function of the request: %r' % (value,))
    return value


def geocoder_configured():
    """Whether a geocoder is configured (``GT_GEOCODER``); with a function of
    the request, it may still give none for a request."""
    return geocoder_setting() is not None


def get_geocoder(request=None):
    """The geocoder for ``request``, or ``None`` when there is none (the
    default).

    A class in ``GT_GEOCODER`` is built with ``GT_GEOCODER_OPTIONS`` whatever
    the request; a function is called with ``request`` (``None`` when there
    is none) and its answer returned.
    """
    found = geocoder_setting()
    if found is None:
        return None
    if isinstance(found, type):
        return found(**getattr(settings, 'GT_GEOCODER_OPTIONS', {}))
    return found(request)
