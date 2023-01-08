from django import forms

from djgentelella.forms.forms import GTForm
from djgentelella.widgets import core as genwidgets


class MediaUploadForm(GTForm):
    photo_record = forms.FileField(label='Your photo',
                                   widget=genwidgets.ImageRecordInput(attrs={
                                       'data-width': "30px",
                                       'data-height': "20px"

                                   }))
    video_record = forms.FileField(label='Your video',
                                   widget=genwidgets.VideoRecordInput(attrs={
                                       'data-width': "100px",
                                       'data-height': "200px"

                                   }))
    audio_record = forms.FileField(label='Your audio',
                                   widget=genwidgets.AudioRecordInput)
