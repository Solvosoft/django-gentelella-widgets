from django.template.loader import render_to_string


class PalleteWidget:
    def __init__(self, context):
        self.context = context

    def render(self):
        return  render_to_string('gentelella/menu/palette.html', context=self.context)

    def get_menu_item(self):
        dev = {
            'id': "fsb_%s"%self.context['item'].id,
            'title': 'Help',
            'link': "#content_%s"%self.context['id'],
            'divref': "content_%s"%self.context['id'],
            'icon': self.context['item'].icon
        }
        return """
            <a id="%(id)s" title="%(title)s" aria-controls="divref" data-toggle="collapse" aria-expanded="false" data-target="%(link)s" href="%(link)s">
      <span class="%(icon)s" aria-hidden="true"></span></a>
        """%dev