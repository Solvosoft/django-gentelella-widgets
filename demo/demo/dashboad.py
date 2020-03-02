from django.shortcuts import render

from djgentelella.elements import StatsCountList
from elements import StatsElement, BoxStatsCountList, BoxTileElement


class MemberStats(StatsElement):
    def get_top_icon(self):
        return "fa fa-user"
    def get_top_text(self):
        return " Total Males"
    def get_count(self):
        return "2,500"

    def get_count_color(self):
        return 'green'

    def get_bottom_color(self):
        return "red"

    def get_bottom_text(self):
        return "From last Week"

    def get_bottom_icon(self):
        return "fa fa-sort-asc"
    def get_bottom_icon_text(self):
        return "20%"

class ClockTime(StatsElement):
    def get_top_icon(self):
        return "fa fa-clock-o"
    def get_top_text(self):
        return "Average Time"
    def get_count(self):
        return "123.50"
    def get_bottom_icon_text(self):
        return "2%"
    def get_bottom_color(self):
        return "green"

    def get_bottom_text(self):
        return "From last Week"

    def get_bottom_icon(self):
        return "fa fa-sort-asc"


class SignupsBox(BoxTileElement):
    def get_icon(self):
        return "fa fa-caret-square-o-right"
    def get_number(self):
        return "179"
    def get_title(self):
        return "New Sign ups"
    def get_subtitle(self):
        return "Lorem ipsum psdea itgum rixt."

class StatsCountListExample(StatsCountList):
    stats_views = [ClockTime, MemberStats, ClockTime, ClockTime]

class BoxTileElementExample(BoxStatsCountList):
    stats_views = [SignupsBox, SignupsBox, SignupsBox,SignupsBox ]


def show_top_counts(request):
    counts = StatsCountListExample()
    tile_views = BoxTileElementExample()
    return render(request, 'dashboard.html', {'counts_views': counts, 'tile_views': tile_views})