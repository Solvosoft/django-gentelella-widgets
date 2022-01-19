from djgentelella.groute import register_lookups
from djgentelella.views.storymap import BaseStoryMapGPView, BaseStoryMapMBView


@register_lookups(prefix="gigapixel_storymap", basename="examplestorymapgp")
class GigaPixelStoryMapExample(BaseStoryMapGPView):
    def get_width(self):
        return 1000

    def get_height(self):
        return 1000

    def get_font_css(self):
        return ''

    def get_calculate_zoom(self):
        return False

    def get_storymap(self):
        return {
            'language': 'en',
            'map_type': 'zoomify',
            'map_as_image': True,
            'map_background_color': '#000000',
            'calculate_zoom': False,
            'zoomify': {
                'path': '',
                'width': 400,
                'height': 400,
                'tolerance': 0.8
            },
            'slides': [
                {
                    'type': 'overview',
                    'text': {
                        'headline': 'HEADLINE EXAMPLE',
                        'text': 'GigaPixel-StoryMap example'
                    }
                },
                {
                    'location': {
                        'lat': 1000.0,
                        'lon': 500.0
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
                        'lat': 800.0,
                        'lon': 300.0
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
                    'location': {
                        'lat': 2000.0,
                        'lon': 5000.0
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