from django.contrib.auth.decorators import permission_required
from django.contrib.auth.mixins import PermissionRequiredMixin

# Create your views here.
from django.db.models import Q
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.utils.translation import gettext_lazy as _

from . import models
from .forms import EntryForm, CategoryForm
from .models import Category


class EntriesList(ListView):

    model = models.Entry
    template_name = 'gentelella/blog/entry_list.html'
    context_object_name = 'entries'
    paginate_by = 10
    paginate_orphans = 5

    def get_queryset(self):
        queryset = super(EntriesList, self).get_queryset().filter(
            Q(is_published=True) | Q(author__isnull=False, author=self.request.user.id))

        q = self.request.GET.get('q', '')
        if q:
            queryset = queryset.filter(Q(published_content__icontains=q)|Q(title__icontains=q))
        cat = self.get_category_id()
        if cat:
            queryset = queryset.filter(categories__in=[cat])
        return queryset.order_by('is_published', '-published_timestamp')  # Put 'drafts' first.

    def get_query_get_params(self, exclude=[]):
        values=[]
        dev = '?'
        for key in self.request.GET.keys():
            if key not in exclude:
                values.append(
                    '%s=%s' % (key, self.request.GET.get(key))
                    )

        if values:
            dev += "&".join(values)

        if dev != '?':
            dev += '&'
        return dev

    def get_category_id(self):
        try:
            dev = int(self.request.GET.get('cat', ''))
        except ValueError:
            dev = ''
        return dev

    def get_context_data(self,  **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.all()
        context['catparams'] = self.get_query_get_params(exclude=['cat'])
        context['q'] = self.request.GET.get('q', '')
        context['cat'] = self.get_category_id()
        context['getparams'] = self.get_query_get_params(exclude=['page'])
        return context

class EntryDetail(DetailView):

    model = models.Entry
    template_name = 'gentelella/blog/entry_detail.html'
    context_object_name = 'entry'
    slug_field = 'slug'

    def get_queryset(self):
        return super(EntryDetail, self).get_queryset().filter(
            Q(is_published=True) | Q(author__isnull=False, author=self.request.user.id))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['draft'] = self.request.GET.get('preview', '') == 'True' and (self.request.user == context['entry'].author
        or self.request.user.has_perm('blog.change_entry'))
        return context

class EntryCreate(PermissionRequiredMixin, CreateView):
    permission_required = 'blog.add_entry'
    model = models.Entry
    template_name = 'gentelella/blog/entry_form.html'
    success_url = reverse_lazy('blog:entrylist')
    form_class = EntryForm

    def form_valid(self, form):
        response = super().form_valid(form)
        publishbtn=self.request.POST.get('publishbtn', '')=='publish'
        if publishbtn:
            self.object.is_published = True
        if self.object.is_published and publishbtn:
            self.object.published_content = self.object.content.rendered
        if self.object.author is None:
            self.object.author = self.request.user
        self.object.save()
        return response


class EntryUpdate(PermissionRequiredMixin, UpdateView):
    permission_required = 'blog.change_entry'
    model = models.Entry
    template_name = 'gentelella/blog/entry_form.html'
    success_url = reverse_lazy('blog:entrylist')
    form_class = EntryForm

    def form_valid(self, form):
        response = super().form_valid(form)
        publishbtn=self.request.POST.get('publishbtn', '')=='publish'
        if publishbtn:
            self.object.is_published = True
        if self.object.is_published and publishbtn:
            self.object.published_content = self.object.content.rendered
        if self.object.author is None:
            self.object.author = self.request.user
        self.object.save()
        return response


class EntryDelete(PermissionRequiredMixin, DeleteView):
    permission_required = 'blog.delete_entry'
    model = models.Entry
    template_name = 'gentelella/blog/entry_delete.html'
    success_url = reverse_lazy('blog:entrylist')


@permission_required('blog.add_category')
def category_add(request):
    if request.method == 'POST':
        form =CategoryForm(request.POST)
        if form.is_valid():
            instance = form.save()
            return JsonResponse({'ok': True, 'id': instance.pk, 'text': str(instance)})

        return JsonResponse({'ok': False,
                             'title': _("An error happen, please try again"),
                             'message':  render_to_string('gentelella/blog/category_add.html',
                                    context={
                                        'form': form
                                    })})
    form = CategoryForm()
    data = {
        'ok':  True,
        'title': _('Name of new category'),
        'message': render_to_string('gentelella/blog/category_add.html',
                                    context={
                                        'form': form
                                    })
    }
    return JsonResponse(data)