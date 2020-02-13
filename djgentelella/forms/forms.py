from django import forms

# "'<tr%(html_class_attr)s><th>%(label)s</th><td>%(errors)s%(field)s%(help_text)s</td></tr>'"
class CustomForm(forms.Form):

    def as_plain(self):
        "Returns this form rendered as HTML <tr>s -- excluding the <table></table>."

        return self._html_output(
            normal_row='<div %(html_class_attr)s >%(label)s%(errors)s%(field)s%(help_text)s</div>',
            error_row='%s',
            row_ender=' ',
            help_text_html='<br /><span class="helptext">%s</span>',
            errors_on_separate_row=False)

    def as_inline(self):
            "Return this form rendered as HTML <tr>s -- excluding the <table></table>."
            return self._html_output(
                normal_row='<div class="form-group"><span class="">%(label)s</span> %(field)s%(help_text)s</div>',
                error_row='%s',
                row_ender='</div>',
                help_text_html=' <span class="helptext">%s</span>',
                errors_on_separate_row=False,
            )

    def as_horizontal(self):
            "Return this form rendered as HTML <tr>s -- excluding the <table></table>."
            return self._html_output(
                normal_row='<div class="form-group row"><span class="col-sm-3">%(label)s</span> <div class="col-sm-9">%(field)s%(help_text)s</div></div>',
                error_row='%s',
                row_ender='</div>',
                help_text_html=' <span class="helptext">%s</span>',
                errors_on_separate_row=False,
            )

