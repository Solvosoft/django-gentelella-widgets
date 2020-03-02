from django.shortcuts import render

from djgentelella.elements import StatsCountList
from elements import StatsElement

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

class StatsCountListExample(StatsCountList):
    stats_views = [ClockTime, MemberStats, ClockTime, ClockTime]

def show_top_counts(request):
    counts = StatsCountListExample()
    return render(request, 'dashboard.html', {'counts_views': counts})