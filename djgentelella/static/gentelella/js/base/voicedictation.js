// Textarea voice dictation consumer. Uses the progressive engine
// (createProgressiveVoiceEngine in voiceprogressive.js): a continuous dictation
// session where finalized segments are transcribed and appended live as the
// user speaks; the authoritative whole-file result replaces the preview on stop.

// Engines by widget id. A container re-render (api_list rebuilds innerHTML and
// re-runs gt_find_initialize_from_dom, a modal reopened) calls this again for a
// brand new node, so the previous engine cannot be found through the DOM -- and
// it would otherwise keep its window listener, its closure and, if it was
// recording, its microphone alive forever.
var _voice_dictation_engines = {};

function getVoiceDictation(element){
    let id = element.id;
    let previous = _voice_dictation_engines[id];
    if(previous){ previous.destroy(); delete _voice_dictation_engines[id]; }
    let textarea = $("#"+id);
    let el = textarea[0];
    let btn_control = $("#"+id+"_btn");
    let btn_cancel = $("#"+id+"_cancel");
    let status_span = $("#"+id+"_status");

    // Preview region [anchor, anchor+preview.length): the live segments fill it
    // and the authoritative whole-file result replaces it on stop. `preview`
    // holds the exact inserted text, not just its length, so the region can be
    // checked before anything is overwritten.
    let anchor = 0, preview = '';
    function resetPreview(){
        // Only honour the caret when the field really has focus: selectionStart
        // is 0 on a textarea the user never clicked, which would silently
        // prepend the dictation to whatever the form already had in it.
        anchor = (document.activeElement === el && el.selectionStart != null)
                 ? el.selectionStart : el.value.length;
        preview = '';
    }
    // The textarea stays editable while dictating. If the user types before the
    // anchor every offset shifts, and splicing over the old region would delete
    // a chunk of what they wrote -- so verify the region still holds our text.
    function ownsPreview(){
        return el.value.substr(anchor, preview.length) === preview;
    }
    function reanchor(){
        anchor = el.value.length;
        preview = '';
    }
    function notify(){
        // input first: that is the event validations and autosave listen to for
        // a programmatic change; change keeps the previous behaviour.
        el.dispatchEvent(new Event('input', {bubbles: true}));
        el.dispatchEvent(new Event('change', {bubbles: true}));
    }
    function appendPreview(text){
        if(!text) return;
        if(!ownsPreview()) reanchor();
        let pos = anchor + preview.length;
        let before = el.value.slice(0, pos);
        let ins = voiceLeadingSep(before) + text;
        el.value = before + ins + el.value.slice(pos);
        preview += ins;
        notify();
    }
    function setFinal(text){
        if(!ownsPreview()) reanchor();
        let before = el.value.slice(0, anchor);
        let after = el.value.slice(anchor + preview.length);
        let ins = voiceLeadingSep(before) + (text || '');
        el.value = before + ins + after;
        preview = ins;
        notify();
    }

    let cfg = voiceBaseConfig(textarea);
    cfg.onStatus = function(status){
        if(status==0){
            btn_cancel.hide();
            btn_control.prop('disabled', false);
            $("#"+id+"_btn i").attr('class', 'fa fa-microphone');
            $("#"+id+"_btn span").text(gettext('Dictate'));
            status_span.text('');
        }else if(status==1){
            resetPreview();
            btn_cancel.show();
            btn_control.prop('disabled', false);
            $("#"+id+"_btn i").attr('class', 'fa fa-stop');
            $("#"+id+"_btn span").text(gettext('Stop and transcribe'));
            status_span.text(gettext('Listening...'));
        }else if(status==2){
            btn_cancel.hide();
            btn_control.prop('disabled', true);
            $("#"+id+"_btn i").attr('class', 'fa fa-spinner fa-spin');
            status_span.text(gettext('Transcribing...'));
        }
    };
    cfg.onSegmentText = appendPreview;   // live preview
    cfg.onFinalText = setFinal;          // authoritative whole-file result

    let engine = createProgressiveVoiceEngine(cfg);
    btn_control.on('click', () => engine.toggle());
    btn_cancel.on('click', () => engine.cancel(false));
    btn_cancel.hide();
    status_span.text('');
    _voice_dictation_engines[id] = engine;
    return engine;
}
