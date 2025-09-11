from django.conf import settings
from django.contrib.auth.models import Permission
from django.db import models
from django.utils.translation import gettext_lazy as _
from tree_queries.models import TreeNode

from djgentelella.chunked_upload.models import AbstractChunkedUpload
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from .models_manager import ObjectManager, AllObjectsManager, \
    DeletedObjectsManager
from  djgentelella.settings import USER_MODEL_BASE
from djgentelella.history.utils import add_log, ADDITION

class GentelellaSettings(models.Model):
    """
    Permite personalizar el sitio, se usa para modificar configuraciones,
    temas etc.
    """
    key = models.CharField(max_length=100)
    value = models.CharField(max_length=500)

    def __str__(self):
        return self.key


class MenuItem(TreeNode):
    title = models.CharField(max_length=500)
    permission = models.ManyToManyField(Permission, blank=True)
    url_name = models.CharField(max_length=500)
    category = models.CharField(max_length=200, default='main',
                                help_text="Clasifica items")
    is_reversed = models.BooleanField(default=False)
    reversed_kwargs = models.CharField(max_length=500, null=True, blank=True,
                                       help_text="Ej key:value,key1:value,key2:value2")
    reversed_args = models.CharField(
        max_length=500, null=True, blank=True,
        help_text="Comma separed atributes, can access to template context " +
                  "with request.user.pk")

    is_widget = models.BooleanField(default=False)
    icon = models.CharField(max_length=50, null=True, blank=True)
    only_icon = models.BooleanField(default=False)

    position = models.IntegerField(default=0)

    def __str__(self):
        return self.title

    class MPTTMeta:
        ordering = ["position"]
        order_insertion_by = ['-id']


class Help(models.Model):
    id_view = models.CharField(max_length=50,
                               help_text="View id")
    question_name = models.CharField(
        max_length=250, help_text="Is a identificaction for question label")
    help_title = models.CharField(max_length=350, verbose_name=_('Help title'))
    help_text = models.TextField(blank=True, default="", verbose_name=_('Help text'))

    def __str__(self):
        return self.help_text

class Notification(models.Model):
    STATE = [('visible', _('Visible')),
             ('hide', _('Hidden'))]

    MESSAGE_TYPE = (
        ('default', _('Default')),
        ('info', _('Information')),
        ('success', _('Success')),
        ('warning', _('Warning')),
        ('danger', _('Danger')),
    )

    description = models.TextField(verbose_name=_("Description"))
    link = models.URLField(verbose_name=_('Link'))
    user = models.ForeignKey(USER_MODEL_BASE, on_delete=models.CASCADE, verbose_name=_('User'))
    # warning, success, info,
    message_type = models.CharField(max_length=150, choices=MESSAGE_TYPE,
                                    verbose_name=_('Message Type'))
    state = models.CharField(max_length=150, default='visible', choices=STATE,
                             verbose_name=_('State'))
    category = models.UUIDField(null=True, blank=True, verbose_name=_("Category"))
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
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE, null=False,
                                   blank=False, verbose_name=_('Permission'))

    def __str__(self):
        return "%s ½s.%s" % (self.category, self.url_name)

    class Meta:
        permissions = [('can_manage_permissions', 'Can manage permissions')]


# determine the "null" and "blank" properties of "user" field in
# the "ChunkedUpload" model
DEFAULT_MODEL_USER_FIELD_NULL = getattr(settings,
                                        'CHUNKED_UPLOAD_MODEL_USER_FIELD_NULL', True)
DEFAULT_MODEL_USER_FIELD_BLANK = getattr(settings,
                                         'CHUNKED_UPLOAD_MODEL_USER_FIELD_BLANK', True)


class ChunkedUpload(AbstractChunkedUpload):
    """
    Default chunked upload model.
    """
    user = models.ForeignKey(
        USER_MODEL_BASE,
        on_delete=models.CASCADE,
        related_name='chunked_uploads',
        null=DEFAULT_MODEL_USER_FIELD_NULL,
        blank=DEFAULT_MODEL_USER_FIELD_BLANK
    )


# Trash
class Trash(models.Model):
    """
        Trash generic. Each row represents an instance deleted.
    """
    content_type = models.ForeignKey(ContentType, on_delete=models.PROTECT,
                                     verbose_name=_("Content type"))
    object_id = models.PositiveIntegerField(verbose_name=_("Object ID"))
    content_object = GenericForeignKey("content_type", "object_id")
    object_repr = models.CharField(
        _("Object repr"), max_length=200,
        help_text=_("Value of str(instance) at deletion time"),
    )
    deleted_by = models.ForeignKey(
        USER_MODEL_BASE,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Deleted by")
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("id",)
        unique_together = ("content_type", "object_id")
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
        ]
        verbose_name = _("Trash")
        verbose_name_plural = _("Trash")

    def __str__(self):
        return _("%(obj)s in trash") % {"obj": self.object_repr}

    def restore(self, user=None):
        obj = self.content_object

        # if `is_deleted` is in the model, unmark it
        if hasattr(obj, "restore"):
            obj.restore()

        self.delete()  # delete the instance of trash


    def hard_delete(self):
        """
            Permanent deletion of the original object and then the trash entry.
        """
        obj = self.content_object

        if obj is None:
            return

        obj.delete(hard=True)

        super().delete()


class DeletedWithTrash(models.Model):
    is_deleted = models.BooleanField(default=False, db_index=True)

    objects = ObjectManager()
    objects_with_deleted = AllObjectsManager()
    objects_deleted_only = DeletedObjectsManager()

    class Meta:
        abstract = True

    def delete(self, using=None, keep_parents=False, *, hard=False, user=None):
        if hard:
            # Permanent deletion
            return super().delete(using=using, keep_parents=keep_parents)

        self.is_deleted = True
        self.save(update_fields=["is_deleted"])

        # create trash instance
        trash = Trash.objects.get_or_create(
            content_type=ContentType.objects.get_for_model(self.__class__),
            object_id=self.pk,
            defaults={
                "object_repr": str(self)[:200],
                "deleted_by": user,
            },
        )

    # Restore an object
    def restore(self):
        self.is_deleted = False
        self.save(update_fields=["is_deleted"])
