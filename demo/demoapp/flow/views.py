from django.shortcuts import render, redirect

from djgentelella.forms.forms import GTStepForm, GTActionsStepForm, GTStatusForm, \
    GTSkipConditionForm, GTFlowForm
from djgentelella.models import GTStep
from demoapp.flow.utils import save_steps, steps_skip_condition, save_skips_condition


def flow_index(request):
    last_step = GTStep.objects.last()
    last_id_step = 0
    if last_step:
        last_id_step = last_step.id

    return render(request, 'gentelella/flow/flow.html', {'last_id_step': last_id_step})

def create_flow(request):

    form = GTFlowForm()

    if request.method == 'POST':
        form = GTFlowForm(request.POST)

        if form.is_valid():
            flow_instance = form.save()

            steps_data_json = form.cleaned_data['stepsData']
            edges_data_json = form.cleaned_data['edgesData']

            steps_instances = save_steps(steps_data_json, GTStepForm, GTActionsStepForm)
            edges_instances = save_skips_condition(edges_data_json, GTSkipConditionForm)

            flow_instance.step.set(steps_instances)

            steps_skip_condition(steps_instances, GTStep)

            return redirect('flow')

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
