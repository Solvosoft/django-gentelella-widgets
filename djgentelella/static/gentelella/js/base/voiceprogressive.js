// Progressive (segment-by-segment) voice dictation engine.
//
// Captures raw PCM via Web Audio, runs an energy/RMS VAD state machine that
// cuts the audio at natural silences (or a forced max length), encodes each
// finalized segment as a standalone mono WAV (native capture rate; the server
// resamples to 16 kHz) and POSTs each segment independently to the
// transcription endpoint. Segments are transcribed concurrently (bounded pool)
// and re-ordered by index before being appended live, so the widget builds the
// transcription in parts as the user speaks.

// --- WAV encoding: Float32 [-1,1] mono -> RIFF/WAVE PCM 16-bit blob ---------
function writeWavBlob(samples, sampleRate){
    let n = samples.length;
    let buffer = new ArrayBuffer(44 + n * 2);
    let view = new DataView(buffer);
    function str(off, s){ for(let i=0;i<s.length;i++) view.setUint8(off+i, s.charCodeAt(i)); }
    str(0, 'RIFF');
    view.setUint32(4, 36 + n * 2, true);
    str(8, 'WAVE');
    str(12, 'fmt ');
    view.setUint32(16, 16, true);            // PCM header size
    view.setUint16(20, 1, true);             // format = PCM
    view.setUint16(22, 1, true);             // channels = mono
    view.setUint32(24, sampleRate, true);    // sample rate
    view.setUint32(28, sampleRate * 2, true);// byte rate = rate * blockAlign
    view.setUint16(32, 2, true);             // block align = channels * 2
    view.setUint16(34, 16, true);            // bits per sample
    str(36, 'data');
    view.setUint32(40, n * 2, true);
    let off = 44;
    for(let i=0;i<n;i++){
        let s = Math.max(-1, Math.min(1, samples[i]));
        view.setInt16(off, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
        off += 2;
    }
    return new Blob([view], {type: 'audio/wav'});
}

function _concatFloat32(frames){
    let total = 0;
    for(let i=0;i<frames.length;i++) total += frames[i].length;
    let out = new Float32Array(total);
    let off = 0;
    for(let i=0;i<frames.length;i++){ out.set(frames[i], off); off += frames[i].length; }
    return out;
}

function _rmsOf(frame){
    let sum = 0;
    for(let i=0;i<frame.length;i++){ sum += frame[i] * frame[i]; }
    return Math.sqrt(sum / (frame.length || 1));
}

// --- Ordering buffer: emit finalized segments in ascending index -----------
// Every dispatched index must eventually be added (text or '' on failure) so
// ordering never stalls. emit(text) is only called for non-empty segments.
function createSegmentOrderer(emit){
    return {
        next: 0,
        buffer: {},
        add: function(index, text){
            this.buffer[index] = text || '';
            while(Object.prototype.hasOwnProperty.call(this.buffer, this.next)){
                let t = this.buffer[this.next];
                delete this.buffer[this.next];
                this.next++;
                if(t) emit(t);
            }
        }
    };
}

// --- The progressive engine ------------------------------------------------
// opts: url (required); getHotwords/getInitialPrompt/getLanguage; onError;
//       onStatus(status) -> 0 idle / 1 recording / 2 draining/finalizing;
//       onSegmentText(text) -> each finalized segment, appended in order;
//       onFinalText(text) -> whole-file result on stop (single/hybrid modes).
//       mode (default 'segments'):
//         'single'   - no live segments; transcribe the whole recording once on
//                      stop and insert the result.
//         'segments' - transcribe each VAD segment and append it live.
//         'hybrid'   - append segments live, then re-transcribe the whole
//                      recording on stop and replace them.
//       plus VAD config.
var _voiceEngineSeq = 0;
function createProgressiveVoiceEngine(opts){
    let mode = (opts.mode === 'single' || opts.mode === 'hybrid')
               ? opts.mode : 'segments';
    let doSegments = mode !== 'single';   // run VAD + dispatch segments live
    let doFinal = mode !== 'segments';    // keep whole audio + final pass on stop
    // Responsive defaults: cut at natural ~0.6s pauses so segments appear live
    // as the user speaks (raise vadSilenceMs/vadMinSpeechMs for longer segments).
    let cfg = {
        vadSilenceMs:   opts.vadSilenceMs   || 600,
        vadMinSpeechMs: opts.vadMinSpeechMs || 500,
        vadMaxSegmentMs:opts.vadMaxSegmentMs|| 10000,
        rmsThreshold:   opts.rmsThreshold   || 0.008,
        rescueRms:      opts.rescueRms      || 0.02,
        preRollMs:      opts.preRollMs      || 200,
        poolSize:       opts.poolSize       || 3
    };

    let engine = {
        status: 0,          // 0 idle, 1 recording, 2 draining/finalizing
        ctx: null,
        stream: null,
        tracks: null,
        node: null,
        source: null,
        // VAD/segment accumulation
        sampleRate: 16000,
        segment: [],
        segmentMs: 0,
        speechMs: 0,
        silenceMs: 0,
        segMaxRms: 0,
        hasSpeech: false,
        segmentIndex: 0,
        gen: 0,               // session generation; invalidates late responses
        allFrames: [],        // whole-session audio (kept in single/hybrid modes)
        finalPending: false,  // the whole-file request is in flight
        // transcription pool
        pending: [],
        active: 0,
        orderer: null,

        setStatus: function(status){
            this.status = status;
            if(opts.onStatus) opts.onStatus(status);
        },

        toggle: function(){
            if(this.status === 0) this.start();
            else if(this.status === 1) this.stop();
            // status 2: draining, ignore
        },

        start: function(){
            var self = this;
            let AC = window.AudioContext || window.webkitAudioContext;
            let constraints = {video: false, audio: {
                channelCount: 1, echoCancellation: true,
                noiseSuppression: true, autoGainControl: true
            }};
            navigator.mediaDevices.getUserMedia(constraints).then(function(stream){
                self.stream = stream;
                self.tracks = stream.getTracks();
                self.ctx = new AC();
                self.sampleRate = self.ctx.sampleRate;
                self.gen++;
                let myGen = self.gen;
                self.orderer = createSegmentOrderer(function(text){
                    if(self.gen === myGen && opts.onSegmentText) opts.onSegmentText(text);
                });
                self._resetSegment();
                self.segmentIndex = 0;
                self.allFrames = []; self.finalPending = false;
                self.pending = []; self.active = 0;
                let resume = self.ctx.resume ? self.ctx.resume() : Promise.resolve();
                return resume.then(function(){
                    self.source = self.ctx.createMediaStreamSource(stream);
                    return self._buildCaptureNode();
                });
            }).then(function(){
                self.setStatus(1);
            }).catch(function(err){ self._reportError(err); });
        },

        // AudioWorklet (preferred) with ScriptProcessor fallback.
        _buildCaptureNode: function(){
            var self = this;
            let onFrame = function(f){ self._handleFrame(f); };
            if(self.ctx.audioWorklet){
                let src = "class PCMProc extends AudioWorkletProcessor{" +
                          "process(inputs){var i=inputs[0];" +
                          "if(i&&i[0]){this.port.postMessage(i[0].slice(0));}return true;}}" +
                          "registerProcessor('gt-pcm-proc',PCMProc);";
                let url = URL.createObjectURL(new Blob([src], {type:'application/javascript'}));
                return self.ctx.audioWorklet.addModule(url).then(function(){
                    URL.revokeObjectURL(url);
                    let node = new AudioWorkletNode(self.ctx, 'gt-pcm-proc');
                    node.port.onmessage = function(e){ onFrame(e.data); };
                    self.source.connect(node);
                    node.connect(self.ctx.destination);  // silent output, no echo
                    self.node = node;
                });
            }
            // Fallback: deprecated ScriptProcessorNode.
            let node = self.ctx.createScriptProcessor(4096, 1, 1);
            node.onaudioprocess = function(e){
                onFrame(e.inputBuffer.getChannelData(0).slice(0));
            };
            self.source.connect(node);
            node.connect(self.ctx.destination);
            self.node = node;
            return Promise.resolve();
        },

        _resetSegment: function(){
            this.segment = []; this.segmentMs = 0; this.speechMs = 0;
            this.silenceMs = 0; this.segMaxRms = 0; this.hasSpeech = false;
        },

        _handleFrame: function(frame){
            if(this.status !== 1) return;
            // Store raw native-rate audio; the server resamples to 16 kHz.
            if(doFinal) this.allFrames.push(frame);       // whole-file pass
            if(!doSegments) return;                        // single mode: no VAD
            let dur = frame.length / this.sampleRate * 1000;
            let rms = _rmsOf(frame);
            this.segment.push(frame);
            this.segmentMs += dur;
            if(rms > this.segMaxRms) this.segMaxRms = rms;
            if(rms >= cfg.rmsThreshold){
                this.hasSpeech = true;
                this.speechMs += dur;
                this.silenceMs = 0;
            }else{
                this.silenceMs += dur;
            }
            // Drop leading silence while waiting for speech (keep pre-roll).
            if(!this.hasSpeech && this.segmentMs > cfg.preRollMs){
                this._trimPreRoll();
            }
            let natural = this.hasSpeech && this.silenceMs >= cfg.vadSilenceMs
                          && this.speechMs >= cfg.vadMinSpeechMs;
            let forced = this.hasSpeech && this.segmentMs >= cfg.vadMaxSegmentMs;
            if(natural || forced) this._cut(false);
        },

        _trimPreRoll: function(){
            let keep = Math.round(cfg.preRollMs / 1000 * this.sampleRate);
            let total = 0;
            for(let i=0;i<this.segment.length;i++) total += this.segment[i].length;
            while(this.segment.length > 1 && (total - this.segment[0].length) >= keep){
                total -= this.segment.shift().length;
            }
            this.segmentMs = total / this.sampleRate * 1000;
            if(this.silenceMs > this.segmentMs) this.silenceMs = this.segmentMs;
        },

        _cut: function(finalFlush){
            let enoughSpeech = this.hasSpeech && this.speechMs >= cfg.vadMinSpeechMs;
            let rescue = this.segMaxRms >= cfg.rescueRms;
            // On the final flush accept a shorter last phrase too.
            let emit = this.segment.length && (enoughSpeech || rescue ||
                       (finalFlush && this.hasSpeech));
            if(emit){
                let samples = _concatFloat32(this.segment);  // native rate
                this._dispatch(this.segmentIndex++, samples);
            }
            this._resetSegment();
        },

        _dispatch: function(index, samples){
            let blob = writeWavBlob(samples, this.sampleRate);
            this.pending.push({index: index, blob: blob, gen: this.gen});
            this._pump();
        },

        _pump: function(){
            var self = this;
            while(self.active < cfg.poolSize && self.pending.length){
                let job = self.pending.shift();
                self.active++;
                self._post(job.blob, 'seg' + job.index + '.wav').then(function(text){
                    if(job.gen === self.gen) self.orderer.add(job.index, text);
                }).catch(function(){
                    if(job.gen === self.gen) self.orderer.add(job.index, '');
                }).then(function(){
                    self.active--;
                    self._pump();
                    self._maybeFinish();
                });
            }
        },

        _post: function(blob, filename){
            let fd = new FormData();
            fd.append('file', blob, filename);
            let hw = opts.getHotwords ? opts.getHotwords() : null;
            if(hw) fd.append('hotwords', hw);
            let ip = opts.getInitialPrompt ? opts.getInitialPrompt() : null;
            if(ip) fd.append('initial_prompt', ip);
            let lang = opts.getLanguage ? opts.getLanguage() : null;
            if(lang) fd.append('language', lang);
            return fetch(opts.url, {
                method: 'POST',
                headers: {'X-CSRFToken': getCookie('csrftoken')},
                body: fd
            }).then(function(r){
                if(!r.ok) throw new Error('HTTP ' + r.status);
                return r.json();
            }).then(function(data){ return data.text || ''; });
        },

        // Whole-file pass (single/hybrid modes): on stop, transcribe the entire
        // session in one request (full ASR context) and hand the result to the
        // consumer via onFinalText (which inserts or replaces the segments).
        _finalTranscribe: function(){
            var self = this;
            if(!this.allFrames.length) return;
            let myGen = this.gen;
            let samples = _concatFloat32(this.allFrames);
            this.allFrames = [];
            let blob = writeWavBlob(samples, this.sampleRate);
            this.finalPending = true;
            this._post(blob, 'full.wav').then(function(text){
                if(self.gen === myGen && text && opts.onFinalText) opts.onFinalText(text);
            }).catch(function(){
                // keep the segment preview if the final pass fails
            }).then(function(){
                self.finalPending = false;
                self._maybeFinish();
            });
        },

        _maybeFinish: function(){
            if(this.status === 2 && this.active === 0 && this.pending.length === 0
               && !this.finalPending){
                this.setStatus(0);
            }
        },

        _teardown: function(){
            if(this.node){ try{ this.node.disconnect(); }catch(e){} this.node = null; }
            if(this.source){ try{ this.source.disconnect(); }catch(e){} this.source = null; }
            if(this.tracks){ this.tracks.forEach(function(t){ t.stop(); }); this.tracks = null; }
            if(this.ctx){ try{ this.ctx.close(); }catch(e){} this.ctx = null; }
            this.stream = null;
        },

        stop: function(){
            if(this.status !== 1) return;
            if(doSegments) this._cut(true);   // flush the last phrase
            this._teardown();
            this.setStatus(2);                // draining segments / final pass
            if(doFinal) this._finalTranscribe();
            this._maybeFinish();              // in case nothing is pending
        },

        cancel: function(trigger){
            this.gen++;   // invalidate any in-flight segment/final responses
            this.pending = [];
            this.allFrames = [];
            this.finalPending = false;
            this._resetSegment();
            this._teardown();
            this.setStatus(0);
            if(!trigger) $(window).trigger('cancelMedia');
        },

        _reportError: function(err){
            console.error('[VoiceProgressive] capture failed:',
                          err && err.name, err && err.message, err);
            this._teardown();
            this.setStatus(0);
            if(opts.onError){ opts.onError(err); return; }
            show_errors_media_record(err);   // shared media-error dialog
        }
    };

    // Starting one dictation cancels any other in-progress one. Namespaced so a
    // re-initialized widget can unbind it via engine.destroy() (avoids leaking a
    // handler that closes over the old engine).
    let ns = 'cancelMedia.gtvoice' + (++_voiceEngineSeq);
    $(window).on(ns, function(){ engine.cancel(true); });
    engine.destroy = function(){ $(window).off(ns); this._teardown(); };
    return engine;
}

// Read optional VAD tuning from a widget's data-* attributes into an engine
// config object (defaults live in the engine). Reads data-vad-silence-ms,
// data-vad-min-speech-ms, data-vad-max-segment-ms, data-rms-threshold,
// data-pool-size.
function voiceVadConfig(el){
    let cfg = {};
    let keys = ['vadSilenceMs', 'vadMinSpeechMs', 'vadMaxSegmentMs',
                'rmsThreshold', 'poolSize'];
    keys.forEach(function(k){
        let v = el.data(k);
        if(v !== undefined && v !== null && v !== ''){ cfg[k] = parseFloat(v); }
    });
    return cfg;
}

// Base engine config shared by the widget consumers: transcription URL, the
// three biasing getters, and any VAD tuning from data-* attrs. Each consumer
// adds only its onStatus/onSegmentText/onFinalText.
function voiceBaseConfig(el){
    let cfg = voiceVadConfig(el);
    cfg.url = el.data('url');
    cfg.getHotwords = function(){ return el.data('hotwords'); };
    cfg.getInitialPrompt = function(){ return el.data('initial-prompt'); };
    cfg.getLanguage = function(){ return el.data('language'); };
    cfg.mode = el.data('mode');   // 'single' | 'segments' (default) | 'hybrid'
    return cfg;
}

// Leading separator: a single space when the preceding text ends in a
// non-whitespace char (so a dictated fragment doesn't glue onto the last word).
function voiceLeadingSep(prevText){
    return (prevText && !/\s$/.test(prevText)) ? ' ' : '';
}
