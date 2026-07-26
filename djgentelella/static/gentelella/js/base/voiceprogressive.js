// Progressive (segment-by-segment) voice dictation engine.
//
// Captures raw PCM via Web Audio, runs an energy/RMS VAD state machine that
// cuts the audio at natural silences (or a forced max length), encodes each
// finalized segment as a standalone mono WAV (native capture rate; the server
// resamples to 16 kHz) and POSTs each segment independently to the
// transcription endpoint. Segments are transcribed concurrently (bounded pool)
// and re-ordered by index before being appended live, so the widget builds the
// transcription in parts as the user speaks.

// getUserMedia is absent outside a secure context (plain http) and in iframes
// without allow="microphone". Reading it there throws synchronously, before any
// promise exists, so start() normalizes the failure into this rejection.
function voice_unsupported_error(){
    let err = new Error('navigator.mediaDevices.getUserMedia is unavailable');
    err.name = 'NotSupportedError';
    return err;
}

// Capture failed: the microphone never opened. NotSupportedError is almost
// always the http/https mistake, which the generic media dialog does not hint at.
function show_errors_voice_capture(error){
    if(error && error.name === 'NotSupportedError'){
        Swal.fire({
            icon: 'error',
            title: gettext('Sorry, there is a problem'),
            text: gettext('Voice dictation needs the page to be served over ' +
                          'https (or localhost) to reach the microphone.')
        });
        return;
    }
    show_errors_media_record(error);
}

// The microphone worked but one or more transcription requests did not. Without
// this the widget just returns to idle with nothing written and no explanation.
function show_errors_voice_transcribe(){
    Swal.fire({
        icon: 'error',
        title: gettext('Sorry, there is a problem'),
        text: gettext('Part of the dictation could not be transcribed. ' +
                      'Check your connection and try again.')
    });
}

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
        poolSize:       opts.poolSize       || 3,
        // Whole-file audio is kept at the native rate: ~11 MB/min as Float32,
        // doubled while the WAV is built. Past this the buffer is dropped and
        // the live segments carry the rest of the session (see
        // _dropWholeFileBuffer).
        maxSessionMs:   opts.maxSessionMs   || 600000,
        // A request that never settles would block the orderer forever and
        // leave the widget draining with nothing on screen.
        requestTimeoutMs: opts.requestTimeoutMs || 60000
    };

    let engine = {
        status: 0,          // 0 idle, 1 recording, 2 draining/finalizing
        starting: false,    // start() is awaiting getUserMedia/AudioContext
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
        sessionMs: 0,         // audio captured this session
        finalPending: false,  // the whole-file request is in flight
        finalApplied: false,  // the whole-file result already replaced the preview
        errors: 0,            // failed transcription requests this session
        // Mode flags, mutable: a session that outgrows the whole-file buffer
        // falls back to segments (see _dropWholeFileBuffer), so `single` mode
        // keeps transcribing instead of discarding the rest of the dictation.
        segmentsOn: doSegments,
        finalOn: doFinal,
        // transcription pool
        pending: [],
        active: 0,
        inflight: [],         // AbortControllers of the requests in the air
        orderer: null,

        setStatus: function(status){
            this.status = status;
            if(opts.onStatus) opts.onStatus(status);
        },

        toggle: function(){
            if(this.starting) return;         // permission prompt still open
            if(this.status === 0) this.start();
            else if(this.status === 1) this.stop();
            // status 2: draining, ignore
        },

        start: function(){
            var self = this;
            if(this.starting || this.status !== 0) return;
            let AC = window.AudioContext || window.webkitAudioContext;
            let constraints = {video: false, audio: {
                channelCount: 1, echoCancellation: true,
                noiseSuppression: true, autoGainControl: true
            }};
            // Claim the session *before* the first await. Bringing up the
            // capture takes several ticks (permission prompt, ctx.resume,
            // addModule); a cancel() or a second start() in the meantime bumps
            // gen, and every continuation below bails out on a mismatch instead
            // of overwriting the live stream/context references (which would
            // leave the previous microphone open forever).
            let myGen = ++this.gen;
            this.starting = true;
            // Everything from here has to end up in the promise chain: on plain
            // http navigator.mediaDevices is undefined, so reading getUserMedia
            // throws synchronously and the .catch below would never run -- the
            // button would just sit there with no error shown at all.
            let capture;
            try{
                capture = (navigator.mediaDevices &&
                           navigator.mediaDevices.getUserMedia)
                    ? navigator.mediaDevices.getUserMedia(constraints)
                    : Promise.reject(voice_unsupported_error());
            }catch(err){
                capture = Promise.reject(err);
            }
            capture.then(function(stream){
                if(self.gen !== myGen){
                    // superseded while the permission prompt was open
                    stream.getTracks().forEach(function(t){ t.stop(); });
                    return null;
                }
                self.stream = stream;
                self.tracks = stream.getTracks();
                self.ctx = new AC();
                self.sampleRate = self.ctx.sampleRate;
                self.orderer = createSegmentOrderer(function(text){
                    // Once the whole-file result is in, a segment that arrives
                    // late describes speech that text already covers: appending
                    // it would duplicate the phrase (hybrid mode races the last
                    // segment against the final pass).
                    if(self.gen === myGen && !self.finalApplied
                       && opts.onSegmentText) opts.onSegmentText(text);
                });
                self._resetSegment();
                self.segmentIndex = 0;
                self.allFrames = []; self.finalPending = false;
                self.finalApplied = false; self.errors = 0;
                self.sessionMs = 0;
                self.segmentsOn = doSegments; self.finalOn = doFinal;
                self.pending = []; self.active = 0;
                let resume = self.ctx.resume ? self.ctx.resume() : Promise.resolve();
                return resume.then(function(){
                    if(self.gen !== myGen) return null;
                    self.source = self.ctx.createMediaStreamSource(stream);
                    return self._buildCaptureNode();
                });
            }).then(function(){
                self.starting = false;
                if(self.gen !== myGen){ self._teardown(); return; }
                self.setStatus(1);
            }).catch(function(err){
                self.starting = false;
                self._reportError(err);
            });
        },

        // AudioWorklet (preferred) with ScriptProcessor fallback.
        _buildCaptureNode: function(){
            var self = this;
            let onFrame = function(f){ self._handleFrame(f); };
            if(self.ctx.audioWorklet){
                return self._buildWorkletNode(onFrame).catch(function(err){
                    // A strict CSP with no blob: in script-src/worker-src makes
                    // addModule reject. Reporting that as "media device is not
                    // available" is both wrong and unnecessary: the deprecated
                    // ScriptProcessor path below still works everywhere.
                    console.warn('[VoiceProgressive] AudioWorklet unavailable, ' +
                                 'falling back to ScriptProcessorNode:', err);
                    self._buildScriptProcessorNode(onFrame);
                });
            }
            self._buildScriptProcessorNode(onFrame);
            return Promise.resolve();
        },

        _buildWorkletNode: function(onFrame){
            var self = this;
            let src = "class PCMProc extends AudioWorkletProcessor{" +
                      "process(inputs){var i=inputs[0];" +
                      "if(i&&i[0]){this.port.postMessage(i[0].slice(0));}return true;}}" +
                      "registerProcessor('gt-pcm-proc',PCMProc);";
            let url = URL.createObjectURL(new Blob([src], {type:'application/javascript'}));
            return self.ctx.audioWorklet.addModule(url).then(function(){
                let node = new AudioWorkletNode(self.ctx, 'gt-pcm-proc');
                node.port.onmessage = function(e){ onFrame(e.data); };
                self.source.connect(node);
                node.connect(self.ctx.destination);  // silent output, no echo
                self.node = node;
            }).finally(function(){
                URL.revokeObjectURL(url);   // also when addModule rejected
            });
        },

        // Deprecated but universally available, and the only option under a
        // blob:-less CSP.
        _buildScriptProcessorNode: function(onFrame){
            let node = this.ctx.createScriptProcessor(4096, 1, 1);
            node.onaudioprocess = function(e){
                onFrame(e.inputBuffer.getChannelData(0).slice(0));
            };
            this.source.connect(node);
            node.connect(this.ctx.destination);
            this.node = node;
        },

        _resetSegment: function(){
            this.segment = []; this.segmentMs = 0; this.speechMs = 0;
            this.silenceMs = 0; this.segMaxRms = 0; this.hasSpeech = false;
        },

        // The whole-file buffer has no natural end, so a long dictation would
        // grow it without bound. Drop it and let the live segments carry the
        // rest of the session: the transcription is the same, the memory is not.
        _dropWholeFileBuffer: function(){
            console.warn('[VoiceProgressive] session past ' + cfg.maxSessionMs +
                         'ms: dropping the whole-file buffer, segments only ' +
                         'from here on');
            this.allFrames = [];
            this.finalOn = false;
            this.segmentsOn = true;   // `single` mode has to start cutting now
            if(opts.onSessionLimit) opts.onSessionLimit(cfg.maxSessionMs);
        },

        _handleFrame: function(frame){
            if(this.status !== 1) return;
            let dur = frame.length / this.sampleRate * 1000;
            this.sessionMs += dur;
            // Store raw native-rate audio; the server resamples to 16 kHz.
            if(this.finalOn){                              // whole-file pass
                this.allFrames.push(frame);
                if(this.sessionMs >= cfg.maxSessionMs) this._dropWholeFileBuffer();
            }
            if(!this.segmentsOn) return;                   // single mode: no VAD
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
                }).catch(function(err){
                    if(job.gen !== self.gen) return;
                    // Keep the stream flowing (the orderer blocks on a gap) but
                    // remember the failure so the session can report it.
                    console.error('[VoiceProgressive] segment ' + job.index +
                                  ' failed:', err);
                    self.errors++;
                    self.orderer.add(job.index, '');
                }).then(function(){
                    // Only jobs of the current session hold a pool slot: start()
                    // and cancel() zero the counter, so decrementing for a stale
                    // response would drive it negative and _maybeFinish() (which
                    // requires active === 0) would never fire again, leaving the
                    // widget stuck in the draining state with no way out.
                    if(job.gen !== self.gen) return;
                    self.active--;
                    self._pump();
                    self._maybeFinish();
                });
            }
        },

        _post: function(blob, filename){
            var self = this;
            let fd = new FormData();
            fd.append('file', blob, filename);
            let hw = opts.getHotwords ? opts.getHotwords() : null;
            if(hw) fd.append('hotwords', hw);
            let ip = opts.getInitialPrompt ? opts.getInitialPrompt() : null;
            if(ip) fd.append('initial_prompt', ip);
            let lang = opts.getLanguage ? opts.getLanguage() : null;
            if(lang) fd.append('language', lang);
            // A bounded request: the orderer emits in index order, so one reply
            // that never comes stalls every later segment. The controller is
            // also what lets cancel() actually drop the requests in the air
            // instead of paying for transcriptions nobody will read.
            let controller = (typeof AbortController !== 'undefined')
                             ? new AbortController() : null;
            let timer = null;
            if(controller){
                self.inflight.push(controller);
                timer = setTimeout(function(){ controller.abort(); },
                                   cfg.requestTimeoutMs);
            }
            let settled = function(){
                if(timer) clearTimeout(timer);
                if(!controller) return;
                let at = self.inflight.indexOf(controller);
                if(at !== -1) self.inflight.splice(at, 1);
            };
            return fetch(opts.url, {
                method: 'POST',
                headers: {'X-CSRFToken': getCookie('csrftoken')},
                body: fd,
                signal: controller ? controller.signal : undefined
            }).then(function(r){
                if(!r.ok) throw new Error('HTTP ' + r.status);
                return r.json();
            }).then(function(data){ return data.text || ''; })
              .finally(settled);
        },

        _abortInflight: function(){
            this.inflight.forEach(function(c){ try{ c.abort(); }catch(e){} });
            this.inflight = [];
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
                if(self.gen === myGen && text && opts.onFinalText){
                    // From here the preview is authoritative: segments still in
                    // flight must not append on top of it.
                    self.finalApplied = true;
                    opts.onFinalText(text);
                }
            }).catch(function(err){
                // keep the segment preview if the final pass fails
                if(self.gen !== myGen) return;
                console.error('[VoiceProgressive] final pass failed:', err);
                self.errors++;
            }).then(function(){
                self.finalPending = false;
                self._maybeFinish();
            });
        },

        _maybeFinish: function(){
            if(this.status === 2 && this.active === 0 && this.pending.length === 0
               && !this.finalPending){
                let failed = this.errors;
                this.errors = 0;
                this.setStatus(0);
                if(failed){
                    if(opts.onTranscribeError) opts.onTranscribeError(failed);
                    else show_errors_voice_transcribe();
                }
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
            if(this.segmentsOn) this._cut(true);   // flush the last phrase
            this._teardown();
            this.setStatus(2);                // draining segments / final pass
            if(this.finalOn) this._finalTranscribe();
            this._maybeFinish();              // in case nothing is pending
        },

        cancel: function(trigger){
            this.gen++;   // invalidate any in-flight segment/final responses
            this.starting = false;
            this._abortInflight();   // stop paying for transcriptions nobody reads
            this.pending = [];
            this.active = 0;   // in-flight jobs are stale now, free their slots
            this.allFrames = [];
            this.sessionMs = 0;
            this.finalPending = false;
            this.finalApplied = false;
            this.segmentsOn = doSegments; this.finalOn = doFinal;
            this.errors = 0;   // nothing to report about a session the user dropped
            this._resetSegment();
            this._teardown();
            this.setStatus(0);
            if(!trigger) $(window).trigger('cancelMedia');
        },

        _reportError: function(err){
            console.error('[VoiceProgressive] capture failed:',
                          err && err.name, err && err.message, err);
            this.starting = false;
            this._teardown();
            this.setStatus(0);
            if(opts.onError){ opts.onError(err); return; }
            show_errors_voice_capture(err);
        }
    };

    // Starting one dictation cancels any other in-progress one. Namespaced so a
    // re-initialized widget can unbind it via engine.destroy() (avoids leaking a
    // handler that closes over the old engine).
    let ns = 'cancelMedia.gtvoice' + (++_voiceEngineSeq);
    $(window).on(ns, function(){ engine.cancel(true); });
    // cancel(), not just _teardown(): the session has to be invalidated too, or
    // segments still in flight resolve later and call back into a consumer whose
    // DOM (textarea, TinyMCE editor) no longer exists.
    engine.destroy = function(){ $(window).off(ns); this.cancel(true); };
    return engine;
}

// Read optional VAD tuning from a widget's data-* attributes into an engine
// config object (defaults live in the engine). Reads data-vad-silence-ms,
// data-vad-min-speech-ms, data-vad-max-segment-ms, data-rms-threshold,
// data-pool-size, data-max-session-ms and data-request-timeout-ms.
function voiceVadConfig(el){
    let cfg = {};
    let keys = ['vadSilenceMs', 'vadMinSpeechMs', 'vadMaxSegmentMs',
                'rmsThreshold', 'poolSize', 'maxSessionMs',
                'requestTimeoutMs'];
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
