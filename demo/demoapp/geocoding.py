"""An offline geocoder for the demo (``GT_GEOCODER``): a few places of Costa
Rica and Panama, so /formwidgets/ and its tests never touch the network."""

import unicodedata

from djgentelella.geocoding import Geocoder, Place

PLACES = [
    Place('San José, Costa Rica', 9.932700, -84.087500),
    Place('Heredia, Costa Rica', 9.998200, -84.116500),
    Place('Cartago, Costa Rica', 9.864700, -83.919400),
    Place('Alajuela, Costa Rica', 10.016300, -84.211600),
    Place('Ciudad de Panamá, Panamá', 8.983300, -79.516700),
    Place('David, Chiriquí, Panamá', 8.427300, -82.430800),
]


def plain(text):
    """Lower case without accents: 'san jose' finds San José."""
    text = unicodedata.normalize('NFKD', text.lower())
    return ''.join(char for char in text if not unicodedata.combining(char))


class DemoGeocoder(Geocoder):
    def search(self, query, limit=5):
        words = plain(query).replace(',', ' ').split()
        return [place for place in PLACES
                if all(word in plain(place.label) for word in words)][:limit]
