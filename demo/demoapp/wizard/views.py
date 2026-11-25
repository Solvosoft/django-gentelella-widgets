from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _

from demoapp.models import NewHire
from demoapp.wizard.forms import JobForm, PersonalForm, VehicleForm
from djgentelella.sites import get_current_site, site_pk
from djgentelella.wizard import GTWizardView, Step


class EmployeeWizard(LoginRequiredMixin, GTWizardView):
    """Hire an employee in three steps; the vehicle step only for who comes
    by car. Drafts are kept in the database (``WizardDraft``)."""

    title = _('New employee')
    model = NewHire
    draft_storage = 'model'
    success_url = reverse_lazy('employee_wizard')
    success_message = _('The employee was saved.')
    steps = [
        Step('personal', PersonalForm, _('Personal data')),
        Step('vehicle', VehicleForm, _('Vehicle'),
             condition=lambda wizard: wizard.cleaned_value('personal', 'has_car')),
        Step('job', JobForm, _('Job')),
    ]

    def done(self, forms):
        self.object = self.save_object(
            forms, site_id=site_pk(get_current_site(self.request)))
