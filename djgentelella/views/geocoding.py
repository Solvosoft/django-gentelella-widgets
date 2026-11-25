from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET

from djgentelella.geocoding import GeocoderError, get_geocoder

#: Longest query sent to the geocoder, and most places returned.
MAX_QUERY = 200
MAX_RESULTS = 10


@login_required
@require_GET
def geocode_view(request):
    """``{"results": [{"label", "lat", "lng", "point"}]}`` for ``?q=``.

    404 while ``GT_GEOCODER`` is not set (or its function gives no geocoder
    for this request), 400 without a query, 502 when the geocoder fails.
    """
    geocoder = get_geocoder(request)
    if geocoder is None:
        return JsonResponse({'error': _('There is no geocoder configured.')},
                            status=404)
    query = request.GET.get('q', '').strip()[:MAX_QUERY]
    if not query:
        return JsonResponse({'error': _('Write an address.')}, status=400)
    try:
        limit = min(max(int(request.GET.get('limit', 5)), 1), MAX_RESULTS)
    except ValueError:
        limit = 5
    try:
        places = geocoder.search(query, limit=limit)
    except GeocoderError:
        return JsonResponse({'error': _('The geocoder did not answer.')},
                            status=502)
    return JsonResponse({'results': [place.as_dict() for place in places[:limit]]})
