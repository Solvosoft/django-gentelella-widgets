///////////////////////////////////////////////
//  PDF Viewer Widget
//  Extends fileupload pattern with PDF.js preview
///////////////////////////////////////////////

$.fn.pdfviewerwidget = function(){
    var md5 = "",
    csrf = getCookie('csrftoken'),
    form_data = [{"name": "csrfmiddlewaretoken", "value": csrf}];

    function calculate_md5(file, chunk_size) {
        var slice = File.prototype.slice || File.prototype.mozSlice || File.prototype.webkitSlice,
          chunks = Math.ceil(file.size / chunk_size),
          current_chunk = 0,
          spark = new SparkMD5.ArrayBuffer();
        function onload(e) {
            spark.append(e.target.result);
            current_chunk++;
            if (current_chunk < chunks) {
                read_next_chunk();
            } else {
                md5 = spark.end();
            }
        }
        function read_next_chunk() {
            var reader = new FileReader();
            reader.onload = onload;
            var start = current_chunk * chunk_size,
            end = Math.min(start + chunk_size, file.size);
            reader.readAsArrayBuffer(slice.call(file, start, end));
        }
        read_next_chunk();
    }

    function validatePDF(file) {
        if (!file) return false;
        if (file.type !== 'application/pdf') return false;
        if (!file.name.toLowerCase().endsWith('.pdf')) return false;
        return true;
    }

    // PDF.js rendering helpers
    var PDF_ZOOM_LEVELS = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0];

    function createPDFViewer(previewEl) {
        var canvas = previewEl.querySelector('.pdfviewer-canvas'),
            canvasContainer = previewEl.querySelector('.pdfviewer-canvas-container'),
            loadingEl = previewEl.querySelector('.pdfviewer-loading'),
            errorEl = previewEl.querySelector('.pdfviewer-error'),
            errorMsgEl = previewEl.querySelector('.pdfviewer-error-message'),
            pageNumEl = previewEl.querySelector('.pdfviewer-page-num'),
            pageCountEl = previewEl.querySelector('.pdfviewer-page-count'),
            zoomLevelEl = previewEl.querySelector('.pdfviewer-zoom-level');

        var state = {
            pdfDoc: null,
            pageNum: 1,
            pageRendering: false,
            pageNumPending: null,
            zoomIndex: 2,
            scale: PDF_ZOOM_LEVELS[2]
        };

        function showLoading() {
            if (loadingEl) loadingEl.classList.remove('d-none');
        }
        function hideLoading() {
            if (loadingEl) loadingEl.classList.add('d-none');
        }
        function showError(msg) {
            if (errorEl && errorMsgEl) {
                errorMsgEl.textContent = msg;
                errorEl.classList.remove('d-none');
            }
        }
        function hideError() {
            if (errorEl) errorEl.classList.add('d-none');
        }
        function updateZoomDisplay() {
            if (zoomLevelEl) {
                zoomLevelEl.textContent = Math.round(state.scale * 100) + '%';
            }
        }

        function renderPage(num) {
            if (!state.pdfDoc || !canvas) return Promise.resolve();
            state.pageRendering = true;

            return state.pdfDoc.getPage(num).then(function(page) {
                var viewport = page.getViewport({ scale: state.scale });
                var ctx = canvas.getContext('2d');
                canvas.height = viewport.height;
                canvas.width = viewport.width;

                return page.render({
                    canvasContext: ctx,
                    viewport: viewport
                }).promise.then(function() {
                    state.pageRendering = false;
                    if (pageNumEl) pageNumEl.textContent = num;
                    state.pageNum = num;

                    if (state.pageNumPending !== null) {
                        var pending = state.pageNumPending;
                        state.pageNumPending = null;
                        return renderPage(pending);
                    }
                });
            });
        }

        function queueRenderPage(num) {
            if (state.pageRendering) {
                state.pageNumPending = num;
            } else {
                renderPage(num);
            }
        }

        // Bind controls
        var prevBtn = previewEl.querySelector('.pdfviewer-prev'),
            nextBtn = previewEl.querySelector('.pdfviewer-next'),
            zoomInBtn = previewEl.querySelector('.pdfviewer-zoom-in'),
            zoomOutBtn = previewEl.querySelector('.pdfviewer-zoom-out'),
            fitWidthBtn = previewEl.querySelector('.pdfviewer-fit-width');

        if (prevBtn) {
            prevBtn.addEventListener('click', function() {
                if (state.pdfDoc && state.pageNum > 1) {
                    state.pageNum--;
                    queueRenderPage(state.pageNum);
                }
            });
        }
        if (nextBtn) {
            nextBtn.addEventListener('click', function() {
                if (state.pdfDoc && state.pageNum < state.pdfDoc.numPages) {
                    state.pageNum++;
                    queueRenderPage(state.pageNum);
                }
            });
        }
        if (zoomInBtn) {
            zoomInBtn.addEventListener('click', function() {
                if (state.zoomIndex < PDF_ZOOM_LEVELS.length - 1) {
                    state.zoomIndex++;
                    state.scale = PDF_ZOOM_LEVELS[state.zoomIndex];
                    updateZoomDisplay();
                    queueRenderPage(state.pageNum);
                }
            });
        }
        if (zoomOutBtn) {
            zoomOutBtn.addEventListener('click', function() {
                if (state.zoomIndex > 0) {
                    state.zoomIndex--;
                    state.scale = PDF_ZOOM_LEVELS[state.zoomIndex];
                    updateZoomDisplay();
                    queueRenderPage(state.pageNum);
                }
            });
        }
        if (fitWidthBtn) {
            fitWidthBtn.addEventListener('click', function() {
                if (!state.pdfDoc || !canvasContainer) return;
                state.pdfDoc.getPage(state.pageNum).then(function(page) {
                    var containerWidth = canvasContainer.offsetWidth - 40;
                    var viewport = page.getViewport({ scale: 1 });
                    state.scale = containerWidth / viewport.width;

                    // Find closest zoom level index
                    var closestIndex = 0;
                    var minDiff = Math.abs(PDF_ZOOM_LEVELS[0] - state.scale);
                    for (var i = 1; i < PDF_ZOOM_LEVELS.length; i++) {
                        var diff = Math.abs(PDF_ZOOM_LEVELS[i] - state.scale);
                        if (diff < minDiff) {
                            minDiff = diff;
                            closestIndex = i;
                        }
                    }
                    state.zoomIndex = closestIndex;
                    updateZoomDisplay();
                    queueRenderPage(state.pageNum);
                });
            });
        }

        return {
            loadPDF: function(url) {
                if (!url || !canvas) return Promise.reject(new Error('No URL or canvas'));
                showLoading();
                hideError();

                // pdf.js 6 dropped the bare-string shorthand: a string, an
                // absolute string and even a URL object are all rejected with
                // "expected either `data`, `range`, or `url` parameter".
                return pdfjsLib.getDocument({url: url}).promise.then(function(pdfDoc) {
                    state.pdfDoc = pdfDoc;
                    state.pageNum = 1;
                    if (pageCountEl) pageCountEl.textContent = pdfDoc.numPages;
                    hideLoading();
                    return renderPage(1);
                }).catch(function(error) {
                    hideLoading();
                    console.error('Error loading PDF:', error);
                    showError(gettext('Failed to load PDF file.'));
                    throw error;
                });
            },
            destroy: function() {
                if (state.pdfDoc) {
                    state.pdfDoc.destroy();
                    state.pdfDoc = null;
                }
            }
        };
    }

    // Widget initialization (follows fileupload.widget.js pattern)
    $.each($(this), function(i, e){
        var $this = $(e);
        var $parentdiv = $this.closest('.pdfviewer-widget');
        var input_token = $this.data('inputtoken');

        // Initialize PDF viewer if preview section exists
        var previewSection = $parentdiv.find('.pdfviewer-preview')[0];
        var pdfViewer = previewSection ? createPDFViewer(previewSection) : null;

        var obj = {
            parentdiv: $this.closest('.input-group'),
            upload_url: $this.data('href'),
            field_name: $this.attr('name'),
            div_message: $parentdiv.find('.' + input_token + '_messages'),
            div_process: $parentdiv.find('.' + input_token + '_progress'),
            div_download: $parentdiv.find('#download_' + input_token),
            div_remove: $parentdiv.find('#remove_' + input_token),
            div_preview: $parentdiv.find('.pdfviewer-preview'),
            url_done: $this.data('done'),
            current_icon: 'eyes',
            input_token: input_token,
            input_field: $parentdiv.find('input[name="' + input_token + '"]'),
            default_value: "",
            pdfviewertoggle: $parentdiv.find('.pdfviewer-toggle'),
            uploadfilecontent: $parentdiv.find('.uploadfilecontent'),
            removecheck: $parentdiv.find('input[data-widget="CheckboxInput"]'),
            pdfViewer: pdfViewer,

            change_fn: function(e){
                var parent = e;
                return function(event){
                    let current_value = parent.input_field.val();
                    if(current_value.length == 0){
                        current_value = parent.default_value;
                    }
                    try{
                        let data = JSON.parse(current_value);
                        parent.render_widget_data(data);
                    }catch(ex) {
                        // do nothing
                    }
                };
            },

            icon_action_toggle: function(){
                if(this.current_icon === 'eyes'){
                    this.show_upload();
                }else{
                    this.show_eyes();
                }
            },

            show_eyes: function(){
                this.current_icon = 'eyes';
                this.change_icon_toggle('fa fa-eye');
            },

            show_upload: function(){
                this.current_icon = 'upload';
                this.change_icon_toggle('fa fa-cloud-upload');
            },

            render_widget_data: function(data){
                var parent = this;
                if("token" in data){
                    parent.uploadfilecontent.hide();
                    parent.div_download.hide();
                    parent.div_remove.hide();
                    parent.div_message.show();
                    parent.div_message.html(data.display_name);
                    parent.div_preview.addClass('d-none');
                    parent.show_upload();
                }else if("url" in data){
                    parent.div_download.show();
                    parent.div_remove.show();
                    parent.div_message.show();
                    parent.uploadfilecontent.hide();
                    parent.div_download.find('a')[0].href = data.url;
                    parent.div_message.html(data.display_name);
                    parent.show_upload();

                    // Load PDF preview
                    if(parent.pdfViewer){
                        parent.div_preview.removeClass('d-none');
                        parent.pdfViewer.loadPDF(data.url).catch(function(err){
                            console.error('Failed to load PDF preview:', err);
                        });
                    }
                }else{
                    parent.div_download.hide();
                    parent.div_remove.hide();
                    parent.uploadfilecontent.show();
                    parent.div_message.hide();
                    parent.div_preview.addClass('d-none');
                    parent.show_eyes();
                }
            },

            change_icon_toggle: function(touseclass){
                this.pdfviewertoggle.find('i').removeClass();
                this.pdfviewertoggle.find('i').addClass(touseclass);
            },

            init: function(){
                $this.attr("required", false);
                this.div_message.hide();
                this.div_remove.hide();
                var parent = this;

                this.pdfviewertoggle.on('click', function(){
                    parent.uploadfilecontent.toggle();
                    parent.div_message.toggle();
                    parent.icon_action_toggle();
                });

                this.input_field[0].onchange = this.change_fn(this);
                this.default_value = this.input_field.val();
                if(this.default_value !== ""){
                    this.input_field.trigger('change');
                }

                this.removecheck.on('ifToggled', function(event){
                    try {
                        let current_data = JSON.parse(parent.input_field.val());
                        if(this.checked){
                            current_data['actions'] = "delete";
                        }else{
                            if('actions' in current_data) delete current_data.actions;
                        }
                        parent.input_field.val(JSON.stringify(current_data));
                    } catch(ex) {}
                });

                $this.fileupload({
                    url: parent.upload_url,
                    dataType: "json",
                    maxChunkSize: 100000,
                    formData: form_data,
                    dropZone: $this,
                    add: function(e, data) {
                        if (!validatePDF(data.files[0])) {
                            Swal.fire(
                                gettext('Invalid file'),
                                gettext('Only PDF files are allowed.'),
                                'error'
                            );
                            return;
                        }
                        parent.div_message.empty();
                        form_data.splice(1);
                        calculate_md5(data.files[0], 100000);
                        data.paramName = 'file';
                        data.submit();
                        parent.uploadfilecontent.hide();
                        parent.div_message.show();
                        parent.div_message.html(data.files[0].name);
                    },
                    chunkdone: function(e, data) {
                        if (form_data.length < 2) {
                            form_data.push(
                                {"name": "upload_id", "value": data.result.upload_id}
                            );
                        }
                        var progress = parseInt(data.loaded / data.total * 100.0, 10);
                        parent.div_process.text(progress + "%");
                    }
                }).bind('fileuploaddone', function(e, data) {
                    parent.input_field.val(JSON.stringify(
                        {'token': data.result.upload_id,
                         'display_name': data.files[0].name}));
                    parent.input_field.trigger('change');
                    $.ajax({
                        type: "POST",
                        url: parent.url_done,
                        data: {
                            csrfmiddlewaretoken: csrf,
                            upload_id: data.result.upload_id,
                            md5: md5
                        },
                        dataType: "json",
                        success: function(data) {
                            parent.div_process.html(' <i class="fa fa-check text-success"></i>');
                        }
                    });
                }).bind('fileuploadchunkfail', function(e, data) {
                    parent.resetEmpty();
                    Swal.fire(
                        gettext('Upload failed'),
                        data.errorThrown,
                        'error'
                    );
                });

                // Load initial PDF if exists
                var initialUrl = $parentdiv.data('pdf-url');
                if (initialUrl && parent.pdfViewer) {
                    parent.pdfViewer.loadPDF(initialUrl).catch(function(err) {
                        console.error('Failed to load initial PDF:', err);
                    });
                }
            },

            resetEmpty: function(){
                this.div_message.html("");
                this.div_message.hide();
                this.div_download.hide();
                this.div_remove.hide();
                this.uploadfilecontent.show();
                this.div_preview.addClass('d-none');
            },

            addRemote: function(item){
                this.input_field.val(JSON.stringify(item));
                this.input_field.trigger('change');
            }
        };
        obj.init();
        $this.data('pdfViewerWidget', obj);
    });
};

///////////////////////////////////////////////
//  End PDF Viewer Widget
///////////////////////////////////////////////
