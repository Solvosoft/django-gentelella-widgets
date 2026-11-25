import logging

from django.conf import settings
from django.contrib.auth.models import Permission
from django.core.cache import DEFAULT_CACHE_ALIAS, cache, caches
from django.core.exceptions import ValidationError
from django.core.cache.backends.db import DatabaseCache
from django.db import DatabaseError, models, router, transaction
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _
from tree_queries.models import TreeNode
from tree_queries.query import TreeQuerySet

from djgentelella.chunked_upload.models import AbstractChunkedUpload
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from .models_manager import ObjectManager, AllObjectsManager, DeletedObjectsManager
from djgentelella.settings import USER_MODEL_BASE
from djgentelella.history.utils import add_log, ADDITION
from djgentelella.menu import is_menu_widget
from djgentelella.sites import site_pk

logger = logging.getLogger(__name__)


class GentelellaSettings(models.Model):
    """
    Permite personalizar el sitio, se usa para modificar configuraciones,
    temas etc.
    """

    key = models.CharField(max_length=100)
    value = models.CharField(max_length=500)
    # NULL is the global value; a Site overrides it for that Site.
    site = models.ForeignKey(
        'sites.Site',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='gentelella_settings',
        verbose_name=_('Site'),
        help_text=_('Empty: the value is global, for every site.'),
    )

    class Meta:
        unique_together = (('key', 'site'),)
        constraints = [
            # unique_together does not cover the global rows: NULLs never
            # collide in a unique index, so (key, NULL) needs its own.
            models.UniqueConstraint(
                fields=['key'],
                condition=models.Q(site__isnull=True),
                name='djgentelella_settings_unique_global_key',
            ),
        ]

    def __str__(self):
        if self.site_id:
            return '%s (%s)' % (self.key, self.site)
        return self.key


def settings_cache_key(key, site=None):
    """Cache key of the setting ``key`` in one scope: ``(key, site_id)``.

    The global scope keeps the bare ``key`` it always had, so whatever already
    clears it by name (``clean_cache([key])``) still works.
    """
    site_id = site_pk(site)
    if site_id is None:
        return key
    return 'gtsettings:%s:%s' % (site_id, key)


# Where a row was cached before a save that moves it: a save can change the
# key or the Site of a row, and its old scope must be forgotten as well.
_PREVIOUS_SCOPE_ATTR = '_gt_previous_cache_key'


@receiver(pre_save, sender=GentelellaSettings)
def _remember_cached_setting(sender, instance, **kwargs):
    previous = None
    if instance.pk is not None:
        previous = sender._default_manager.filter(pk=instance.pk).values_list(
            'key', 'site_id').first()
    setattr(instance, _PREVIOUS_SCOPE_ATTR,
            settings_cache_key(*previous) if previous else None)


@receiver([post_save, post_delete], sender=GentelellaSettings)
def _forget_cached_setting(sender, instance, **kwargs):
    # The admin and any other ORM write change a value in place: the next read
    # must see it, not what get_settings cached before -- in the scope the row
    # has now and in the one it had before the save (another key or Site).
    keys = {settings_cache_key(instance.key, instance.site_id)}
    previous = instance.__dict__.pop(_PREVIOUS_SCOPE_ATTR, None)
    if previous is not None:
        keys.add(previous)
    backend = caches[DEFAULT_CACHE_ALIAS]  # `cache` is a proxy: no isinstance
    if not isinstance(backend, DatabaseCache):
        cache.delete_many(list(keys))
        return
    # A DatabaseCache whose table was never created (a test database: nobody
    # runs createcachetable) holds nothing to forget, and must not break the
    # save -- a fixture load, typically. The savepoint keeps the failed query
    # from aborting the surrounding transaction on PostgreSQL.
    try:
        with transaction.atomic(using=router.db_for_write(backend.cache_model_class)):
            cache.delete_many(list(keys))
    except DatabaseError:
        logger.warning('Could not forget the cached settings %s: the cache '
                       'table is not there (run createcachetable).', sorted(keys))


class MenuItemQuerySet(TreeQuerySet):
    def get_by_natural_key(self, key, site_domain=None):
        """The item with ``key`` in the scope of the Site whose domain is
        ``site_domain`` (``None``: the global items). An item without a key
        has no natural key."""
        if not key:
            raise self.model.DoesNotExist('A menu item without a key has no '
                                          'natural key.')
        if site_domain is None:
            return self.get(key=key, site__isnull=True)
        return self.get(key=key, site__domain=site_domain)


class MenuItem(TreeNode):
    title = models.CharField(max_length=500)
    permission = models.ManyToManyField(Permission, blank=True)
    url_name = models.CharField(max_length=500)
    category = models.CharField(
        max_length=200, default='main', help_text='Clasifica items'
    )
    is_reversed = models.BooleanField(default=False)
    reversed_kwargs = models.CharField(
        max_length=500,
        null=True,
        blank=True,
        help_text='Ej key:value,key1:value,key2:value2',
    )
    reversed_args = models.CharField(
        max_length=500,
        null=True,
        blank=True,
        help_text='Comma separed atributes, can access to template context '
        + 'with request.user.pk',
    )

    is_widget = models.BooleanField(default=False)
    icon = models.CharField(max_length=50, null=True, blank=True)
    only_icon = models.BooleanField(default=False)

    position = models.IntegerField(default=0)
    # NULL is a global item, shown on every site.
    site = models.ForeignKey(
        'sites.Site',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='gentelella_menu_items',
        verbose_name=_('Site'),
        help_text=_('Empty: the item is global, shown on every site.'),
    )
    # A condition of djgentelella.authorization: the item shows only when it
    # holds, besides the permissions.
    condition = models.JSONField(
        null=True,
        blank=True,
        verbose_name=_('Condition'),
        help_text=_('Empty: no condition. A djgentelella.authorization condition, '
                    'e.g. {"perm": "app.view_model"} or {"flag": "beta"}.'),
    )
    # The natural key, with the Site: what an exported menu names the item by,
    # so importing it again updates it in place. Optional.
    key = models.SlugField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name=_('Key'),
        help_text=_('Optional. Names the item in its Site (or among the global '
                    'items) when a menu is exported and imported again.'),
    )

    objects = MenuItemQuerySet.as_manager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['site', 'key'],
                condition=models.Q(key__isnull=False, site__isnull=False),
                name='djgentelella_menuitem_unique_site_key',
            ),
            # NULLs never collide in a unique index: the global items need
            # their own.
            models.UniqueConstraint(
                fields=['key'],
                condition=models.Q(key__isnull=False, site__isnull=True),
                name='djgentelella_menuitem_unique_global_key',
            ),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        # A blank key is no key: '' would collide with every other blank one.
        if not self.key:
            self.key = None
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        # A widget item names a class the menu imports and calls: only those
        # the project declares (djgentelella.menu.register_menu_widget).
        if self.is_widget and not is_menu_widget(self.url_name):
            raise ValidationError({'url_name': _(
                '%s is not a registered menu widget.') % self.url_name})


class Help(models.Model):
    id_view = models.CharField(max_length=50, help_text='View id')
    question_name = models.CharField(
        max_length=250, help_text='Is a identificaction for question label'
    )
    help_title = models.CharField(max_length=350, verbose_name=_('Help title'))
    help_text = models.TextField(blank=True, default='', verbose_name=_('Help text'))

    def __str__(self):
        return self.help_text


class Notification(models.Model):
    STATE = [('visible', _('Visible')), ('hide', _('Hidden'))]

    MESSAGE_TYPE = (
        ('default', _('Default')),
        ('info', _('Information')),
        ('success', _('Success')),
        ('warning', _('Warning')),
        ('danger', _('Danger')),
    )

    description = models.TextField(verbose_name=_('Description'))
    link = models.URLField(verbose_name=_('Link'))
    user = models.ForeignKey(
        USER_MODEL_BASE, on_delete=models.CASCADE, verbose_name=_('User')
    )
    # warning, success, info,
    message_type = models.CharField(
        max_length=150, choices=MESSAGE_TYPE, verbose_name=_('Message Type')
    )
    state = models.CharField(
        max_length=150, default='visible', choices=STATE, verbose_name=_('State')
    )
    category = models.UUIDField(null=True, blank=True, verbose_name=_('Category'))
    creation_date = models.DateTimeField(auto_now_add=True)
    update_date = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.description

    class Meta:
        ordering = ['-creation_date']


class PermissionsCategoryManagement(models.Model):
    name = models.CharField(max_length=150, verbose_name=_('Name'))
    category = models.CharField(max_length=50, verbose_name=_('Category'))
    url_name = models.CharField(max_length=50, verbose_name=_('Url Name'))
    permission = models.ForeignKey(
        Permission,
        on_delete=models.CASCADE,
        null=False,
        blank=False,
        verbose_name=_('Permission'),
    )

    def __str__(self):
        return '%s ½s.%s' % (self.category, self.url_name)

    class Meta:
        permissions = [('can_manage_permissions', 'Can manage permissions')]


# determine the "null" and "blank" properties of "user" field in
# the "ChunkedUpload" model
DEFAULT_MODEL_USER_FIELD_NULL = getattr(
    settings, 'CHUNKED_UPLOAD_MODEL_USER_FIELD_NULL', True
)
DEFAULT_MODEL_USER_FIELD_BLANK = getattr(
    settings, 'CHUNKED_UPLOAD_MODEL_USER_FIELD_BLANK', True
)


class ChunkedUpload(AbstractChunkedUpload):
    """
    Default chunked upload model.
    """

    user = models.ForeignKey(
        USER_MODEL_BASE,
        on_delete=models.CASCADE,
        related_name='chunked_uploads',
        null=DEFAULT_MODEL_USER_FIELD_NULL,
        blank=DEFAULT_MODEL_USER_FIELD_BLANK,
    )


class HistoryRelation(models.Model):
    """Links one audit ``LogEntry`` to the other objects an action touched.

    One action often spans several instances (an object shared with several
    containers, a transfer between two of them): each of them gets a row, so
    the history of any related object is one indexed join away
    (``LogEntry.objects.filter(gt_relations__content_type=..., ...)``).

    ``data`` stores an arbitrary JSON annotation.  On a row with a target it
    describes that relation; a row with no target (``content_type`` and
    ``object_id`` NULL) carries the entry's own extra payload — request
    metadata, browser, whatever the caller passed as ``extra`` to
    :func:`djgentelella.history.utils.add_log`.
    """

    log_entry = models.ForeignKey(
        'admin.LogEntry',
        on_delete=models.CASCADE,
        related_name='gt_relations',
        verbose_name=_('Log entry'),
    )
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name=_('Content type'),
    )
    object_id = models.PositiveBigIntegerField(
        null=True, blank=True, verbose_name=_('Object ID')
    )
    content_object = GenericForeignKey('content_type', 'object_id')
    data = models.JSONField(null=True, blank=True, verbose_name=_('Data'))

    class Meta:
        ordering = ('id',)
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
        ]
        constraints = [
            models.CheckConstraint(
                # A row either points at something (both halves of the
                # generic FK) or carries data; never an empty husk.
                condition=(
                    models.Q(
                        content_type__isnull=False, object_id__isnull=False
                    )
                    | models.Q(
                        content_type__isnull=True,
                        object_id__isnull=True,
                        data__isnull=False,
                    )
                ),
                name='gt_historyrelation_valid_row',
            ),
        ]
        verbose_name = _('History relation')
        verbose_name_plural = _('History relations')

    def __str__(self):
        if self.content_type_id:
            return '%s -> %s #%s' % (
                self.log_entry_id, self.content_type, self.object_id
            )
        return _('Extra data of log entry %(pk)s') % {'pk': self.log_entry_id}


# Trash
class Trash(models.Model):
    """
    Trash generic. Each row represents an instance deleted.
    """

    content_type = models.ForeignKey(
        ContentType, on_delete=models.PROTECT, verbose_name=_('Content type')
    )
    object_id = models.PositiveIntegerField(verbose_name=_('Object ID'))
    content_object = GenericForeignKey('content_type', 'object_id')
    object_repr = models.CharField(
        _('Object repr'),
        max_length=200,
        help_text=_('Value of str(instance) at deletion time'),
    )
    deleted_by = models.ForeignKey(
        USER_MODEL_BASE,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_('Deleted by'),
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('id',)
        unique_together = ('content_type', 'object_id')
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
        ]
        verbose_name = _('Trash')
        verbose_name_plural = _('Trash')

    def __str__(self):
        return _('%(obj)s in trash') % {'obj': self.object_repr}

    def restore(self, user=None):
        obj = self.content_object

        # if `is_deleted` is in the model, unmark it
        if hasattr(obj, 'restore'):
            obj.restore()

        self.delete()  # delete the instance of trash

    def hard_delete(self):
        """
        Permanent deletion of the original object and then the trash entry.
        """
        obj = self.content_object

        # An orphan row -- its object was hard-deleted elsewhere -- has
        # nothing left to delete but the row itself.
        if obj is not None:
            # The generic FK may point at a model without the
            # DeletedWithTrash mixin, whose delete() takes no `hard`.
            if isinstance(obj, DeletedWithTrash):
                obj.delete(hard=True)
            else:
                obj.delete()

        super().delete()


class TrashRelation(models.Model):
    """Links one trash entry to the context its deletion happened in.

    A deleted object rarely stands alone: it belonged to an organization, a
    project, a folder.  Recording those instances next to the ``Trash``
    row lets a multi-tenant screen scope the trash with one indexed join
    (``Trash.objects.filter(gt_relations__content_type=..., ...)``).  Rows
    are written by ``DeletedWithTrash.delete(related_objects=...)`` and the
    queryset ``delete()``, and go away with their trash entry (restored or
    hard deleted) through the cascade.
    """

    trash = models.ForeignKey(
        Trash,
        on_delete=models.CASCADE,
        related_name='gt_relations',
        verbose_name=_('Trash entry'),
    )
    content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, verbose_name=_('Content type')
    )
    object_id = models.PositiveBigIntegerField(verbose_name=_('Object ID'))
    content_object = GenericForeignKey('content_type', 'object_id')

    class Meta:
        ordering = ('id',)
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
        ]
        verbose_name = _('Trash relation')
        verbose_name_plural = _('Trash relations')

    def __str__(self):
        return '%s -> %s #%s' % (self.trash_id, self.content_type, self.object_id)


def relation_targets(related_objects):
    """Validate ``related_objects`` into ``[(content_type, object_id)]``.

    Accepts a single instance or an iterable of instances.  Integers and
    strings are rejected on purpose, same as ``add_log()``: a bare pk does
    not say which model it belongs to, and guessing is how a trash screen
    ends up scoped to the wrong table.
    """
    if related_objects is None:
        return []
    if not hasattr(related_objects, '__iter__'):
        related_objects = [related_objects]
    targets = []
    for item in related_objects:
        if item is None:
            continue
        if isinstance(item, (int, str)):
            raise ValueError(
                'related_objects takes model instances, not %r: a bare '
                'pk does not identify the model it belongs to.' % item
            )
        targets.append(
            (ContentType.objects.get_for_model(item.__class__), item.pk)
        )
    return targets


class DeletedWithTrash(models.Model):
    is_deleted = models.BooleanField(default=False, db_index=True)

    objects = ObjectManager()
    objects_with_deleted = AllObjectsManager()
    objects_deleted_only = DeletedObjectsManager()

    class Meta:
        abstract = True

    def delete(self, using=None, keep_parents=False, *, hard=False, user=None,
               related_objects=None):
        if hard:
            # Permanent deletion
            return super().delete(using=using, keep_parents=keep_parents)

        self.is_deleted = True
        self.save(update_fields=['is_deleted'])

        # create trash instance
        trash, _created = Trash.objects.get_or_create(
            content_type=ContentType.objects.get_for_model(self.__class__),
            object_id=self.pk,
            defaults={
                'object_repr': str(self)[:200],
                'deleted_by': user,
            },
        )

        # The first deletion that provides context wins: a re-deleted entry
        # keeps the relations recorded when it originally went to the trash.
        if related_objects is not None and not trash.gt_relations.exists():
            TrashRelation.objects.bulk_create([
                TrashRelation(
                    trash=trash, content_type=ctype, object_id=object_id
                )
                for ctype, object_id in relation_targets(related_objects)
            ])

    # Restore an object
    def restore(self):
        self.is_deleted = False
        self.save(update_fields=['is_deleted'])
