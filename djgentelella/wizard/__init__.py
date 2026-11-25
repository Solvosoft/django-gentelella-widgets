"""Forms in several steps with a progress bar and drafts.

:class:`~djgentelella.wizard.views.GTWizardView` and
:class:`~djgentelella.wizard.views.Step`; the drafts are
:class:`djgentelella.models.WizardDraft` rows or live in the session
(:mod:`djgentelella.wizard.storage`). Docs: ``docs/source/wizard.rst``.

Imported lazily: :mod:`djgentelella.models` imports
:mod:`djgentelella.wizard.conf` while the app registry loads.
"""

from importlib import import_module

__all__ = ['GTWizardView', 'Step', 'WizardConflict']


def __getattr__(name):
    if name in __all__:
        return getattr(import_module('djgentelella.wizard.views'), name)
    raise AttributeError(name)
