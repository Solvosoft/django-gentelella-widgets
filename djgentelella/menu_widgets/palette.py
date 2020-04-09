import json

from django.template.loader import render_to_string


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
            for item in self.context['item'].reversed_kwargs.split(','):
                permissions[item] = self.context['context']['request'].user.has_perm(item)

        data = {
            'id_view': view_name,
            "help_url": help_url,
            "permissions": permissions
        }
        return """
<script>document.help_widget=%(data)s; 
 var menu=$("#fsb_%(item_pk)s");
 var menuoffset=menu.offset();
 console.log(menuoffset);
 $("#content_%(id)s").css({'position': 'fixed', 'top':  menuoffset.top-$("#content_%(id)s").height()-10, 'left': menuoffset.left, 'z-index': 1000});
 $("#expand_%(id)s").on('click', function(){
    if($("#content_%(id)s").hasClass("col-md-3")){
        $("#content_%(id)s").addClass("col-md-10");
        $("#content_%(id)s").removeClass("col-md-3");

        $("#expand_%(id)s i").removeClass("fa-arrows-alt");
        $("#expand_%(id)s i").addClass("fa-minus");
    }else{
        $("#content_%(id)s").addClass("col-md-3");
        $("#content_%(id)s").removeClass("col-md-10");
        $("#expand_%(id)s i").removeClass("fa-minus");
        $("#expand_%(id)s i").addClass("fa-arrows-alt");
    }
 });

</script>    
        """%{'data':json.dumps(data),
             'id': self.context['id'],
             'item_pk': self.context['item'].pk
             }

    def render_external_html(self):
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