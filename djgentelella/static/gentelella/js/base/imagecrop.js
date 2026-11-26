/**
  ImageCropInput (djgentelella.widgets.imagecrop): crop an image before it
  is uploaded. Cropper.js is loaded on the first file chosen
  (gt_load_script, formwidgets.js); "Apply" swaps the file of the input for
  the cropped one through a DataTransfer, so the form posts it as usual.
  The server validates it again (ImageCropField).
**/
function gt_image_crop(instance) {
    instance.each(function (i, input) {
        if (!gt_widget_once(input, 'Crop')) return;
        var wrapper = input.closest('.gt-image-crop');
        var editor = wrapper.querySelector('.gt-image-crop-editor');
        var source = wrapper.querySelector('.gt-image-crop-source');
        var result = wrapper.querySelector('.gt-image-crop-result');
        var preview = wrapper.querySelector('.gt-image-crop-preview');
        var ratio = parseFloat(input.getAttribute('data-aspect-ratio'));
        var maxWidth = parseInt(input.getAttribute('data-max-width'), 10) || undefined;
        var maxHeight = parseInt(input.getAttribute('data-max-height'), 10) || undefined;
        var outputType = input.getAttribute('data-output-type') || 'image/jpeg';
        var quality = parseFloat(input.getAttribute('data-quality')) || 0.9;
        var cropper = null;
        var objectUrl = null;
        var original = null;

        var close = function () {
            if (cropper) { cropper.destroy(); cropper = null; }
            if (objectUrl) { URL.revokeObjectURL(objectUrl); objectUrl = null; }
            editor.classList.add('d-none');
        };
        var open = function (file) {
            close();
            original = file;
            objectUrl = URL.createObjectURL(file);
            source.src = objectUrl;
            editor.classList.remove('d-none');
            result.classList.add('d-none');
            cropper = new Cropper(source, {
                aspectRatio: isNaN(ratio) ? NaN : ratio,
                viewMode: 1,
                autoCropArea: 1,
                responsive: true
            });
        };

        input.addEventListener('change', function () {
            var file = input.files && input.files[0];
            if (!file || input.dataset.gtCropped === '1') {
                input.dataset.gtCropped = '';
                return;
            }
            if (!/^image\//.test(file.type)) {
                close();  // not an image: the server answers why
                return;
            }
            Promise.all([
                gt_load_style(input.getAttribute('data-cropper-css')),
                gt_load_script(input.getAttribute('data-cropper-js'))
            ]).then(function () { open(file); })
              .catch(function (error) { console.error('ImageCropInput', error); });
        });

        wrapper.querySelector('.gt-image-crop-apply').addEventListener('click', function () {
            if (!cropper) return;
            var canvas = cropper.getCroppedCanvas({
                maxWidth: maxWidth, maxHeight: maxHeight,
                fillColor: outputType === 'image/jpeg' ? '#fff' : 'transparent',
                imageSmoothingQuality: 'high'
            });
            canvas.toBlob(function (blob) {
                if (!blob) return;
                var extension = outputType.split('/')[1].replace('jpeg', 'jpg');
                var name = original.name.replace(/\.[^.]*$/, '') + '.' + extension;
                var cropped = new File([blob], name, {type: outputType});
                var transfer = new DataTransfer();
                transfer.items.add(cropped);
                input.files = transfer.files;
                // Some browsers fire change on that assignment: not a new file.
                input.dataset.gtCropped = '1';
                preview.src = canvas.toDataURL(outputType, quality);
                result.classList.remove('d-none');
                close();
                input.dispatchEvent(new CustomEvent('gt-image-cropped',
                                                    {bubbles: true, detail: {file: cropped}}));
                setTimeout(function () { input.dataset.gtCropped = ''; }, 0);
            }, outputType, quality);
        });
        wrapper.querySelector('.gt-image-crop-rotate').addEventListener('click', function () {
            if (cropper) cropper.rotate(90);
        });
        wrapper.querySelector('.gt-image-crop-reset').addEventListener('click', function () {
            if (cropper) cropper.reset();
        });
        wrapper.querySelector('.gt-image-crop-cancel').addEventListener('click', function () {
            // Keep the file as chosen, uncropped.
            close();
        });
    });
}
