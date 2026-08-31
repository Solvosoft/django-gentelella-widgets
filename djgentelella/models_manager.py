from django.contrib.contenttypes.models import ContentType
from django.db import models


class ObjectQuerySet(models.QuerySet):
    # Non-deleted records
    def alive(self):
        return self.filter(is_deleted=False)

    # Only deleted records
    def dead(self):
        return self.filter(is_deleted=True)

    # Overridden delete (soft delete). Creates the Trash rows too: a bulk
    # soft-delete that skips them leaves objects marked is_deleted with no way
    # to find or restore them from the trash screen.
    def delete(self, user=None, related_objects=None):
        # Circular import: djgentelella.models imports this module.
        from djgentelella.models import (  # noqa: PLC0415
            Trash, TrashRelation, relation_targets,
        )

        content_type = ContentType.objects.get_for_model(self.model)
        rows = [
            Trash(
                content_type=content_type,
                object_id=pk,
                object_repr=str(repr_)[:200],
                deleted_by=user,
            )
            for pk, repr_ in ((obj.pk, obj) for obj in self)
        ]
        # ignore_conflicts: re-deleting something already in the trash keeps
        # the original row (unique_together on content_type/object_id).
        Trash.objects.bulk_create(rows, ignore_conflicts=True)

        if related_objects is not None:
            # ignore_conflicts leaves pre-existing rows without a pk in
            # `rows`, so the standing entries are fetched back; only those
            # with no context yet get the relations (first deletion wins,
            # same rule as the instance-level delete()).
            targets = relation_targets(related_objects)
            trash_rows = Trash.objects.filter(
                content_type=content_type,
                object_id__in=[row.object_id for row in rows],
                gt_relations__isnull=True,
            )
            TrashRelation.objects.bulk_create([
                TrashRelation(
                    trash=trash, content_type=ctype, object_id=object_id
                )
                for trash in trash_rows
                for ctype, object_id in targets
            ])

        return super().update(is_deleted=True)

    # Permanent deletion
    def hard_delete(self):
        return super().delete()

    # Bulk restore
    def restore(self):
        return self.update(is_deleted=False)


class ObjectManager(models.Manager):
    # Only alive objects by default
    def get_queryset(self):
        return ObjectQuerySet(self.model, using=self._db).alive()


class AllObjectsManager(models.Manager):
    # Explicit access to all objects
    def get_queryset(self):
        return ObjectQuerySet(self.model, using=self._db)


class DeletedObjectsManager(models.Manager):
    # Only deleted objects
    def get_queryset(self):
        return ObjectQuerySet(self.model, using=self._db).dead()
