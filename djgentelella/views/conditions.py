"""``ConditionRequiredMixin``: a class-based view guarded by a condition.

It is re-exported by :mod:`djgentelella.authorization`, which imports it on
first access: ``AccessMixin``'s module imports the auth models, and the
authorization module must load before the app registry is ready.
"""

from django.contrib.auth.mixins import AccessMixin
from django.core.exceptions import ImproperlyConfigured

from djgentelella.authorization import evaluate_condition


class ConditionRequiredMixin(AccessMixin):
    """A class-based view that needs ``condition`` to hold.

    Anonymous users who fail are sent to the login page; signed-in ones get
    a 403 (``AccessMixin.handle_no_permission``).
    """

    condition = None

    def get_condition(self):
        if self.condition is None:
            raise ImproperlyConfigured(
                '%s needs a condition: set condition or override get_condition().'
                % self.__class__.__name__)
        return self.condition

    def get_condition_object(self):
        """The object the condition is checked against; none by default."""
        return None

    def has_condition(self):
        return evaluate_condition(self.get_condition(), self.request,
                                  self.get_condition_object())

    def dispatch(self, request, *args, **kwargs):
        if not self.has_condition():
            return self.handle_no_permission()
        return super().dispatch(request, *args, **kwargs)
