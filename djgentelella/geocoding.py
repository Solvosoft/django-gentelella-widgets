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
    """

    def __init__(self, url='https://nominatim.openstreetmap.org/search',
                 user_agent='djgentelella', timeout=5, countrycodes=None,
                 language=None):
        self.url = url
        self.user_agent = user_agent
        self.timeout = timeout
        self.countrycodes = countrycodes
        self.language = language

    def search(self, query, limit=5):
        params = {'q': query, 'format': 'jsonv2', 'limit': limit}
        if self.countrycodes:
            params['countrycodes'] = self.countrycodes
        headers = {'User-Agent': self.user_agent}
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


def get_geocoder():
    """The geocoder of ``GT_GEOCODER``, or None when there is none (default)."""
    path = getattr(settings, 'GT_GEOCODER', None)
    if not path:
        return None
    try:
        geocoder_class = import_string(path)
    except ImportError as error:
        raise ImproperlyConfigured('GT_GEOCODER: %s' % error) from error
    return geocoder_class(**getattr(settings, 'GT_GEOCODER_OPTIONS', {}))
