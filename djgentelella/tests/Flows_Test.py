import datetime
from types import SimpleNamespace

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import ImproperlyConfigured
from django.core.files.uploadedfile import SimpleUploadedFile
from django.template import Context, Template
from django.test import RequestFactory, TestCase
from django.urls import reverse

from django.test import override_settings

from demoapp.models import Country, UUIDThing
from djgentelella.async_notification.models import EmailNotification, EmailTemplate
from djgentelella.flows import (
    ANY_STATE,
    Action,
    Assign,
    CallFunction,
    Flow,
    Notify,
    SendEmail,
    SetField,
    Transition,
    TransitionNotAllowed,
    get_flow,
    register_flow,
)
from djgentelella.flows.actions import resolve
from djgentelella.flows.models import FlowInstance
from djgentelella.flows.utils import json_safe
from djgentelella.models import Notification

CALLS = []


def remember(context):
    CALLS.append((context.transition.name, context.obj.pk))


def explode(context):
    raise RuntimeError('boom')


class CodeForm(forms.ModelForm):
    class Meta:
        model = Country
        fields = ['code']


@register_flow
class CountryReviewFlow(Flow):
    name = 'tests.country_review'
    title = 'Country review'
    model = Country
    states = [('draft', 'Draft'), ('review', 'In review'),
              ('approved', 'Approved'), ('rejected', 'Rejected')]
    initial = 'draft'
    transitions = [
        Transition('submit', 'draft', 'review', label='Submit',
                   perms=['demoapp.change_country'],
                   actions=[Assign(group='Reviewers'),
                            CallFunction('djgentelella.tests.Flows_Test.remember')]),
        Transition('approve', 'review', 'approved', label='Approve',
                   perms=['demoapp.view_country'], form=CodeForm,
                   condition=lambda context:
                   context.obj.name != context.user.username,
                   actions=[SetField('name', lambda context: context.obj.name.upper()),
                            Notify('{{ object }} approved by {{ user }}.', to='actor',
                                   message_type='success'),
                            SendEmail('country_approved', to=['actor', 'team@x.org'])]),
        Transition('reject', ['review'], 'rejected',
                   perms=['demoapp.delete_country'],
                   actions=[CallFunction(explode)]),
    ]


class FlowDeclarationTests(TestCase):
    def test_registry(self):
        self.assertIsInstance(get_flow('tests.country_review'), CountryReviewFlow)

    def test_invalid_declarations(self):
        class NoInitial(Flow):
            model = Country
            states = [('a', 'A')]
        with self.assertRaises(ImproperlyConfigured):
            NoInitial()

        class UnknownState(Flow):
            model = Country
            states = [('a', 'A')]
            initial = 'a'
            transitions = [Transition('go', 'a', 'z')]
        with self.assertRaises(ImproperlyConfigured):
            UnknownState()

    def test_default_name(self):
        class Plain(Flow):
            model = Country
            states = [('a', 'A')]
            initial = 'a'
        self.assertEqual(Plain().name, 'demoapp.Plain')


class FlowEngineTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.flow = get_flow('tests.country_review')
        cls.reviewers = Group.objects.create(name='Reviewers')
        cls.editor = User.objects.create_user('editor', email='ed@x.org', password='x')
        cls.editor.user_permissions.add(
            Permission.objects.get(codename='change_country'),
            Permission.objects.get(codename='view_country'))
        cls.nobody = User.objects.create_user('nobody', password='x')
        cls.country = Country.objects.create(name='Costa Rica')
        EmailTemplate.objects.create(code='country_approved',
                                     subject='{{ object }} approved',
                                     message='<p>{{ user }} approved it.</p>')

    def setUp(self):
        CALLS.clear()

    def test_objects_start_in_the_initial_state(self):
        self.assertEqual(self.flow.state(self.country), 'draft')
        self.assertFalse(FlowInstance.objects.exists())

    def test_available_transitions_follow_state_and_perms(self):
        available = self.flow.available_transitions(self.country, self.editor)
        names = [transition.name for transition in available]
        self.assertEqual(names, ['submit'])
        self.assertEqual(self.flow.available_transitions(self.country, self.nobody), [])

    def test_run_moves_logs_and_acts(self):
        instance = self.flow.run(self.country, 'submit', self.editor, comment='ready')
        self.assertEqual(instance.state, 'review')
        self.assertEqual(instance.assigned_group, self.reviewers)
        self.assertEqual(CALLS, [('submit', self.country.pk)])
        log = instance.log.get()
        self.assertEqual((log.source, log.target, log.user, log.comment),
                         ('draft', 'review', self.editor, 'ready'))

    def test_wrong_state_or_permission_is_refused(self):
        with self.assertRaises(TransitionNotAllowed):
            self.flow.run(self.country, 'approve', self.editor)
        with self.assertRaises(TransitionNotAllowed):
            self.flow.run(self.country, 'submit', self.nobody)
        with self.assertRaises(TransitionNotAllowed):
            self.flow.run(self.country, 'nope', self.editor)

    def test_condition(self):
        self.flow.run(self.country, 'submit', self.editor)
        self.country.name = 'editor'
        self.country.save()
        self.assertNotIn('approve', [t.name for t in self.flow.available_transitions(
            self.country, self.editor)])

    def test_actions_with_a_model_form(self):
        self.flow.run(self.country, 'submit', self.editor)
        form = CodeForm({'code': 'cr'}, instance=self.country)
        self.assertTrue(form.is_valid())
        self.flow.run(self.country, 'approve', self.editor, form=form)
        self.country.refresh_from_db()
        self.assertEqual((self.country.name, self.country.code), ('COSTA RICA', 'cr'))
        notice = Notification.objects.get(user=self.editor)
        self.assertEqual(notice.description, 'COSTA RICA approved by editor.')
        self.assertEqual(notice.link, reverse('flow_detail', args=[
            self.flow.name, self.country.pk]))
        email = EmailNotification.objects.get()
        self.assertEqual(email.recipients, ['ed@x.org', 'team@x.org'])
        self.assertEqual(self.flow.history(self.country).first().data, {'code': 'cr'})

    def test_a_failing_action_undoes_the_transition(self):
        self.flow.run(self.country, 'submit', self.editor)
        superuser = get_user_model().objects.create_superuser('root', password='x')
        with self.assertRaises(RuntimeError):
            self.flow.run(self.country, 'reject', superuser)
        self.assertEqual(self.flow.state(self.country), 'review')
        self.assertEqual(self.flow.history(self.country).count(), 1)

    def test_inbox(self):
        other = Country.objects.create(name='Panama')
        self.assertEqual(set(self.flow.inbox(self.editor)), {self.country, other})
        self.flow.run(self.country, 'submit', self.editor)
        reviewer = get_user_model().objects.create_user('rev', password='x')
        reviewer.groups.add(self.reviewers)
        self.assertEqual(list(self.flow.inbox(reviewer)), [self.country])
        self.assertEqual(list(self.flow.inbox(self.nobody)), [])


# English labels are asserted: the demo runs in Spanish once its .mo, which is
# not versioned, is compiled, and a local run would disagree with CI.
@override_settings(LANGUAGE_CODE='en')
class FlowViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.flow = get_flow('tests.country_review')
        cls.editor = get_user_model().objects.create_user('editor', password='x')
        cls.editor.user_permissions.add(
            Permission.objects.get(codename='change_country'))
        Group.objects.create(name='Reviewers')
        cls.country = Country.objects.create(name='Chile')

    def setUp(self):
        self.client.force_login(self.editor)

    def url(self, name, *args):
        return reverse(name, args=[self.flow.name, *args])

    def test_detail(self):
        response = self.client.get(self.url('flow_detail', self.country.pk))
        self.assertContains(response, 'Draft')
        self.assertContains(response, self.url('flow_transition', 'submit',
                                               self.country.pk))

    def test_transition_form_and_run(self):
        url = self.url('flow_transition', 'submit', self.country.pk)
        self.assertContains(self.client.get(url), 'name="flow_comment-comment"')
        response = self.client.post(url, {'flow_comment-comment': 'go',
                                          'next': '/somewhere/'})
        self.assertRedirects(response, '/somewhere/', fetch_redirect_response=False)
        self.assertEqual(self.flow.state(self.country), 'review')

    def test_unsafe_next_is_ignored(self):
        url = self.url('flow_transition', 'submit', self.country.pk)
        response = self.client.post(url, {'next': 'https://evil.example/'})
        self.assertRedirects(response, self.url('flow_detail', self.country.pk),
                             fetch_redirect_response=False)

    def test_unavailable_transition_redirects_with_a_message(self):
        url = self.url('flow_transition', 'approve', self.country.pk)
        detail = self.url('flow_detail', self.country.pk)
        self.assertRedirects(self.client.get(url), detail,
                             fetch_redirect_response=False)
        response = self.client.post(url, follow=True)
        self.assertContains(response, 'Approve cannot run from Draft.')
        self.assertEqual(self.flow.state(self.country), 'draft')

    def test_unknown_flow_and_anonymous(self):
        self.assertEqual(self.client.get(reverse(
            'flow_detail', args=['nope', 1])).status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.get(self.url('flow_inbox')).status_code, 302)

    def test_inbox_page(self):
        self.assertContains(self.client.get(self.url('flow_inbox')), 'Chile')

    def test_status_tag(self):
        request = RequestFactory().get('/page/')
        request.user = self.editor
        template = Template(
            "{% load gtflows %}{% flow_status country 'tests.country_review' %}")
        html = template.render(Context({'country': self.country, 'request': request}))
        self.assertIn('Draft', html)
        self.assertIn('?next=/page/', html)


ON_COMMIT = []


class Remember(Action):
    on_commit = True

    def run(self, context):
        ON_COMMIT.append(context.transition.name)


@register_flow
class ThingFlow(Flow):
    name = 'tests.things'
    model = UUIDThing
    states = [('new', 'New'), ('open', 'Open'), ('closed', 'Closed'),
              ('archived', 'Archived')]
    initial = 'new'
    final_states = ['archived']
    transitions = [
        Transition('open', 'new', 'open', actions=[Assign(user='actor')]),
        Transition('note', 'open', 'open', keep_assignment=True,
                   actions=[Remember()]),
        Transition('close', 'open', 'closed', actions=[Remember()]),
        Transition('broken', 'open', 'closed',
                   actions=[Remember(), CallFunction(explode)]),
        Transition('archive', ANY_STATE, 'archived'),
    ]


class FlowStabilityTests(TestCase):
    """Regression tests of the stability review."""

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.flow = get_flow('tests.things')
        cls.viewer = User.objects.create_user('viewer', password='x')
        cls.viewer.user_permissions.add(
            Permission.objects.get(codename='view_uuidthing'))
        cls.nobody = User.objects.create_user('nobody', password='x')
        cls.thing = UUIDThing.objects.create(name='Thing')

    def setUp(self):
        ON_COMMIT.clear()

    def test_reach_is_restrictive_by_default(self):
        self.assertEqual(list(self.flow.get_queryset(self.nobody)), [])
        self.assertEqual(list(self.flow.inbox(self.nobody)), [])
        self.client.force_login(self.nobody)
        detail = reverse('flow_detail', args=[self.flow.name, self.thing.pk])
        self.assertEqual(self.client.get(detail).status_code, 404)
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get(detail).status_code, 200)

    def test_uuid_pks_in_the_inbox(self):
        self.assertEqual(list(self.flow.inbox(self.viewer)), [self.thing])
        self.flow.run(self.thing, 'open', self.viewer)
        row = self.flow.inbox(self.viewer).get()
        self.assertEqual(row.flow_state, 'open')
        self.assertEqual(self.flow.states_for([self.thing]), {self.thing.pk: 'open'})

    def test_second_run_of_the_same_transition_is_refused(self):
        self.flow.run(self.thing, 'open', self.viewer)
        with self.assertRaises(TransitionNotAllowed):
            self.flow.run(self.thing, 'open', self.viewer)

    def test_on_commit_actions_wait_for_the_commit(self):
        self.flow.run(self.thing, 'open', self.viewer)
        with self.captureOnCommitCallbacks(execute=True):
            self.flow.run(self.thing, 'close', self.viewer)
        self.assertEqual(ON_COMMIT, ['close'])

    def test_on_commit_actions_never_run_after_a_rollback(self):
        self.flow.run(self.thing, 'open', self.viewer)
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            with self.assertRaises(RuntimeError):
                self.flow.run(self.thing, 'broken', self.viewer)
        self.assertEqual((ON_COMMIT, callbacks), ([], []))
        self.assertEqual(self.flow.state(self.thing), 'open')

    def test_any_state_and_final_states(self):
        archive = self.flow.get_transition('archive')
        self.assertTrue(self.flow.leaves(archive, 'new'))
        self.assertFalse(self.flow.leaves(archive, 'archived'))
        self.assertTrue(self.flow.is_final('archived'))
        self.assertFalse(self.flow.is_final('closed'))  # archive leaves it

    def test_assignment_is_cleared_unless_kept(self):
        instance = self.flow.run(self.thing, 'open', self.viewer)
        self.assertEqual(instance.assigned_to, self.viewer)
        instance = self.flow.run(self.thing, 'note', self.viewer)
        self.assertEqual(instance.assigned_to, self.viewer)
        instance = self.flow.run(self.thing, 'close', self.viewer)
        self.assertIsNone(instance.assigned_to)

    def test_deleting_the_object_forgets_its_state(self):
        self.flow.run(self.thing, 'open', self.viewer)
        other = UUIDThing.objects.create(name='Other')
        self.flow.run(other, 'open', self.viewer)
        other.delete()
        self.assertEqual(FlowInstance.objects.filter(flow=self.flow.name).count(), 1)

    def test_a_name_cannot_be_taken_twice(self):
        class Impostor(Flow):
            name = 'tests.things'
            model = UUIDThing
            states = [('new', 'New')]
            initial = 'new'
        with self.assertRaises(ImproperlyConfigured):
            register_flow(Impostor)
        register_flow(ThingFlow)  # the same class again is fine

    def test_missing_group_is_a_refusal_not_a_500(self):
        flow = get_flow('tests.country_review')
        editor = get_user_model().objects.create_superuser('root', password='x')
        country = Country.objects.create(name='Peru')
        with self.assertRaises(TransitionNotAllowed):
            flow.run(country, 'submit', editor)  # no "Reviewers" group exists
        self.assertEqual(flow.state(country), 'draft')

    def test_json_safe(self):
        data = json_safe({'when': datetime.date(2026, 1, 31),
                          'file': SimpleUploadedFile('cv.pdf', b'x'),
                          'thing': self.thing})
        self.assertEqual(data, {'when': '2026-01-31', 'file': 'cv.pdf',
                                'thing': 'Thing'})

    @override_settings(ROOT_URLCONF='djgentelella.tests.flows_nourls')
    def test_flow_status_without_the_flow_urls(self):
        request = RequestFactory().get('/page/')
        request.user = self.viewer
        html = Template("{% load gtflows %}{% flow_status thing 'tests.things' %}"
                        ).render(Context({'thing': self.thing, 'request': request}))
        self.assertIn('New', html)
        self.assertNotIn('History', html)

    def test_flow_states_tag(self):
        html = Template("{% load gtflows %}{% flow_states things 'tests.things' as s %}"
                        "{{ s|flow_label:thing.pk }}").render(
            Context({'things': [self.thing], 'thing': self.thing}))
        self.assertEqual(html, 'New')

    def test_flows_are_registered_at_startup(self):
        # demoapp.gtflows is imported by FlowsConfig.ready(), without needing
        # the URLconf.
        self.assertIsNotNone(get_flow('demoapp.CountryApprovalFlow'))


class AttachmentForm(forms.Form):
    attachment = forms.FileField()


@register_flow
class UploadFlow(Flow):
    name = 'tests.uploads'
    model = UUIDThing
    states = [('new', 'New'), ('filed', 'Filed')]
    initial = 'new'
    transitions = [Transition('file', 'new', 'filed', form=AttachmentForm)]


class FlowReviewTests(TestCase):
    """Regression tests of the second review."""

    @classmethod
    def setUpTestData(cls):
        cls.viewer = get_user_model().objects.create_user('viewer', password='x')
        cls.viewer.user_permissions.add(
            Permission.objects.get(codename='view_uuidthing'),
            Permission.objects.get(codename='view_country'))
        cls.thing = UUIDThing.objects.create(name='Thing')

    def setUp(self):
        self.client.force_login(self.viewer)

    def test_a_transition_form_receives_its_files(self):
        url = reverse('flow_transition', args=['tests.uploads', 'file', self.thing.pk])
        self.assertContains(self.client.get(url), 'enctype="multipart/form-data"')
        self.client.post(url, {'flow-attachment': SimpleUploadedFile('cv.pdf', b'x')})
        flow = get_flow('tests.uploads')
        self.assertEqual(flow.state(self.thing), 'filed')
        self.assertEqual(flow.history(self.thing).get().data, {'attachment': 'cv.pdf'})

    def test_a_state_left_only_by_any_state_is_not_final(self):
        class Cancellable(Flow):
            model = Country
            states = [('draft', 'D'), ('review', 'R'), ('cancelled', 'C')]
            initial = 'draft'
            transitions = [Transition('submit', 'draft', 'review'),
                           Transition('cancel', ANY_STATE, 'cancelled')]
        flow = Cancellable()
        self.assertFalse(flow.is_final('review'))
        self.assertTrue(flow.is_final('cancelled'))

    def test_a_pk_the_model_cannot_hold_is_a_404(self):
        for flow, pk in (('tests.country_review', 'abc'),
                         ('tests.things', 'not-a-uuid'), ('tests.things', 'a/b')):
            url = reverse('flow_detail', args=[flow, pk])
            self.assertEqual(self.client.get(url).status_code, 404, url)

    def test_recipients_expand_querysets_and_managers(self):
        group = Group.objects.create(name='Team')
        group.user_set.add(self.viewer)
        context = SimpleNamespace(obj=group, user=None, instance=None)
        self.assertEqual(resolve('field:user_set', context), [self.viewer])
        self.assertEqual(resolve(lambda c: get_user_model().objects.all(), context),
                         [self.viewer])
