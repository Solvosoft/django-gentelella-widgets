import datetime

from djgentelella.groute import register_lookups
from djgentelella.views.timeline import BaseTimelineView

@register_lookups(prefix="timeline", basename="exampletimeline")
class TimelineExample(BaseTimelineView):
    def get_title(self):
        return {
            'start_date' : datetime.date(year=2021, month=1, day=20),
            'text': {'text': 'Timeline example', 'headline': 'Headline example'}
        }

    def get_events(self):
        return [{
        "media": {
          "url": "https://youtu.be/fSrO91XO1Ck",
          "caption": "",
          "credit": "<a href=\"http://unidiscmusic.com\">Unidisc Music</a>"
        },
        "start_date": "1978",
        "text": {
          "headline": "First Recording",
          "text": "At the age of 15 Houston was featured on Michael Zager's song, Life's a Party."
        }
      },
      {
        "media": {
          "url": "https://youtu.be/_gvJCCZzmro",
          "caption": "A young poised Whitney Houston in an interview with EbonyJet.",
          "credit": "EbonyJet"
        },
        "start_date": "1978",
        "text": {
          "headline": "The Early Years",
          "text": "As a teen Houston's credits include background vocals for Jermaine Jackson, Lou Rawls and the Neville Brothers. She also sang on Chaka Khan's, 'I'm Every Woman,' a song which she later remade for the <i>Bodyguard</i> soundtrack which is the biggest selling soundtrack of all time. It sold over 42 million copies worldwide."
        }
      }]

    def get_scale(self):
        return 'human'

    def get_eras(self):
        return []