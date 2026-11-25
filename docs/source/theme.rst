Theme roller
============

Each Site (:doc:`sites`) can have its own look without anyone writing CSS: a
``djgentelella.models.SiteTheme`` holds

* the Bootstrap colours ``primary``, ``secondary``, ``success`` and
  ``danger``;
* the sidebar's background and text (``sidebar_bg``, ``sidebar_text``);
* the border radius (``border_radius``, 0 to 24 pixels);
* a font out of a fixed list of system font stacks (``font``: ``system``,
  ``sans``, ``humanist``, ``serif``, ``mono``; nothing is downloaded);
* a logo (``logo``): PNG, JPEG, GIF or WebP, at most
  ``GT_THEME_LOGO_MAX_BYTES`` (512 KB). Never SVG.

A blank value keeps the bundled stylesheet's. One theme per Site, plus one
global (``site`` empty) that every Site without its own uses -- the whole
theme, not value by value.

Values, never CSS
-----------------

Every value is typed and validated: a colour is ``#rrggbb`` and nothing else,
the radius an integer in its range, the font a key of the list. The logo is
opened with Pillow, its format must be one of the four and match the
extension of its name, and it is served with the content type of that format
and ``X-Content-Type-Options: nosniff``. The stylesheet is written by
``djgentelella.theme.css.render_css`` from those values, and that writer
checks each value again: a value that is not valid is left out, never copied
into the CSS.

What the stylesheet sets
------------------------

Bootstrap 5 reads its CSS variables at run time, so nothing is recompiled:
``--bs-primary`` and ``--bs-primary-rgb`` (and the other three colours, with
their ``-text-emphasis``, ``-bg-subtle`` and ``-border-subtle``), the link
colours, ``--bs-border-radius`` (and ``-sm``, ``-lg``, ``-xl``),
``--bs-body-font-family``; the variables of ``.btn-<colour>`` and
``.btn-outline-<colour>``, whose hover and active shades are derived from the
colour (and the text, black or white, from its luminance); the active pill,
pagination and checked box; and the sidebar (``.left_col``, its title, menu
and footer).

``{% gt_theme_css %}`` (``{% load gttheme %}``), at the end of the ``head``
block of ``gentelella/base.html``, links ``/gt-theme/<pk>.css?v=<version>``
for the request's Site. Every save of the theme bumps ``version``, so the
stylesheet is served with ``Cache-Control: public, max-age=31536000,
immutable`` (an older ``v`` gets the current theme with ``no-cache``) and an
``ETag``. Which theme a Site uses is cached too, and forgotten on every save
or delete. ``{% gt_theme_logo_url %}`` is the URL of the logo; the sidebar of
``base.html`` shows it instead of the ``sidebar_icon``.

The roller page
---------------

``gt_theme_roller`` (``/gt-theme/``) edits the theme of a Site, or the global
one, chosen at the top (by default the request's Site). It needs
``djgentelella.change_sitetheme`` and ``djgentelella.add_sitetheme``. Each
colour has a text field and a colour picker; as the values change, the page
reloads ``gt_theme_preview`` -- the same writer on the values being edited,
so only valid values reach it -- and the whole page, sidebar included, shows
them before anything is saved. "Remove theme" deletes it: the Site goes back
to the global theme, or to the bundled one.

In Python, ``djgentelella.theme.resolve.get_theme(site)`` is the theme that
applies to a Site and ``resolve_theme(site)`` its ``(pk, version, has_logo)``,
cached.
