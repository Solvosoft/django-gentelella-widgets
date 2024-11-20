import importlib

from django.conf import settings
from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from django.utils.translation import gettext_lazy as _
from tree_queries.models import TreeNode

from djgentelella.chunked_upload.models import AbstractChunkedUpload


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
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name=_('User'))
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
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='chunked_uploads',
        null=DEFAULT_MODEL_USER_FIELD_NULL,
        blank=DEFAULT_MODEL_USER_FIELD_BLANK
    )


REPRESENTATION_LIST = [
    ('as_table', _('As Table')),
    ('as_p', _('As P')),
    ('as_ul', _('As ul')),
    ('as_inline', _('As Inline')),
    ('as_horizontal', _('As Horizontal')),
    ('as_plain', _('As Plain')),
    ('as_grid', _("As grid"))

]

class GTDbForm(models.Model):
    token = models.CharField(max_length=50, unique=True, verbose_name=_("Token"))
    prefix = models.CharField(max_length=50, null=True, blank=True, verbose_name=_("Prefix"))
    representation_list = models.CharField(choices=REPRESENTATION_LIST, max_length=50, default='as_table', verbose_name=_("Representation List"))
    template_name = models.CharField(max_length=100, default='default', verbose_name=_("Template Name"))
    def __str__(self):
        return self.token

class GTDbField(models.Model):
    form = models.ForeignKey(GTDbForm, on_delete=models.CASCADE, verbose_name=_("Form"))
    name = models.CharField(max_length=100, verbose_name=_("Name"))
    label = models.CharField(max_length=100, null=True, blank=True, verbose_name=_("Label"))
    required = models.BooleanField(default=True, verbose_name=_("Required"))
    label_suffix = models.CharField(max_length=100, null=True, blank=True, verbose_name=_("Label Suffix"))
    help_text = models.CharField(max_length=500, null=True, blank=True, verbose_name=_("Help Text"))
    disabled = models.BooleanField(default=False, verbose_name=_("Disable"))
    extra_attr = models.JSONField(blank=True, null=True, verbose_name=_("Extra Attr"))
    extra_kwarg = models.JSONField(blank=True, null=True, verbose_name=_("EXtra Kwarg"))
    order = models.IntegerField(default=0, verbose_name=_("Order"))

    def __str__(self):
        return self.name

class GTStatus(models.Model):

    name = models.CharField(max_length=100, blank=False, verbose_name=_("Name"))
    description = models.TextField(blank=False, verbose_name=_("Description"))
    def __str__(self):
        return self.name

class GTActionsStep(models.Model):
    name = models.CharField(max_length=100, blank=False, verbose_name=_("Name"))
    description = models.TextField(blank=False, verbose_name=_("Description"))

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    def __str__(self):
        return self.name

class GTStep(models.Model):
    name = models.CharField(max_length=100, blank=False, verbose_name=_("Name"))
    order = models.PositiveIntegerField(blank=False, verbose_name=_("Order"))
    status_id = models.ForeignKey(GTStatus, on_delete=models.CASCADE, blank=True, null=True, verbose_name=_("Status"))
    form = models.ManyToManyField(GTDbForm, related_name='forms', verbose_name=_("Form"))
    post_action = models.ManyToManyField(GTActionsStep, related_name='post_steps', verbose_name=_("Post Action"))
    pre_action = models.ManyToManyField(GTActionsStep, related_name='pre_steps', verbose_name=_("Pre Action"))

    def __str__(self):
        return self.name

class GTFlow(models.Model):
    name = models.CharField(max_length=100, blank=False, verbose_name=_("Name"))
    description = models.TextField(blank=False, verbose_name=_("Description"))
    step = models.ManyToManyField(GTStep, related_name='steps', verbose_name=_("Step"))
    def __str__(self):
        return self.name


class GTSkipCondition(models.Model):
    step_id = models.ForeignKey(GTStep, on_delete=models.CASCADE, verbose_name=_("Step"))
    condition_field = models.CharField(max_length=100, blank=True, null=True, verbose_name=_("Condition Field"))
    condition_value = models.CharField(max_length=100, blank=True, null=True, verbose_name=_("Condition Value"))
    skip_to_step = models.ForeignKey(GTStep, on_delete=models.CASCADE, related_name='target_step', verbose_name=_("Skip To Step"))

    def execute_condition(self, context):
        module, function = self.condition_field.rsplit('.', 1)
        mod = importlib.import_module(module)
        func = getattr(mod, function)
        return func(context)



