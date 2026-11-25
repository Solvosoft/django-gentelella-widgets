"""Publishing a design document as a :class:`~djgentelella.designs.models.Page`.

What ``gtdesigns_publish`` and the admin go through: the document is upgraded
and resolved first, and nothing is saved while it has errors.
"""

import copy

from django.contrib.auth.models import Permission
from django.db import transaction
from django.db.models import Q
from django.utils.translation import gettext as _

from djgentelella.designs import engine, format
from djgentelella.designs.models import Page, normalize_path
from djgentelella.sites import resolve_site


def default_path(document):
    """Where a document is published unless told otherwise: its ``meta.url``."""
    return normalize_path(document['meta']['url'])


def validate(document, user=None, site=None, *, context=None):
    """The :class:`~djgentelella.designs.jsonschema.Error` list of a document,
    resolved with the trust ``user`` would give it as its publisher, for
    ``site`` (a Site, its id or ``None``): a flow or anything else that only
    exists in that Site is found.

    ``context`` is the :class:`~djgentelella.designs.components.ResolveContext`
    subclass it is resolved with; by default ``GT_DESIGNS_RESOLVE_CONTEXT``
    (:func:`~djgentelella.designs.components.default_context_class`), the
    project's rules wherever a page is published."""
    trusted_templates = trusted_js = False
    if user is not None:
        page = Page(document=document, updated_by=user)
        trusted_templates, trusted_js = engine.page_trust(page)
    _resolved, errors = engine.resolve(document, allow_templates=trusted_templates,
                                       allow_js=trusted_js, site=resolve_site(site),
                                       context=context)
    return errors


def _permissions_query(perms):
    query = Q(pk__in=[])
    for perm in perms:
        app_label, _dot, codename = perm.partition('.')
        query |= Q(content_type__app_label=app_label, codename=codename)
    return Permission.objects.filter(query)


def permission_objects(perms):
    return list(_permissions_query(perms))


def publish(document, *, site=None, path=None, user=None, published=True,
            context=None):
    """``(page, [])`` after saving the page, ``(None, errors)`` without saving.

    The page at ``(site, path)`` is replaced when it exists. Its permissions
    become the ``meta.permissions`` of the document. The document is validated
    for ``site``, so it may name what only exists there (a flow published in
    that Site), with ``context`` (see :func:`validate`).
    """
    try:
        document = format.upgrade(document)
    except format.UpgradeError as error:
        return None, [format.Error('$.schema_version', str(error))]
    errors = validate(document, user, site=site, context=context)
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


# -- a page as data ----------------------------------------------------------------

#: The keys of an exported page, besides which nothing is accepted.
PAGE_FIELDS = {'path': str, 'title': str, 'is_published': bool, 'document': dict,
               'permissions': list}


def export_page(page):
    """A :class:`~djgentelella.designs.models.Page` as data, without pks:
    ``path``, ``title``, ``is_published``, ``document`` and ``permissions``
    (``['app_label.codename', ...]``, those the page has now). The Site is not
    in it: :func:`import_page` is told where."""
    return {
        'path': page.path,
        'title': page.title,
        'is_published': page.is_published,
        'document': page.document,
        'permissions': sorted('%s.%s' % (perm.content_type.app_label, perm.codename)
                              for perm in page.permissions.select_related(
                                  'content_type')),
    }


def validate_page_data(data):
    """The :class:`~djgentelella.designs.jsonschema.Error` list of the shape
    of ``data`` (what :func:`export_page` gives); the document itself is
    validated when it is published."""
    if not isinstance(data, dict):
        return [format.Error('$', _('a page is an object'))]
    errors = [format.Error('$.' + name, _('unknown field'))
              for name in sorted(set(data) - set(PAGE_FIELDS))]
    for name, kind in PAGE_FIELDS.items():
        if name not in data:
            if name in ('path', 'document'):
                errors.append(format.Error('$.' + name, _('required')))
        elif not isinstance(data[name], kind):
            errors.append(format.Error('$.' + name, _('wrong type')))
    if isinstance(data.get('path'), str) and \
            normalize_path(data['path']) != data['path']:
        errors.append(format.Error('$.path', _(
            'a page path has no leading, trailing or double slashes')))
    if isinstance(data.get('title'), str) and len(data['title']) > 255:
        errors.append(format.Error('$.title', _('longer than %d characters') % 255))
    permissions = data.get('permissions')
    if isinstance(permissions, list):
        if not all(isinstance(label, str) and '.' in label for label in permissions):
            errors.append(format.Error('$.permissions',
                                       _('a list of "app_label.codename"')))
        else:
            found = {'%s.%s' % pair for pair in _permissions_query(
                permissions).values_list('content_type__app_label', 'codename')}
            errors.extend(format.Error('$.permissions', _('no permission %s') % label)
                          for label in permissions if label not in found)
    return errors


def import_page(data, *, site=None, user=None, context=None):
    """Publish the page ``data`` (the format of :func:`export_page`) in
    ``site`` with :func:`publish`, ``user`` as its publisher (whose trust the
    document gets): ``(page, [])`` once saved, ``(None, errors)`` -- nothing
    saved -- when the data or the document are not valid.

    The page at ``(site, path)`` is replaced when it exists. Its title is the
    data's; its permissions are the data's ``permissions`` when it has them,
    else the document's ``meta.permissions``. ``context`` as in
    :func:`validate`.
    """
    errors = validate_page_data(data)
    if errors:
        return None, errors
    with transaction.atomic():
        page, errors = publish(copy.deepcopy(data['document']), site=site,
                               path=data['path'], user=user,
                               published=data.get('is_published', True),
                               context=context)
        if errors:
            return None, errors
        if 'permissions' in data:
            page.permissions.set(permission_objects(data['permissions']))
        if 'title' in data and page.title != data['title']:
            # save() takes the title from meta.title: the data's wins.
            page.title = data['title']
            Page.objects.filter(pk=page.pk).update(title=data['title'])
    return page, []
