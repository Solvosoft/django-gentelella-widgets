from django.contrib import admin
from djgentelella.blog import models

admin.site.register(models.Entry)
admin.site.register(models.EntryImage)
admin.site.register(models.Category)
