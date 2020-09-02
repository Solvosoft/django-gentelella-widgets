import json

from django.template.loader import render_to_string
from django.templatetags import static

from djgentelella.forms.models import HelpForm


class PalleteWidget:
    def __init__(self, context):
        self.context = context

    def render(self):
        return render_to_string('gentelella/menu/palette.html', context=self.context)

    def render_js(self):
        view_name = self.context['context']['request'].resolver_match.view_name
        if self.context['item'].reversed_args:
            help_url = self.context['item'].reversed_args
        else:
            help_url = ''
        permissions = {}
        if self.context['item'].reversed_kwargs:
            item_permissions =self.context['item'].reversed_kwargs.split(',')
        else:
            item_permissions = ["djgentelella.add_help",  "djgentelella.change_help",
                                "djgentelella.view_help", "djgentelella.delete_help"]

        for item in item_permissions:
            permissions[item] = self.context['context']['request'].user.has_perm(item)

        data = {
            'id_view': view_name,
            "help_url": help_url,
            "permissions": permissions
        }
        return """
<script>document.help_widget=%(data)s; 
 var menu=$("#fsb_%(item_pk)s");
 $(document).ready(function(){
    $('#helper_box').helper_box("%(id)s");
 });
</script>    
        """%{'data':json.dumps(data),
             'id': self.context['id'],
             'item_pk': self.context['item'].pk  }

    def render_external_html(self):
        self.context['form'] = HelpForm()
        return render_to_string('gentelella/menu/palette_modal.html', context=self.context)

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