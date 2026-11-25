"""``{{ text|markdown }}``: Markdown shown as cleaned HTML
(:func:`djgentelella.markdown.render_markdown`)."""

from django import template

from djgentelella.markdown import render_markdown

register = template.Library()


@register.filter(name='markdown')
def markdown_filter(text):
    return render_markdown(text)
