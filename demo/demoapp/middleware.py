"""The demo's language: Spanish unless the visitor chose another one.

Django's ``LocaleMiddleware`` would also follow the browser's
``Accept-Language``, and the demo (and its tests) is written to run in
Spanish. This one only honours the language cookie that ``set_language``
(``/i18n/setlang/``, the switcher of the top bar) writes.
"""

from django.conf import settings
from django.utils import translation


class LanguageCookieMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        code = request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME)
        if code not in dict(settings.LANGUAGES):
            return self.get_response(request)
        with translation.override(code):
            request.LANGUAGE_CODE = code
            response = self.get_response(request)
            response.headers.setdefault('Content-Language', code)
            return response
