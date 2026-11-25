"""Theme roller: the look of each Site without touching CSS.

A :class:`~djgentelella.models.SiteTheme` holds Bootstrap's colours, the
sidebar's, the border radius, a font and a logo for one Site (or for every
Site without its own: ``site=NULL``). ``{% gt_theme_css %}`` in ``base.html``
links the stylesheet written from it (:mod:`djgentelella.theme.css`), at a URL
with the theme's version: cached for a year, fetched again when it is saved.
The page ``theme_roller`` edits it with a live preview.

The Site rule is that of :mod:`djgentelella.sites`, for the whole theme: a
Site's theme replaces the global one; a blank value is the default of the
bundled stylesheet.
"""
