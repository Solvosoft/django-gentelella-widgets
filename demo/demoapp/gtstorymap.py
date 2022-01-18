from djgentelella.groute import register_lookups
from djgentelella.views.storymap import BaseStoryMapGPView, BaseStoryMapMBView


@register_lookups(prefix="storymap_gigapixel", basename="examplestorymapgp")
class StoryMapGigaPixelExample(BaseStoryMapGPView):
    def get_width(self):
        return 100

    def get_height(self):
        return 80

    def get_font_css(self):
        return ''

    def get_calculate_zoom(self):
        return False

    def get_storymap(self):
        return {
            'language': 'en',
            'map_type': 'zoomify',
            'map_as_image': True,
            'map_background_color': '#FFFFFF',
            'calculate_zoom': False,
            'zoomify': {
                'path': 'http://cdn.verite.co/maps/zoomify/seurat/',
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
                        'lat': 1000,
                        'lon': 1000
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