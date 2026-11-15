# The flow models moved to their own app, djgentelella.flows (label
# ``gtflows``), with migrations of its own. This migration created
# FlowInstance, FlowTransitionLog and FlowVote here; as the flow engine was
# never released, its history was rewritten instead of adding a migration that
# deletes them. It stays, empty, so the migrations after it keep their
# dependency. A database that had applied the old version keeps three orphan
# tables (djgentelella_flowinstance, _flowtransitionlog, _flowvote), safe to
# drop by hand.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('djgentelella', '0020_trashrelation'),
    ]

    operations = []
