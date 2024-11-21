
from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from djgentelella.models import GTDbForm, GTStatus


#EDIT


def update_steps(edges_data_json, steps_data_json, step_form, actions_form, skip_condition_form, flow_instance):
    steps_instances = []
    id_map = {}

    with transaction.atomic():
        for step in steps_data_json:
            step_data = step['data']

            if step_data.get('status_id'):
                try:
                    status_instance = GTStatus.objects.get(id=step_data['status_id'])
                except GTStatus.DoesNotExist:
                    status_instance = None
            else:
                status_instance = None

            step_form_data = {
                'name': step_data['name'],
                'order': step_data['order'],
                'status_id': status_instance,
            }

            step_instance = flow_instance.step.filter(id=step_data['id']).first()

            if step_instance:
                step_instance.name = step_form_data['name']
                step_instance.order = step_form_data['order']
                step_instance.status_id = status_instance
                step_instance.save()

                step_instance.form.set([])
                step_instance.pre_action.set([])
                step_instance.post_action.set([])

                form_ids = step_data.get('form', [])
                if form_ids:
                    form_ids = list(map(int, form_ids))
                    related_forms = GTDbForm.objects.filter(id__in=form_ids)
                    step_instance.form.set(related_forms)
                else:
                    pass

                update_actions(step_instance, step_data, actions_form)
                id_map[step_data['id']] = step_instance.id
            else:

                step_instance = step_form.objects.create(**step_form_data)

                step_instance.form.set([])
                step_instance.pre_action.set([])
                step_instance.post_action.set([])

                save_actions(step_data, step_instance, actions_form)

                flow_instance.step.add(step_instance)

                steps_instances.append(step_instance)
                id_map[step_data['id']] = step_instance.id

        update_skip_condition(skip_condition_form, edges_data_json, id_map)


def update_actions(step_instance, step_data, actions_form):


        if 'pre_action' in step_data and step_data['pre_action']:
            for pre_action_data in step_data['pre_action']:

                if 'id' in pre_action_data and isinstance(pre_action_data['id'],
                                                          str) and \
                    pre_action_data['id'].startswith('action_'):
                    pre_action_data['id'] = int(
                        pre_action_data['id'].replace('action_', ''))

                pre_action = step_instance.pre_action.filter(
                    id=pre_action_data['id']).first()
                if pre_action:
                    pre_action.name = pre_action_data['name']
                    pre_action.description = pre_action_data['description']
                    pre_action.object_id = pre_action_data['object_id']
                    pre_action.content_type_id = int(pre_action_data['content_type'])
                    pre_action.save()

                else:

                    pre_action_form = actions_form(pre_action_data)
                    if pre_action_form.is_valid():
                        pre_action = pre_action_form.save()
                        step_instance.pre_action.add(pre_action)



        if 'post_action' in step_data and step_data['post_action']:
            for post_action_data in step_data['post_action']:

                if 'id' in post_action_data and isinstance(post_action_data['id'],
                                                           str) and \
                    post_action_data['id'].startswith('action_'):
                    post_action_data['id'] = int(
                        post_action_data['id'].replace('action_', ''))

                post_action = step_instance.post_action.filter(
                    id=post_action_data['id']).first()
                if post_action:
                    post_action.name = post_action_data['name']
                    post_action.description = post_action_data['description']
                    post_action.object_id = post_action_data['object_id']
                    post_action.content_type_id = int(post_action_data['content_type'])
                    post_action.save()

                else:
                    post_action_form = actions_form(post_action_data)
                    if post_action_form.is_valid():
                        post_action = post_action_form.save()
                        step_instance.post_action.add(post_action)



def update_skip_condition(skip_condition_form, edges_data_json, id_map):

    valid_skip_data = prepare_skip_conditions(edges_data_json, id_map)

    for edge_data in valid_skip_data:
        edge_id = edge_data.get('step_id')

        existing_condition = skip_condition_form.Meta.model.objects.filter(
            step_id=edge_id,
            skip_to_step=edge_data['skip_to_step']
        ).first()

        if existing_condition:
            existing_condition.condition_field = edge_data.get('condition_field')
            existing_condition.condition_value = edge_data.get('condition_value')
            existing_condition.save()
        else:
            form = skip_condition_form(edge_data)
            if form.is_valid():
                form.save()

#CREATE

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

def prepare_skip_conditions(edges_data_json, id_map):

    valid_skip_data = []

    for edge in edges_data_json:
        source_id = id_map.get(edge['source'])
        target_id = id_map.get(edge['target'])

        if source_id and target_id:
            elderly, minor = identify_larger_number(source_id, target_id)
            resul = float(elderly) - float(minor)

            if resul >= 2:
                edge_data = {
                    'step_id': source_id,
                    'condition_field': edge.get('condition_field', ''),
                    'condition_value': edge.get('condition_value', ''),
                    'skip_to_step': target_id,
                }
                valid_skip_data.append(edge_data)

    return valid_skip_data

def save_skip_conditions(valid_skip_data, skip_form):

    edges_instances = []

    for edge_data in valid_skip_data:
        form = skip_form(edge_data)
        if form.is_valid():
            edge_instance = form.save()
            edges_instances.append(edge_instance)

    return edges_instances

def save_steps(edges_data_json, steps_data_json, step_form, actions_form, skip_condition_form):

    steps_instances = []
    id_map = {}

    with transaction.atomic():

        for step in steps_data_json:
            step_data = step['data']

            step_form_data = {
                'name': step_data['name'],
                'order': step_data['order'],
                'status_id': int(step_data['status_id']) if step_data.get('status_id') else None,
                'form': [],
                'pre_action': [],
                'post_action': [],
            }

            form = step_form(step_form_data)

            if form.is_valid():
                step_instance = form.save()

                form_ids = step_data.get('form', [])
                if form_ids:
                    form_ids = list(map(int, form_ids))
                    related_forms = GTDbForm.objects.filter(id__in=form_ids)
                    step_instance.form.set(related_forms)

                save_actions(step_data, step_instance, actions_form)
                stepId = step_data['id']
                steps_instances.append(step_instance)
                id_map[stepId] = step_instance.id

    valid_skip_data = prepare_skip_conditions(edges_data_json, id_map)

    save_skip_conditions(valid_skip_data, skip_condition_form)

    return steps_instances


def save_actions(step_data, step_instance, actions_form):

    if 'pre_action' in step_data and step_data['pre_action']:
        for pre_action_data in step_data['pre_action']:
            try:
                pre_action_data['content_type'] = int(pre_action_data['content_type'])

                pre_action_form = actions_form(pre_action_data)
                if pre_action_form.is_valid():
                    pre_action = pre_action_form.save()
                    step_instance.pre_action.add(pre_action)

            except ContentType.DoesNotExist:
                print('not register')

    if 'post_action' in step_data and step_data['post_action']:
        for post_action_data in step_data['post_action']:
            try:
                post_action_data['content_type'] = int(post_action_data['content_type'])

                post_action_form = actions_form(post_action_data)
                if post_action_form.is_valid():
                    post_action = post_action_form.save()
                    step_instance.post_action.add(post_action)

            except ContentType.DoesNotExist:
                print('not register ')
