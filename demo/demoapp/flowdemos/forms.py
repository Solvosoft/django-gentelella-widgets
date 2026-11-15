"""Forms of the flow demos: the ones that create the objects, and the ones a
transition asks for."""

from django import forms
from django.utils.translation import gettext_lazy as _

from demoapp import models
from djgentelella.forms.forms import GTForm
from djgentelella.forms.widgetmap import gt_formfield_callback
from djgentelella.widgets import core as genwidgets


# -- what a transition asks for --------------------------------------------------
class PurchaseOrderForm(GTForm):
    """Not a ModelForm: its data only goes to the log (the file by name)."""

    supplier = forms.CharField(label=_('Supplier'), widget=genwidgets.TextInput)
    order_number = forms.CharField(label=_('Order number'),
                                   widget=genwidgets.TextInput)
    quote = forms.FileField(label=_('Quote'), required=False,
                            widget=genwidgets.FileInput)


class ResolutionForm(GTForm, forms.ModelForm):
    """A ModelForm: the engine saves it on the ticket, in the transition."""

    class Meta:
        model = models.SupportTicket
        fields = ['resolution']
        formfield_callback = gt_formfield_callback

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['resolution'].required = True


class ReviewNotesForm(GTForm, forms.ModelForm):
    class Meta:
        model = models.EditorialDocument
        fields = ['reviewer_notes']
        formfield_callback = gt_formfield_callback

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['reviewer_notes'].required = True


# -- what creates the objects (gt_formfield_callback picks the widgets) -----------
class PurchaseRequestForm(GTForm, forms.ModelForm):
    class Meta:
        model = models.PurchaseRequest
        fields = ['title', 'amount', 'justification']
        formfield_callback = gt_formfield_callback


class SupportTicketForm(GTForm, forms.ModelForm):
    class Meta:
        model = models.SupportTicket
        fields = ['subject', 'priority', 'description']
        formfield_callback = gt_formfield_callback


class EditorialDocumentForm(GTForm, forms.ModelForm):
    class Meta:
        model = models.EditorialDocument
        fields = ['title', 'body']
        formfield_callback = gt_formfield_callback


class LeaveRequestForm(GTForm, forms.ModelForm):
    class Meta:
        model = models.LeaveRequest
        fields = ['approver', 'start', 'end', 'reason']
        formfield_callback = gt_formfield_callback

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('start') and cleaned.get('end') and \
                cleaned['end'] < cleaned['start']:
            self.add_error('end', _('It ends before it starts.'))
        return cleaned


class ExpenseReportForm(GTForm, forms.ModelForm):
    class Meta:
        model = models.ExpenseReport
        fields = ['title', 'amount', 'manager']
        formfield_callback = gt_formfield_callback
