import json

from django.contrib import messages
from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404

from djgentelella.forms.forms import GTStepForm, GTActionsStepForm, GTStatusForm, \
    GTSkipConditionForm, GTFlowForm, GTDbFormSet, GTDbFieldForm
from djgentelella.models import GTStep, GTFlow, GTSkipCondition, GTStatus, GTDbField
from demoapp.flow.utils import save_steps, update_steps

def base_nav(request):

    return render(request, 'gentelella/flow/base_nav.html', {})

def get_flows_data():
    flows = GTFlow.objects.prefetch_related('step').all()
    return list(flows.values('id', 'name', 'description'))
def flows_index(request):

    flows_data = get_flows_data()

    return render(request, 'gentelella/flow/flows_index.html', {'flows_data': json.dumps(flows_data)})

def flow(request):
    edit = request.GET.get('edit', False)
    if edit:
        return render(request, 'gentelella/flow/flow.html', {'edit_flow': edit, 'data_local': True})

    return render(request, 'gentelella/flow/flow.html', {})


def view_flow(request, id):

    flow = get_object_or_404(GTFlow, id=id)

    gt_db_form_formset = GTDbFormSet()
    gt_db_field_form = GTDbFieldForm()

    steps = flow.step.all()
    steps_with_forms_and_fields = []

    for step in steps:
        forms = step.form.all()

        forms_with_fields = []
        for form in forms:
            fields = GTDbField.objects.filter(form=form).order_by('order')

            forms_with_fields.append({
                'id': form.id,
                'token': form.token,
                'prefix': form.prefix,
                'representation_list': form.representation_list,
                'template_name': form.template_name,
                'fields': [{'id': field.id, 'name': field.name, 'label': field.label,
                            'required': field.required, 'order': field.order} for field
                           in fields]
            })

        steps_with_forms_and_fields.append({
            'id': step.id,
            'name': step.name,
            'order': step.order,
            'forms_with_fields': forms_with_fields
        })

    data = {
        'flow': {
            'id': flow.id,
            'name': flow.name,
            'description': flow.description,
        },
        'steps': steps_with_forms_and_fields
    }

    return render(request,'gentelella/flow/view_flow.html', {'data': json.dumps(data), 'gt_db_form_formset': gt_db_form_formset, 'gt_db_field_form': gt_db_field_form})

def edit_flow(request, id):

    flow = get_object_or_404(GTFlow, id=id)
    form = GTFlowForm(request.POST or None, instance=flow)

    steps = []
    for step in flow.step.all():
        form_ids = step.form.values_list('id', flat=True)

        pre_actions = list(step.pre_action.values('id', 'name', 'description', 'content_type', 'object_id'))
        post_actions = list(step.post_action.values('id', 'name', 'description', 'content_type', 'object_id'))

        steps.append({
            'id': step.id,
            'name': step.name,
            'order': step.order,
            'status_id': step.status_id.id if step.status_id else None,
            'form': list(form_ids),
            'pre_action': pre_actions,
            'post_action': post_actions
        })

    edges_data_json = []
    for step in flow.step.all():
        edges = GTSkipCondition.objects.filter(step_id=step)
        for edge in edges:
            edges_data_json.append({
                'id': edge.id,
                'source': edge.step_id.id,
                'target': edge.skip_to_step.id,
                'condition_field': edge.condition_field,
                'condition_value': edge.condition_value
            })

    data = {
        'flow': {
            'id': flow.id,
            'name': flow.name,
            'description': flow.description,
        },
        'steps': list(steps),
        'edges': edges_data_json
    }

    return render(request,'gentelella/flow/flow.html', {'data': json.dumps(data), 'edit_flow':True})



def edit_flow_data(request, id):

   if request.method == 'POST':
       flow = get_object_or_404(GTFlow, id=id)
       form = GTFlowForm(request.POST, instance=flow)

       if form.is_valid():

           form.save()

           steps_data_json = form.cleaned_data['stepsData']
           edges_data_json = form.cleaned_data['edgesData']

           update_steps(edges_data_json, steps_data_json, GTStep, GTActionsStepForm, GTSkipConditionForm, flow)
           flows_data = get_flows_data()

           return render(request, 'gentelella/flow/flows_index.html',
                         {'flows_data': json.dumps(flows_data)})


def create_flow(request):

    form = GTFlowForm()

    if request.method == 'POST':
        form = GTFlowForm(request.POST)

        if form.is_valid():
            flow_instance = form.save()

            steps_data_json = form.cleaned_data['stepsData']
            edges_data_json = form.cleaned_data['edgesData']

            steps_instances = save_steps(edges_data_json, steps_data_json, GTStepForm, GTActionsStepForm, GTSkipConditionForm)

            flow_instance.step.set(steps_instances)

            return redirect('flows_index')

        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")

            return render(request, 'gentelella/flow/create_flow.html', {'form': form})

    return render(request, 'gentelella/flow/create_flow.html', {'form': form})

def step_index(request, id):
    form = GTStepForm()

    return render(request, 'gentelella/flow/step.html', {'form': form, 'id': id})

def actions_index(request):

    return render(request, 'gentelella/flow/actions_index.html')

def actions_form(request, id, action):
    form = GTActionsStepForm()

    return render(request, 'gentelella/flow/action.html', {'form': form, 'id':id, 'action':action})


def status_index(request):
    form = GTStatusForm()
    if request.method == 'POST':
        form = GTStatusForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('status')

    return render(request, 'gentelella/flow/status.html', {'form': form})

def skip_conditions_index(request):

    return render(request, 'gentelella/flow/skip_conditions_index.html')

def skip_condition_form(request, id):
    form = GTSkipConditionForm()

    return render(request, 'gentelella/flow/skip_condition.html', {'form': form, 'id':id})

def delete_flow(request, id):
    try:
        flow = GTFlow.objects.get(id=id)

        with transaction.atomic():
            steps_to_delete = flow.step.all()

            GTSkipCondition.objects.filter(step_id__in=steps_to_delete).delete()

            for step in steps_to_delete:
                post_actions = step.post_action.all()
                pre_actions = step.pre_action.all()

                step.post_action.clear()
                step.pre_action.clear()

                for action in post_actions.union(pre_actions):
                    if not action.post_steps.exists() and not action.pre_steps.exists():
                        action.delete()

            steps_to_delete.delete()

            flow.delete()

        messages.success(request, 'Flujo eliminado correctamente.')

    except GTFlow.DoesNotExist:
        messages.error(request, 'Flujo no encontrado.')

    except Exception as e:
        messages.error(request, f'Error al eliminar el flujo: {str(e)}')

    return redirect('flows_index')


#Status


def status_index(request):

    form = GTStatusForm()

    statuses = GTStatus.objects.all()
    statuses_data = list(statuses.values('id', 'name', 'description'))

    return render(request, 'gentelella/flow/status/status_index.html',{'form':form, 'statuses_data': json.dumps(statuses_data)})
def status_create(request):
    form = GTStatusForm()

    if request.method == 'POST':
        form = GTStatusForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('status_index')

    return render(request, 'gentelella/flow/status/status.html',{ 'form': form})

def status_edit(request, id):
    status = get_object_or_404(GTStatus, id=id)
    form = GTStatusForm(instance=status)

    if request.method == 'POST':
        form = GTStatusForm(request.POST, instance=status)
        if form.is_valid():
            form.save()
            return redirect('status_index')

    return render(request, 'gentelella/flow/status/status.html',{ 'form': form})

def status_delete(request, id):
    status = get_object_or_404(GTStatus, id=id)

    if request.method == 'POST':
        status.delete()
        messages.success(request, 'Flujo eliminado correctamente.')
    else:
        print(status.id)

    return redirect('status_index')


