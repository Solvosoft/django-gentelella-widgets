"""``{% pwa_head %}``: the manifest tags and the service worker registration
of :mod:`djgentelella.pwa`, each behind its setting. ``base.html`` prints it
in its ``pwa_head`` block."""
from django import template
from django.template.loader import render_to_string

from djgentelella.pwa import conf
from djgentelella.pwa.manifest import build_manifest

register = template.Library()


@register.simple_tag(takes_context=True)
def pwa_head(context):
    manifest_on = conf.manifest_enabled()
    worker_on = conf.service_worker_enabled()
    if not manifest_on and not worker_on:
        return ''
    request = context.get('request')
    return render_to_string('gentelella/pwa/head.html', {
        'manifest_on': manifest_on,
        'worker_on': worker_on,
        'manifest': build_manifest(request) if manifest_on and request else None,
        'scope': conf.scope(),
    })
