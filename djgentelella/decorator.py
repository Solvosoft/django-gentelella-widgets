from django.utils.html import escape

def add_required_label_tag(original_function):
  """Adds the 'required' CSS class and an asterisks to required field labels.
    Use fieldname id you want to add a specific css class in """
  def required_label_tag(self, contents=None, attrs=None):
    contents = contents or escape(self.label)

    #fieldname = self.field.__class__.__name__
    if self.field.required:
      if not self.label.endswith(" *"):
        self.label += " *"
        contents += " *"
      attrs = {'class': 'required'}
    # if attrs and fieldname == 'CharField':
    #     attrs.update({'class':'control-label' + attrs['class']})
    return original_function(self, contents, attrs)
  return required_label_tag



def decorate_bound_field():
  from django.forms.forms import BoundField
  BoundField.label_tag = add_required_label_tag(BoundField.label_tag)