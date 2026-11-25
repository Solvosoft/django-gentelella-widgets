"""Helpers for the browser tests of a project built on djgentelella.

Nothing here imports selenium: the functions take the driver and the
elements a test already has, so the module imports in any environment.

``mouse_click`` is the click a user makes: Bootstrap 5 sets
``scroll-behavior: smooth`` on ``:root``, so a ``scrollIntoView()`` -- the one
WebDriver does before a click, or one of the test's own -- is still moving
when the click lands, and Chrome answers ``ElementClickInterceptedException``
(the point it aimed at now holds another element) or clicks whatever passed
under it. Scrolling without animation first, to the centre of the viewport,
away from the fixed bars of the gentelella layout, leaves the element still
and uncovered::

    from djgentelella.testing import mouse_click

    mouse_click(self.driver, self.driver.find_element(By.CSS_SELECTOR, '#save'))

A live server test starts from a flushed database, without the settings the
migrations load: call :func:`djgentelella.utils.load_default_settings` in its
``setUp``.
"""

__all__ = ['SCROLL_INSTANTLY_JS', 'mouse_click', 'scroll_instantly']

#: Turns off the smooth scrolling of the page and brings ``arguments[0]`` to
#: the centre of the viewport, at once.
SCROLL_INSTANTLY_JS = (
    "var element = arguments[0];"
    "document.documentElement.style.scrollBehavior = 'auto';"
    "if (document.body) { document.body.style.scrollBehavior = 'auto'; }"
    "element.scrollIntoView({block: 'center', inline: 'center',"
    "                        behavior: 'instant'});"
)


def scroll_instantly(driver, element):
    """Bring ``element`` (a WebElement) to the centre of the viewport, with
    the page's smooth scrolling turned off."""
    driver.execute_script(SCROLL_INSTANTLY_JS, element)


def mouse_click(driver, element):
    """Click ``element`` with the mouse (WebDriver's native click, so an
    element covered by another one still fails), after
    :func:`scroll_instantly`. Returns ``element``."""
    scroll_instantly(driver, element)
    element.click()
    return element
