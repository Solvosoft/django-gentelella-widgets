import json

from django.shortcuts import render, redirect

from demoapp.flow.utils import save_steps
from djgentelella.forms.forms import GTStepForm, GTActionsStepForm, GTStatusForm, \
    GTSkipConditionForm, GTFlowForm
from djgentelella.models import GTStep


def flow_index(request):
    return render(request, 'gentelella/flow/flow.html')

def create_flow(request):

    form = GTFlowForm()

    if request.method == 'POST':
        form = GTFlowForm(request.POST)
        if form.is_valid():
            form.save()
            steps_data = request.POST.get('stepsData')
            steps_data_json = json.loads(steps_data)
            save_steps(steps_data_json)
            return redirect('flow')

    return render(request, 'gentelella/flow/create_flow.html', {'form': form})

def step_index(request, id):

    step = GTStep()

    form = GTStepForm(instance=step)
    return render(request, 'gentelella/flow/step.html', {'form': form, 'id': id})

def actions_index(request):
    if request.method == 'POST':
        form = GTActionsStepForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('flow')
    else:
        form = GTActionsStepForm()

    return render(request, 'gentelella/flow/actions.html', {'form': form})


def status_index(request):
    if request.method == 'POST':
        form = GTStatusForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('status')
    else:
        form = GTStatusForm()

    return render(request, 'gentelella/flow/status.html', {'form': form})

def skip_condition_index(request):
    if request.method == 'POST':
        form = GTSkipConditionForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('success_url')
    else:
        form = GTSkipConditionForm()

    return render(request, 'gentelella/flow/skip_conditions.html', {'form': form})
