from djgentelella.groute import register_lookups
from djgentelella.views.storyline import StorylineBuilder


@register_lookups(prefix="storyline2", basename="examplestoryline2")
class StorylineExample(StorylineBuilder):

    def create_options(self):
        options= {
            "data": {
                "datetime_column_name": "date",
                "datetime_format": "%Y-%m-%d",
                "data_column_name": "income"},
            "chart": {
                "datetime_format": "%Y",
                "y_axis_label": "Income2"
            },
            "slider": {
                "start_at_card": "4",
                "title_column_name": "title",
                "text_column_name": "text",
            }}
        return options

    def create_csv(self):
        csv = ['date,income,title,text,,',
               '1984-01-01,48720,,,,\r\n',
               '1985-01-01,49631,,\r\n', # two less columns in this line, this is valid, should be handled by view
               '1986-01-01,51388,,,,\r\n',
               '1987-01-01,52032,,,,\r\n',
               '1988-01-01,52432,,,,\r\n',
               '1989-01-01,53367,Reagan Boom Boom,"Two major underlying factors lead to a weakening U.S. economy—restrictive moves from the Federal Reserve designed to curb inflation, and a depreciating real estate market.",,\r\n',
               '1990-01-01,52684,Hello Downturn My Old Friend,"It’s all over in July, the last month of this period’s economic expansion. When Iraq invades Kuwait in August, oil prices skyrocket, and consumer confidence tanks. We head into a recession.",,\r\n',
               '1991-01-01,51145,,,,\r\n',
               '1992-01-01,50725,,,,\r\n',
               '1993-01-01,50478,Internet FTW,"Okay, technically the internet isn’t acting alone. Alongside this technology boon, the housing market starts to recover, due in part to lower interest rates and energy prices. People start making and spending money again.",,\r\n',
               '1994-01-01,51065,,,,\r\n',
               '1995-01-01,52664,,,,\r\n',
               '1996-01-01,53407,,,,\r\n',
               '1997-01-01,54506,,,,\r\n',
               '1998-01-01,56510,,,,view\r\n',
               '1999-01-01,57909,"Internet, You Have Failed Me","What’s the sound of countless investors sneaking away from Silicon Valley? A dot-com bubble burst. Investors see no path to revenue, dot-coms shut their doors, and the economy slumps. Goodbye, pets.com.",,\r\n',
               '2000-01-01,57790,,,,\r\n',
               '2001-01-01,56531,,,,\r\n']

        for row in csv:
            yield row

