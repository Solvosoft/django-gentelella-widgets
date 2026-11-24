"""Optional app that installs the ``pg_trgm`` extension with a migration.

Add ``'djgentelella.search.trigram'`` to ``INSTALLED_APPS`` of a PostgreSQL
project (it needs ``psycopg``) to get typo-tolerant hits in the global search.
The migration runs ``CREATE EXTENSION IF NOT EXISTS pg_trgm``, which needs a
role allowed to create it (pg_trgm is a trusted extension since PostgreSQL 13:
the owner of the database can). On other databases it does nothing. Without
this app the search still detects an extension created by hand.
"""
