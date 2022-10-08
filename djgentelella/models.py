from django.contrib.auth.models import Permission, User
from django.db import models
from django.utils.translation import gettext_lazy as _
from tree_queries.models import TreeNode

from djgentelella.chunked_upload.models import AbstractChunkedUpload
from django.conf import settings

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
    #name = models.SlugField(max_length=50, unique=True)
    #parent = TreeForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')
    title = models.CharField(max_length=500)
    permission = models.ManyToManyField(Permission, blank=True)
    url_name = models.CharField(max_length=500)
    category = models.CharField(max_length=200, default='main',
                                help_text="Clasifica items")
    is_reversed = models.BooleanField(default=False)
    reversed_kwargs = models.CharField(max_length=500, null=True, blank=True,
                                       help_text="Ej key:value,key1:value,key2:value2")
    reversed_args = models.CharField(max_length=500, null=True, blank=True,
                                     help_text="Comma separed atributes, can access to template context with request.user.pk")

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
    question_name = models.CharField(max_length=250,
                                     help_text="Is a identificaction for question label")
    help_title = models.CharField(max_length=350, verbose_name=_('Help title'))
    help_text = models.TextField(blank=True, default="", verbose_name=_('Help text'))

    def __str__(self):
        return self.help_text


class Notification(models.Model):
    STATE = [('visible',_('Visible')),
               ('hide', _('Hidden'))]

    MESSAGE_TYPE=(
        ('default', _('Default')),
        ('info', _('Information')),
        ('success', _('Success')),
        ('warning', _('Warning')),
        ('danger', _('Danger')),
    )

    description = models.TextField(verbose_name=_("Description"))
    link = models.URLField(verbose_name=_('Link'))
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name=_('User'))
    # warning, success, info,
    message_type = models.CharField(max_length=150, choices=MESSAGE_TYPE, verbose_name=_('Message Type'))
    state = models.CharField(max_length=150, default='visible', choices=STATE, verbose_name=_('State'))
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
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE, null=False, blank=False, verbose_name=_('Permission'))


    def __str__(self):
        return "%s ½s.%s"%(self.category, self.url_name)


# determine the "null" and "blank" properties of "user" field in the "ChunkedUpload" model
DEFAULT_MODEL_USER_FIELD_NULL = getattr(settings, 'CHUNKED_UPLOAD_MODEL_USER_FIELD_NULL', True)
DEFAULT_MODEL_USER_FIELD_BLANK = getattr(settings, 'CHUNKED_UPLOAD_MODEL_USER_FIELD_BLANK', True)


class ChunkedUpload(AbstractChunkedUpload):
    """
    Default chunked upload model.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='chunked_uploads',
        null=DEFAULT_MODEL_USER_FIELD_NULL,
        blank=DEFAULT_MODEL_USER_FIELD_BLANK
    )
