from django import forms
from rest_framework.reverse import reverse_lazy

from djgentelella.forms.forms import GTForm
from djgentelella.widgets.storymap import GigaPixelStoryMapInput, MapBasedStoryMapInput


class GigapixelForm(GTForm):
    gigapixel_storymap_options = {
        "map_type": "zoomify",
        "map_background_color": "#333",
        "map_as_image": True,
        "calculate_zoom": False,
        "zoomify": {
            "path": "http://cdn.verite.co/maps/zoomify/seurat/",
            "width": 30000,
            "height": 19970,
            "tolerance": 0.9,
            "attribution": "<a href='http://www.google.com/culturalinstitute/asset-viewer/a-sunday-on-la-grande-jatte-1884/twGyqq52R-lYpA?projectId=art-project' target='_blank'>Google Art Project</a>"
        }
    }
    gigapixel_storymap = forms.CharField(widget=GigaPixelStoryMapInput(
        attrs={"data-url": reverse_lazy('examplestorymapgp-list'), "storymap_options": gigapixel_storymap_options}))


class MapbasedForm(GTForm):
    mapbased_storymap = forms.CharField(widget=MapBasedStoryMapInput(
        attrs={"data-url": reverse_lazy('examplestorymapmb-list')}))