from django.utils.safestring import mark_safe

class Element:
    def __init__(self, position, brothers):
        self.position = position
        self.brothers = brothers
        if brothers == 0:
            raise Exception("Not allowed 0 elements on this class")

    def load_data(self):
        pass

    def get_columns(self):
        pos = int(12/self.brothers)
        if pos<2:
            pos = 2
        pos_sm = pos*2
        if pos_sm > 12:
            pos_sm = 12
        return "col-md-%d col-sm-%d"%(pos,pos_sm)

class StatsElement(Element):
    def render(self):
        self.load_data()
        dev = self.get_top()
        dev += self._get_count()
        dev += self.get_bottom()
        return  dev

    def get_top(self):
        dev = """<span class="count_top">%s %s</span>"""%(
            self._get_top_icon(),
            self.get_top_text()
        )
        return dev

    def get_bottom(self):
        dev = """
        <span class="count_bottom"><i class="%s">%s %s</i> %s</span>
        """%(
            self.get_bottom_color(),
            self._get_bottom_icon(),
            self.get_bottom_icon_text(),
            self.get_bottom_text()
        )
        return dev

    def get_bottom_icon_text(self):
        return ""
    def get_top_icon(self):
        return ""
    def get_top_text(self):
        return ""

    def get_count(self):
        return ""

    def get_count_color(self):
        return ""


    def get_bottom_color(self):
        return "green"

    def get_bottom_text(self):
        return ""

    def get_bottom_icon(self):
        return ""

    def _get_count(self):
        return """<div class="count %s">%s</div>"""%(
            self.get_count_color(),
            self.get_count()
        )
    def _get_top_icon(self):
        icon = self.get_top_icon()
        if icon:
            return '<i class="%s"></i>'%(icon,)
        return ""

    def _get_bottom_icon(self):
        icon = self.get_bottom_icon()
        if icon:
            return '<i class="%s"></i>'%(icon,)
        return ""


class BoxTileElement(Element):
    def get_icon(self):
        return ""
    def get_number(self):
        return ""
    def get_title(self):
        return ""
    def get_subtitle(self):
        return ""

    def render(self):
        return """
<div class="animated flipInY">
<div class="tile-stats">
<div class="icon"><i class="%(icon)s"></i></div>
<div class="count">%(number)s</div>
<h3>%(title)s</h3>
<p>%(subtitle)s</p>
</div>
</div>
        """%{
            'icon': self.get_icon(),
            'number': self.get_number(),
            'title': self.get_title(),
            'subtitle': self.get_subtitle()

        }



class BaseListElement:
    stats_views = []
    css_class = ''
    css_class = ''

    def render(self):
        dev = """<div class="row"><div class="%s">"""%self.css_class
        for i, stat in enumerate(self.stats_views):
            view = stat(i, len(self.stats_views))
            dev += '<div class="'+view.get_columns()+' tile_stats_count">'
            dev += view.render()
            dev += '</div>'
        dev += "</div></div>"
        return mark_safe(dev)

class StatsCountList(BaseListElement):
    css_class = 'tile_count'

class BoxStatsCountList(BaseListElement):
    css_class = 'tile_stats'