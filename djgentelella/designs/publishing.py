"""Publishing a design document as a :class:`~djgentelella.designs.models.Page`.

What ``gtdesigns_publish`` and the admin go through: the document is upgraded
and resolved first, and nothing is saved while it has errors.
"""

from django.contrib.auth.models import Permission
from django.db import transaction
from django.db.models import Q

from djgentelella.designs import engine, format
from djgentelella.designs.models import Page, normalize_path


def default_path(document):
    """Where a document is published unless told otherwise: its ``meta.url``."""
    return normalize_path(document['meta']['url'])


def validate(document, user=None):
    """The :class:`~djgentelella.designs.jsonschema.Error` list of a document,
    resolved with the trust ``user`` would give it as its publisher."""
    trusted_templates = trusted_js = False
    if user is not None:
        page = Page(document=document, updated_by=user)
        trusted_templates, trusted_js = engine.page_trust(page)
    _resolved, errors = engine.resolve(document, allow_templates=trusted_templates,
                                       allow_js=trusted_js)
    return errors


def permission_objects(perms):
    query = Q(pk__in=[])
    for perm in perms:
        app_label, _dot, codename = perm.partition('.')
        query |= Q(content_type__app_label=app_label, codename=codename)
    return list(Permission.objects.filter(query))


def publish(document, *, site=None, path=None, user=None, published=True):
    """``(page, [])`` after saving the page, ``(None, errors)`` without saving.

    The page at ``(site, path)`` is replaced when it exists. Its permissions
    become the ``meta.permissions`` of the document.
    """
    try:
        document = format.upgrade(document)
    except format.UpgradeError as error:
        return None, [format.Error('$.schema_version', str(error))]
    errors = validate(document, user)
    if errors:
        return None, errors
    path = normalize_path(path) if path else default_path(document)
    with transaction.atomic():
        page = Page.objects.filter(site=site, path=path).first() or Page(
            site=site, path=path)
        page.document = document
        page.is_published = published
        page.updated_by = user
        page.save()
        page.permissions.set(permission_objects(format.view_permissions(document)))
    return page, []
