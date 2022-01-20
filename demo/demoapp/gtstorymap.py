from djgentelella.groute import register_lookups
from djgentelella.views.storymap import BaseStoryMapGPView, BaseStoryMapMBView


@register_lookups(prefix="gigapixel_storymap", basename="examplestorymapgp")
class GigaPixelStoryMapExample(BaseStoryMapGPView):
    def get_width(self):
        return 1000

    def get_height(self):
        return 1000

    def get_font_css(self):
        return 'stock:opensans-gentiumbook'

    def get_calculate_zoom(self):
        return False

    def get_storymap(self):
        return {
            'language': 'en',
            'map_type': 'zoomify',
            'map_as_image': True,
            'map_background_color': '',
            'calculate_zoom': False,
            'zoomify': {
                'path': 'http://gigapixel.knightlab.com/seurat/',
                'width': 30000,
                'height': 19970,
                'tolerance': 0.9
            },
            'slides': [
                {
                    'type': 'overview',
                    'location': {
                        'icon': 'http://maps.gstatic.com/intl/en_us/mapfiles/ms/micons/blue-pushpin.png',
                        'line': True,
                    },
                    'text': {
                        'headline': 'HEADLINE EXAMPLE',
                        'text': 'GigaPixel-StoryMap example'
                    }
                },
                {
                    'location': {
                        'icon': 'http://maps.gstatic.com/intl/en_us/mapfiles/ms/micons/blue-pushpin.png',
                        'line': True,
                        'lat': 75.71,
                        'lon': -132.18
                    },
                    'text': {
                        'headline': 'FIRST PAGE',
                        'text': 'GigaPixel-StoryMap example'
                    },
                    'media': {
                        'url': 'https://m.media-amazon.com/images/M/MV5BMTJiMzgwZTktYzZhZC00YzhhLWEzZDUtMGM2NTE4MzQ4NGFmXkEyXkFqcGdeQWpybA@@._V1_QL75_UX500_CR0,0,500,281_.jpg',
                        'caption': 'Breaking Bad review',
                        'credit': 'Vince Gilligan',
                    }
                },
                {
                    'location': {
                        'icon': 'http://maps.gstatic.com/intl/en_us/mapfiles/ms/micons/blue-pushpin.png',
                        'line': True,
                        'lat': 77.62,
                        'lon': -20.47
                    },
                    'text': {
                        'headline': 'FIRST PAGE',
                        'text': 'GigaPixel-StoryMap example'
                    },
                    'media': {
                        'url': 'https://m.media-amazon.com/images/M/MV5BMTJiMzgwZTktYzZhZC00YzhhLWEzZDUtMGM2NTE4MzQ4NGFmXkEyXkFqcGdeQWpybA@@._V1_QL75_UX500_CR0,0,500,281_.jpg',
                        'caption': 'Breaking Bad review',
                        'credit': 'Vince Gilligan',
                    }
                }
            ]
        }


@register_lookups(prefix="mapbased_storymap", basename="examplestorymapmb")
class MapBasedStoryMapExample(BaseStoryMapMBView):
    def get_width(self):
        return 1000

    def get_height(self):
        return 1000

    def get_font_css(self):
        return ''

    def get_calculate_zoom(self):
        return True

    def get_storymap(self):
        return {
            'language': 'en',
            'map_type': 'stamen:toner-lite',
            'map_as_image': False,
            'map_subdomains': '',
            'slides': [
                {
                    'type': 'overview',
                    'text': {
                        'headline': 'HEADLINE EXAMPLE',
                        'text': 'MapBased-StoryMap example'
                    }
                },
                {
                    'type': '',
                    'location': {
                        'lat': 37.2,
                        'lon': -122.3
                    },
                    'text': {
                        'headline': 'FIRST PAGE',
                        'text': 'MapBased-StoryMap example'
                    },
                    'media': {
                        'url': 'https://m.media-amazon.com/images/M/MV5BMTJiMzgwZTktYzZhZC00YzhhLWEzZDUtMGM2NTE4MzQ4NGFmXkEyXkFqcGdeQWpybA@@._V1_QL75_UX500_CR0,0,500,281_.jpg',
                        'caption': 'Breaking Bad review',
                        'credit': 'Vince Gilligan',
                    }
                }
            ]
        }