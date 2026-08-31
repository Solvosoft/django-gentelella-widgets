from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from demoapp.models import PDFDocument
from demoapp.pdfviewer.forms import PDFDocumentForm


class PDFViewerListView(LoginRequiredMixin, ListView):
    model = PDFDocument
    template_name = 'gentelella/pdfviewer/list.html'
    context_object_name = 'documents'


class PDFViewerCreateView(LoginRequiredMixin, CreateView):
    model = PDFDocument
    form_class = PDFDocumentForm
    template_name = 'gentelella/pdfviewer/form.html'
    success_url = reverse_lazy('pdfviewer-list')


class PDFViewerUpdateView(LoginRequiredMixin, UpdateView):
    model = PDFDocument
    form_class = PDFDocumentForm
    template_name = 'gentelella/pdfviewer/form.html'
    success_url = reverse_lazy('pdfviewer-list')


class PDFViewerDeleteView(LoginRequiredMixin, DeleteView):
    model = PDFDocument
    template_name = 'gentelella/pdfviewer/confirm_delete.html'
    success_url = reverse_lazy('pdfviewer-list')
