from django.contrib.auth.models import Permission, User
from django.db import models
from mptt.models import MPTTModel, TreeForeignKey
# Create your models here.
from django.utils.translation import ugettext_lazy as _


class GentelellaSettings(models.Model):
    """
    Permite personalizar el sitio, se usa para modificar configuraciones,
    temas etc.
    """
    key = models.CharField(max_length=100)
    value = models.CharField(max_length=500)

    def __str__(self):
        return self.key



class MenuItem(MPTTModel):
    #name = models.SlugField(max_length=50, unique=True)
    parent = TreeForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')
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


    def __str__(self):
        return self.title

    class MPTTMeta:
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
