from django.urls import reverse_lazy

from djgentelella.widgets.tinymce import EditorTinymce


class EmailEditorTinymce(EditorTinymce):
    """TinyMCE editor whose image/video uploads go to the
    async_notification endpoints.

    Images are stored as :class:`AttachedFile` records and referenced by a
    ``preview-file/<pk>`` URL, which is rewritten to an inline ``cid:``
    attachment at send time. This makes pasted/uploaded images embed in the
    email itself instead of hot-linking a media URL.
    """

    def __init__(self, attrs=None, extraskwargs=True):
        super().__init__(attrs=attrs, extraskwargs=extraskwargs)
        # Keep the base widget name so the existing TinyMCE JS initializer
        # runs (there is no JS handler registered for the subclass name);
        # it reads the upload URLs from data-option-image/video below.
        self.attrs['data-widget'] = 'EditorTinymce'
        self.attrs['data-option-image'] = reverse_lazy(
            'async_notification:async_upload_image')
        self.attrs['data-option-video'] = reverse_lazy(
            'async_notification:async_upload_video')
