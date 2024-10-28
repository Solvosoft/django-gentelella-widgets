from django.urls import reverse

from django.forms.widgets import Widget
from django.utils.safestring import mark_safe
from django.contrib.contenttypes.models import ContentType



def identify_larger_number(step_id, skip_to_step):
    elderly = 0
    minor = 0

    if step_id > skip_to_step:
        elderly = step_id
        minor = skip_to_step
    else:
        elderly = skip_to_step
        minor = step_id

    return elderly, minor

def save_skips_condition(edges_data_json, skip_form):

    edges_instances = []

    for edge in edges_data_json:

        elderly, minor = identify_larger_number(edge.get('source'), edge.get('target'))

        resul = float(elderly) - float(minor)

        if resul >= 2:

            edge_form_data = {
                'step_id': edge['source'],
                'condition_field': edge['condition_field'],
                'condition_value': edge['condition_value'],
                'skip_to_step': edge['target'],
            }

            form = skip_form(edge_form_data)

            if form.is_valid():
                edge_instance = form.save()
                edges_instances.append(edge_instance)

    return edges_instances

def save_steps(steps_data_json, step_form, actions_form):

    steps_instances = []

    for step in steps_data_json:
        step_data = step['data']

        step_form_data = {
            'name': step_data['name'],
            'order': step_data['order'],
            'status_id': [],
            'form': [],
            'pre_action': [],
            'post_action': [],
        }

        form = step_form(step_form_data)

        if form.is_valid():
            step_instance = form.save()
            save_actions(step_data, step_instance, actions_form)
            steps_instances.append(step_instance)

    return steps_instances

def save_actions(step_data, step_instance, actions_form):

    if 'preActions' in step_data and step_data['preActions']:
        for pre_action_data in step_data['preActions']:
            try:
                content_type = ContentType.objects.get(app_label='your_app_label', model='your_model_name')
                pre_action_data['content_type'] = content_type.id

                pre_action_form = actions_form(pre_action_data)
                if pre_action_form.is_valid():
                    pre_action = pre_action_form.save()
                    step_instance.pre_action.add(pre_action)
                else:
                    print(pre_action_form.errors)
            except ContentType.DoesNotExist:
                print("El content_type especificado no existe.")

    if 'postActions' in step_data and step_data['postActions']:
        for post_action_data in step_data['postActions']:
            try:
                content_type = ContentType.objects.get(app_label='your_app_label', model='your_model_name')
                post_action_data['content_type'] = content_type.id

                post_action_form = actions_form(post_action_data)
                if post_action_form.is_valid():
                    post_action = post_action_form.save()
                    step_instance.post_action.add(post_action)
                else:
                    print(post_action_form.errors)
            except ContentType.DoesNotExist:
                print("El content_type especificado no existe.")


def steps_skip_condition(steps_instances, step_model):

    steps = []

    for step in steps_instances:
        step_add = step_model.objects.get(id=step.id)
        steps.append(step_add)

    steps_details = [{'id': step.id, 'name': step.name, 'order': step.order, 'status_id': step.status_id, }  for step in steps]

    return steps_details
