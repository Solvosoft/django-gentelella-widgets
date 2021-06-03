from .test_base import WidgetTest
from djgentelella.widgets import wysiwyg as widgets

class TextareaWysiwygTest(WidgetTest):
    widget=widgets.TextareaWysiwyg()
    
    def test_attrs_options(self):
        attrs = self.widget.get_context(name='name', value=None, attrs={})['widget']['attrs']
        
        self.assertEquals(attrs['data-option-video'], "/upload_video")
        self.assertEquals(attrs['data-option-image'], "/upload_image")
        self.assertEquals(attrs['data-option-file'], "/upload_file")

    def test_attrs_class(self):
        attrs = self.widget.get_context(name='name', value=None, attrs={})['widget']['attrs']
        self.assertEquals(attrs['class'], "froala-editor form-control")
    
    def test_render_none(self):
        self.check_render_none(
            self.widget, '<textarea class="form-control froala-editor" cols="40" data-option-file="/upload_file" data-option-image="/upload_image" data-option-video="/upload_video" data-widget="TextareaWysiwyg" name="" rows="10" style="overflow:scroll; max-height:300px"></textarea>')
   
    def test_template_name(self):    
        self.check_template_name(self.widget,'gentelella/widgets/wysiwygtwo.html')
