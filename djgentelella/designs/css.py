"""Cleaning of ``assets.css``, the stylesheet a design document carries.

The CSS of a page is data anyone with ``change_page`` writes, and the page
serves it inside a ``<style>`` to everyone who opens it. ``assets.js`` has a
gate (``GT_DESIGNS_ALLOW_JS`` and a publisher with ``publish_js``); the CSS
is cleaned instead, so plain styling keeps working on every page:

* comments go (they could split a keyword: ``expr/**/ession(``);
* CSS escapes of letters and digits are decoded first (``@\\69mport``);
* ``@import`` rules go -- the page would load a stylesheet from anywhere;
* ``expression(``, ``-moz-binding``, ``behavior:`` and the ``javascript:``,
  ``vbscript:`` and ``livescript:`` schemes are neutralized by renaming
  them, which makes the declaration invalid;
* the steps repeat until nothing changes, so removing a rule cannot join
  the text around it into a new one (``@im@import x;port``);
* the engine then escapes ``</`` and ``<!--``, so nothing closes the tag.

A page whose publisher may serve ``assets.js`` gets its CSS as written: that
publisher can already run any script on it.
"""
import re

#: Characters CSS lets a keyword be split with that browsers ignore.
_GAP = r'[\s\x00]*'


def _word(word):
    return _GAP.join(re.escape(char) for char in word)


_COMMENT = re.compile(r'/\*.*?(?:\*/|$)', re.S)
_ESCAPE = re.compile(r'\\(?:([0-9a-fA-F]{1,6})[ \t\r\n\f]?|([^\r\n\f0-9a-fA-F]))')


def _escaped(char):
    r"""``char`` itself, ``\char`` or its hex escape (``\3a``, ``\00003a ``)."""
    return r'(?:\\?%s|\\0{0,4}%x[ \t\r\n\f]?)' % (re.escape(char), ord(char))


_IMPORT = re.compile(_escaped('@') + _GAP + _word('import') + r'[^;{}]*;?', re.I)
_BLOCKED = re.compile('|'.join([
    _word('expression') + _GAP + '(?=%s)' % _escaped('('),
    _word('-moz-binding'),
    '(?:%s)%s(?=%s)' % ('|'.join(_word(word) for word in (
        'behavior', 'javascript', 'vbscript', 'livescript')), _GAP, _escaped(':')),
]), re.I)

#: What an escape is decoded to: the letters and digits a keyword is spelled
#: with. ``\:`` and the like stay, they mean something in a selector.
_PLAIN = re.compile(r'[A-Za-z0-9]')


def _decode(match):
    code, char = match.groups()
    if code is not None:
        value = int(code, 16)
        char = chr(value) if 0 < value < 0x110000 else ''
    return char if _PLAIN.fullmatch(char or '_') else match.group(0)


def _clean_once(css):
    css = css.replace('\x00', '')
    css = _COMMENT.sub('', css)
    css = _ESCAPE.sub(_decode, css)
    css = _IMPORT.sub('', css)
    return _BLOCKED.sub('blocked', css)


def clean_css(css):
    """``css`` without what can load or run code; see the module.

    Removing a rule joins the text around it (``@im@import x;port`` becomes
    ``@import``), so the cleaning repeats until a pass changes nothing. Every
    step that changes the text makes it shorter, so this ends.
    """
    if not isinstance(css, str):
        return ''
    while True:
        cleaned = _clean_once(css)
        if cleaned == css:
            return cleaned
        css = cleaned
