from django.db import models


class ObjectQuerySet(models.QuerySet):
    # Non-deleted records
    def alive(self):
        return self.filter(is_deleted=False)

    # Only deleted records
    def dead(self):
        return self.filter(is_deleted=True)

    # Overridden delete (soft delete)
    def delete(self):
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

