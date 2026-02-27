"""
In-memory registry for email template context configurations.

Each registered context maps a template code to the models and extra
variables available when rendering that template. No DB access occurs
during registration — model strings are resolved lazily during
introspection.
"""

_CONTEXT_REGISTRY = {}


def register_context(code, subject, models, exclude=None,
                     extra_variables=None, depth=2,
                     preview_provider=None):
    """Register a template context configuration.

    Args:
        code: Unique string identifier for this context (e.g., 'order_confirmation').
        subject: Default subject template string.
        models: Dict mapping prefix to model string (e.g., {'user': 'auth.User'}).
        exclude: Optional dict mapping prefix to list of field names to exclude.
        extra_variables: Optional dict of extra variable names to descriptions.
        depth: Max depth for model field introspection (default 2).
        preview_provider: Optional dotted path or class for preview data generation.
    """
    _CONTEXT_REGISTRY[code] = {
        'code': code,
        'subject': subject,
        'models': models or {},
        'exclude': exclude or {},
        'extra_variables': extra_variables or {},
        'depth': depth,
        'preview_provider': preview_provider,
    }


def get_context_config(code):
    """Retrieve a registered context configuration by code.

    Args:
        code: The context code to look up.

    Returns:
        Dict with context configuration, or None if not found.
    """
    return _CONTEXT_REGISTRY.get(code)


def get_all_contexts():
    """Return all registered context configurations.

    Returns:
        Dict mapping codes to their configurations.
    """
    return dict(_CONTEXT_REGISTRY)


def clear_registry():
    """Clear all registered contexts. Useful for testing."""
    _CONTEXT_REGISTRY.clear()
