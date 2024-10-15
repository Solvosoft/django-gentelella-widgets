from django.urls import reverse

from django.forms.widgets import Widget
from django.utils.safestring import mark_safe

class RedirectButtonWidget(Widget):
    def render(self, name, value, attrs=None, renderer=None):
        action_url = reverse('actions')
        button_html = f'<br> <a href="{action_url}" id="{name}_button" class="btn btn-primary hidden">Add Action</a>'
        return mark_safe(button_html)


def save_steps(steps_data_json):
    from djgentelella.forms.forms import GTStepForm
    for step in steps_data_json:
        step_data = step['data']

        step_form_data = {
            'name': step_data.get('name'),
            'order': step_data.get('order'),
            'status_id': [],
            'form': [],
            'pre_action': [],
            'post_action': [],
        }

        form = GTStepForm(step_form_data)

        if form.is_valid():
            step_instance = form.save()

            save_actions(step_data, step_instance)
            print('exito')
        else:
            print(form.errors)

def save_actions(step_data, step_instance):
    from djgentelella.forms.forms import GTActionsStepForm

    if 'preActions' in step_data and step_data['preActions']:
        for pre_action_data in step_data['preActions']:
            pre_action_form = GTActionsStepForm(pre_action_data)
            if pre_action_form.is_valid():
                pre_action = pre_action_form.save()
                step_instance.pre_action.add(pre_action)
            else:
                print(pre_action_form.errors)


    if 'postActions' in step_data and step_data['postActions']:
        for post_action_data in step_data['postActions']:
            post_action_form = GTActionsStepForm(post_action_data)
            if post_action_form.is_valid():
                post_action = post_action_form.save()
                step_instance.post_action.add(post_action)
            else:
                print(post_action_form.errors)
