// Escape a plain transcription string before handing it to TinyMCE's
// insertContent (which parses HTML) so no markup gets injected.
function voice_escape_html(text){
    return String(text)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
}

// TinyMCE editor with a microphone button in its own toolbar for voice
// dictation. Uses the progressive engine (createProgressiveVoiceEngine): each
// finalized speech segment is transcribed and inserted at the cursor via
// editor.insertContent as the user keeps speaking; the authoritative whole-file
// result replaces the preview on stop.
function build_voice_editor_tinymce(instance){
    $(instance).removeAttr('required');

    let mic_svg = '<svg width="24" height="24" viewBox="0 0 24 24">' +
        '<path fill-rule="nonzero" d="M12 15a3 3 0 0 0 3-3V6a3 3 0 1 0-6 0v6a3 3 0 0 0 3 3zm5-3a5 5 0 0 1-10 0H5a7 7 0 0 0 6 6.92V22h2v-3.08A7 7 0 0 0 19 12h-2z"/>' +
        '</svg>';

    let config = gentelella_tinymce_config(instance);
    config.toolbar = 'voicedictate | ' + config.toolbar;
    config.setup = function (editor) {
        editor.ui.registry.addIcon('microphone', mic_svg);

        let mic_api = null;
        let listen_notif = null;
        let previewSpan = null;

        // Live preview lives inside a marker <span>; the authoritative
        // whole-file result replaces it on stop, then the span is unwrapped
        // into plain content. Appending into the node (not at the caret)
        // keeps it robust to the user moving the cursor.
        function unwrapNode(sp){
            let p = sp.parentNode;
            if(!p) return;   // already detached (undo, setContent, editor teardown)
            while(sp.firstChild){ p.insertBefore(sp.firstChild, sp); }
            p.removeChild(sp);
        }
        function clearOldMarkers(){
            editor.dom.select('span[data-voice-preview]').forEach(unwrapNode);
        }
        function startPreview(){
            clearOldMarkers();
            let mid = 'gtvp' + (new Date().getTime());
            editor.insertContent('<span id="' + mid +
                '" data-voice-preview="1">​</span>');
            previewSpan = editor.dom.get(mid);
        }
        function appendPreview(text){
            if(!text) return;
            if(!previewSpan){ editor.insertContent(voice_escape_html(text)); return; }
            let cur = previewSpan.textContent.replace(/​/g, '');
            if(!cur){ previewSpan.textContent = text; }
            else{ previewSpan.appendChild(
                editor.getDoc().createTextNode(voiceLeadingSep(cur) + text)); }
            editor.nodeChanged();
        }
        // Unwrap the marker span into plain content (keeps its text). The span
        // may already be gone -- an undo or a setContent() drops it while the
        // dictation is still running -- so this must not assume a parent.
        function unwrapPreview(){
            if(!previewSpan) return;
            let sp = previewSpan;
            previewSpan = null;
            unwrapNode(sp);
            editor.nodeChanged();
        }
        // single/hybrid modes: replace the preview with the whole-file text.
        function setFinal(text){
            if(!previewSpan){
                if(text){ editor.insertContent(voice_escape_html(text)); }
                return;
            }
            previewSpan.textContent = text || '';   // textContent escapes
            unwrapPreview();
        }

        let disposed = false;
        let cfg = voiceBaseConfig(instance);
        cfg.onStatus = function (status) {
            // destroy() cancels the session, which reports status 0 back here.
            // By then the editor is being torn down and touching its ui,
            // notifications or document would throw.
            if (disposed) return;
            if (mic_api) {
                mic_api.setActive(status == 1);
                // TinyMCE 6 replaced the toggle button's setDisabled with
                // setEnabled, in the opposite sense.
                mic_api.setEnabled(status != 2);
            }
            editor.setProgressState(status == 2);
            if (status == 1) {
                startPreview();
                if (!listen_notif) {
                    listen_notif = editor.notificationManager.open({
                        text: gettext('Listening...'),
                        type: 'info', closeButton: false, timeout: 0
                    });
                }
            } else {
                if (listen_notif) { listen_notif.close(); listen_notif = null; }
                // Segment-only (no final pass): flatten the marker when done.
                if (status == 0) unwrapPreview();
            }
        };
        cfg.onSegmentText = appendPreview;   // segments/hybrid: appended live
        cfg.onFinalText = setFinal;          // single/hybrid: whole-file result
        let engine = createProgressiveVoiceEngine(cfg);

        editor.ui.registry.addToggleButton('voicedictate', {
            icon: 'microphone',
            tooltip: gettext('Dictate'),
            onAction: function () { engine.toggle(); },
            onSetup: function (api) {
                mic_api = api;
                return function () { mic_api = null; };
            }
        });

        // On editor teardown, stop recording, drop any in-flight transcription
        // and unbind the window listener.
        editor.on('remove', function () { disposed = true; engine.destroy(); });
    };

    gentelella_tinymce_init(instance, config);
}
