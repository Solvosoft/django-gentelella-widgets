import json

from django import forms
from django.contrib import admin, messages
from django.shortcuts import get_object_or_404, redirect
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from djgentelella.designs import engine
from djgentelella.designs.models import Page
from djgentelella.designs.publishing import validate


class PageAddForm(forms.ModelForm):
    class Meta:
        model = Page
        fields = ['site', 'path', 'document', 'is_published', 'permissions']

    #: Who publishes it (the admin sets it): the trust the document is
    #: validated with, as ``gtdesigns_publish --user`` does.
    publisher = None

    def clean(self):
        cleaned_data = super().clean()
        if 'document' in cleaned_data:
            # Validated as publish() does: for the page's Site, with the
            # publisher's trust and the project's ResolveContext
            # (GT_DESIGNS_RESOLVE_CONTEXT).
            errors = validate(cleaned_data['document'], self.publisher,
                              site=cleaned_data.get('site'))
            if errors:
                self.add_error('document', [str(error) for error in errors])
        return cleaned_data


@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    list_display = ['path', 'site', 'title', 'is_published', 'schema_version',
                    'updated_at', 'updated_by']
    list_filter = ['is_published', 'site']
    search_fields = ['path', 'title']
    filter_horizontal = ['permissions']
    change_form_template = 'admin/gtdesigns/page/change_form.html'
    readonly_fields = ['title', 'schema_version', 'hash', 'document_json',
                       'created_at', 'updated_at', 'updated_by']
    fields = ['site', 'path', 'is_published', 'permissions', 'title',
              'schema_version', 'hash', 'document_json', 'created_at',
              'updated_at', 'updated_by']

    @admin.display(description=_('document'))
    def document_json(self, obj):
        return format_html('<pre style="max-height: 40em; overflow: auto">{}</pre>',
                           json.dumps(obj.document, indent=2, ensure_ascii=False))

    def get_form(self, request, obj=None, **kwargs):
        if obj is None:
            kwargs['form'] = PageAddForm
        form = super().get_form(request, obj, **kwargs)
        if obj is None:
            form = type(form.__name__, (form,), {'publisher': request.user})
        return form

    def get_fields(self, request, obj=None):
        if obj is None:
            return PageAddForm.Meta.fields
        return self.fields

    def get_readonly_fields(self, request, obj=None):
        return [] if obj is None else self.readonly_fields

    def save_model(self, request, obj, form, change):
        # Whoever saves the page is its publisher: the trust for templates and
        # JavaScript (engine.page_trust) follows that user's permissions.
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)

    def get_urls(self):
        return [
            path('<int:pk>/validate/', self.admin_site.admin_view(self.validate_view),
                 name='gtdesigns_page_validate'),
        ] + super().get_urls()

    def validate_view(self, request, pk):
        page = get_object_or_404(Page, pk=pk)
        if not self.has_view_or_change_permission(request, page):
            return redirect('admin:index')
        allow_templates, allow_js = engine.page_trust(page)
        _resolved, errors = engine.resolve(page.document,
                                           allow_templates=allow_templates,
                                           allow_js=allow_js,
                                           site=page.site if page.site_id else None)
        if errors:
            for error in errors:
                messages.error(request, str(error))
        else:
            messages.success(request, _('The design is valid.'))
        return redirect(reverse('admin:gtdesigns_page_change', args=[page.pk]))
