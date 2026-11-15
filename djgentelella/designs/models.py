from django.conf import settings
from django.contrib.auth.models import Permission
from django.db import models
from django.db.models import F, Q
from django.utils.translation import gettext_lazy as _

from djgentelella.designs import format
from djgentelella.sites import site_q


def normalize_path(path):
    """``/ventas/clientes/`` -> ``ventas/clientes``: how a Page path is stored."""
    return '/'.join(part for part in str(path).split('/') if part)


class PageQuerySet(models.QuerySet):
    def for_site(self, site):
        """The pages of ``site`` and the global ones."""
        return self.filter(site_q(site))

    def find(self, path, site=None):
        """The page at ``path`` for ``site``: its own first, then the global one."""
        return (self.for_site(site).filter(path=normalize_path(path))
                .order_by(F('site').asc(nulls_last=True)).first())


class Page(models.Model):
    """A design document published as a page at ``designs/<path>``."""

    site = models.ForeignKey('sites.Site', null=True, blank=True,
                             on_delete=models.CASCADE, related_name='gtdesign_pages',
                             verbose_name=_('site'),
                             help_text=_('Empty: the page is served on every site '
                                         'that has none of its own at this path.'))
    path = models.CharField(_('path'), max_length=255,
                            help_text=_('Under designs/, without leading or '
                                        'trailing slash.'))
    title = models.CharField(_('title'), max_length=255, blank=True)
    document = models.JSONField(_('document'))
    schema_version = models.PositiveIntegerField(_('schema version'),
                                                 default=format.CURRENT)
    hash = models.CharField(_('hash'), max_length=64, editable=False, db_index=True)
    is_published = models.BooleanField(_('published'), default=False)
    permissions = models.ManyToManyField(
        Permission, blank=True, related_name='gtdesign_pages',
        verbose_name=_('permissions'),
        help_text=_('Needed to see the page, besides the meta.permissions of the '
                    'document.'))
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name='+',
                                   verbose_name=_('updated by'))

    objects = PageQuerySet.as_manager()

    class Meta:
        verbose_name = _('design page')
        verbose_name_plural = _('design pages')
        ordering = ['path']
        constraints = [
            models.UniqueConstraint(fields=['site', 'path'],
                                    name='gtdesigns_page_site_path'),
            # NULLs are distinct in a unique constraint: one global page per path.
            models.UniqueConstraint(fields=['path'], condition=Q(site__isnull=True),
                                    name='gtdesigns_page_global_path'),
        ]
        permissions = [
            ('publish_template',
             _('Can publish design pages whose html is a Django template')),
            ('publish_js', _('Can publish design pages with their own JavaScript')),
        ]

    def __str__(self):
        return '%s%s' % ('%s:' % self.site.domain if self.site_id else '', self.path)

    def save(self, *args, **kwargs):
        self.path = normalize_path(self.path)
        if isinstance(self.document, dict):
            meta = self.document.get('meta')
            if isinstance(meta, dict) and meta.get('title'):
                self.title = str(meta.get('title', ''))[:255]
            version = self.document.get('schema_version')
            if isinstance(version, int) and not isinstance(version, bool):
                self.schema_version = version
        self.hash = format.document_hash(self.document)
        super().save(*args, **kwargs)

    def required_permissions(self):
        """``app.codename`` of the page's own permissions (the M2M)."""
        return ['%s.%s' % pair for pair in self.permissions.values_list(
            'content_type__app_label', 'codename')]
