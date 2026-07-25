// Textarea voice dictation consumer. Uses the progressive engine
// (createProgressiveVoiceEngine in voiceprogressive.js): a continuous dictation
// session where finalized segments are transcribed and appended live as the
// user speaks; the authoritative whole-file result replaces the preview on stop.

function getVoiceDictation(element){
    let id = element.id;
    let textarea = $("#"+id);
    let el = textarea[0];
    let btn_control = $("#"+id+"_btn");
    let btn_cancel = $("#"+id+"_cancel");
    let status_span = $("#"+id+"_status");

    // Preview region [anchor, anchor+previewLen): the live segments fill it and
    // the authoritative whole-file result replaces it on stop.
    let anchor = 0, previewLen = 0;
    function resetPreview(){
        anchor = (el.selectionStart != null) ? el.selectionStart : el.value.length;
        previewLen = 0;
    }
    function appendPreview(text){
        if(!text) return;
        let pos = anchor + previewLen;
        let before = el.value.slice(0, pos);
        let ins = voiceLeadingSep(before) + text;
        el.value = before + ins + el.value.slice(pos);
        previewLen += ins.length;
        el.dispatchEvent(new Event('change', {bubbles: true}));
    }
    function setFinal(text){
        let before = el.value.slice(0, anchor);
        let after = el.value.slice(anchor + previewLen);
        let ins = voiceLeadingSep(before) + (text || '');
        el.value = before + ins + after;
        previewLen = ins.length;
        el.dispatchEvent(new Event('change', {bubbles: true}));
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
    return engine;
}
