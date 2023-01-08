function show_errors_media_record(error){
    Swal.fire({
          icon: 'error',
          title: 'Sorry, there is a problem',
          text: 'Media device is not available',
        })
}
function getPhotoRecord(element){
    let id = element.id
    let media = {
          tag: 'video',
          type: 'image/png',
          ext: '.png',
          gUM: {video: true}
    }

    let v= {
        id: id,
        canvas: $("#"+id+"_canvas"),
        video: $("#"+id+"_video"),
        btn_control: $("#"+id+"_btn"),
        btn_cancel: $("#"+id+"_cancel"),
        width: $("#"+id).data('width') || '320px',
        height: $("#"+id).data('height') || '240px',
        recorder: null,
        media: media,
        status: 0,
        initialize: function(){
            this.btn_control.on('click', this.callClick(this));
            this.btn_cancel.on('click', this.callCancel(this));
            this.btn_cancel.hide();
            this.canvas.hide();
            this.video.hide();
            this.canvas[0].style.width=this.width;
            this.canvas[0].style.height=this.height;
            this.video[0].style.width=this.width;
            this.video[0].style.height=this.height;
            $(window).on('cancelMedia', this.callCancel(this, trigger=true));

        },
        clickEvent: function(){
            var video = this.video[0];
            var parent = this;
            if(this.status==0){
                navigator.mediaDevices.getUserMedia(this.media.gUM).then(_stream => {
                     video.srcObject = _stream;
                     parent.tracks = _stream.getTracks();
                }).catch(show_errors_media_record);
                this.video.show();
                this.canvas.hide();
            }else if(this.status==1){
                let canvas = this.canvas[0];
                this.video.hide();
                canvas.getContext('2d').drawImage(this.video[0], 0, 0, canvas.width, canvas.height);
                this.canvas.show();
            }else{
                this.status = -1;
                this.save_media();
                if(this.tracks) this.tracks.forEach(track => track.stop());
            }
            this.status = this.status+1;
            this.presentbutton();
        },
        presentbutton: function(){
            if(this.status==0){
                this.btn_cancel.hide();
                $("#"+this.id+"_btn i").attr('class', 'fa fa-video-camera');
                $("#"+this.id+"_btn span").text('Start');
            }else{
                this.btn_cancel.show();
            }
            if(this.status==1){
                    $("#"+this.id+"_btn i").attr('class', 'fa fa-camera');
                    $("#"+this.id+"_btn span").text('Capture');
            }
            if(this.status==2) {
                    $("#"+this.id+"_btn i").attr('class', 'fa fa-check');
                    $("#"+this.id+"_btn span").text('Save');
            }
        },
        cancel: function(trigger){
            this.status=0;
            if(this.recorder != null) this.recorder.stop();
            if(this.tracks) this.tracks.forEach(track => track.stop());
            this.btn_cancel.hide();
            this.canvas.hide();
            this.video.hide();
            this.presentbutton();
             if(!trigger)$(window).trigger('cancelMedia');

        },

        callCancel: function(instance, trigger=false){
            return () => { instance.cancel(trigger) };
        },
        callClick: function(instance){
             return () => { instance.clickEvent() };
        },
        save_media:function(){
            var parent = this;
            this.canvas[0].toBlob((blob) => {
              let file = new File([blob], "photo"+parent.media.ext, { type: parent.media.type  })
              let container = new DataTransfer();
              container.items.add(file);
            $("#"+parent.id)[0].files = container.files;
            }, parent.media.type);
        }
    }

    v.initialize()
    return v;
}


function getVideoRecord(element){
    let id = element.id
    let media = {
                  tag: 'video',
                  type: 'video/webm',
                  ext: '.mp4',
                  gUM: {video: true, audio: true}
                }
    let v= {
        id: id,
        canvas: $("#"+id+"_canvas"),
        video: $("#"+id+"_video"),
        btn_control: $("#"+id+"_btn"),
        btn_cancel: $("#"+id+"_cancel"),
        width: $("#"+id).data('width') || '320px',
        height: $("#"+id).data('height') || '240px',
        chunks: [],
        recorder: null,
        media: media,
        status: 0,
        initialize: function(){
            this.btn_control.on('click', this.callClick(this));
            this.btn_cancel.on('click', this.callCancel(this));
            this.btn_cancel.hide();
            this.video[0].style.width=this.width;
            this.video[0].style.height=this.height;
            this.video.hide();
            $(window).on('cancelMedia', this.callCancel(this, trigger=true));

        },
        clickEvent: function(){
            var video = this.video[0];
            var parent = this;
            if(this.status==0){
                navigator.mediaDevices.getUserMedia(this.media.gUM).then(_stream => {
                    video.srcObject = _stream;
                    parent.tracks = _stream.getTracks();
                    parent.recorder = new MediaRecorder(_stream);
                    parent.recorder.ondataavailable = e => {
                    parent.chunks.push(e.data);
                    if(parent.recorder.state == 'inactive')  parent.save_media();
                    };
                }).catch(show_errors_media_record);
                this.video.show();

            }else if(this.status==1){
                this.chunks=[];
                if(this.recorder) this.recorder.start();
            }else{
                if(this.recorder != null && this.recorder.state == 'inactive') this.recorder.stop();
                this.cancel(true)
                this.status = -1;
            }
            this.status = this.status+1;
            this.presentbutton();
        },
        presentbutton: function(){
            if(this.status==0){
                this.btn_cancel.hide();
                $("#"+this.id+"_btn i").attr('class', 'fa fa-video-camera');
                $("#"+this.id+"_btn span").text('Start');

            }else{
                this.btn_cancel.show();
            }
            if(this.status==1){
                $("#"+this.id+"_btn i").attr('class', 'fa fa-play');
                $("#"+this.id+"_btn span").text('Record');
                $("#"+this.id+"_container .mediareproductor").remove();
            }
            if(this.status==2) {
                $("#"+this.id+"_btn i").attr('class', 'fa fa-pause');
                $("#"+this.id+"_btn span").text('Recording...');
            }
        },
        cancel: function(trigger){
            this.status=0;
            if(this.recorder != null && this.recorder.state != 'inactive') this.recorder.stop();
            if(this.tracks) this.tracks.forEach(track => track.stop());
            this.btn_cancel.hide();
            this.video.hide();
            this.presentbutton();
             if(!trigger)$(window).trigger('cancelMedia');

        },

        callCancel: function(instance, trigger=false){
            return () => { instance.cancel(trigger) };
        },
        callClick: function(instance){
             return () => { instance.clickEvent() };
        },
        save_media:function(){
            let file = new File(this.chunks, "record"+this.media.ext, {type: this.media.type , lastModified:new Date().getTime()});
            let container = new DataTransfer();
            container.items.add(file);
            $("#"+this.id)[0].files = container.files;
             let blob = new Blob(this.chunks, {type: this.media.type })
             let url = URL.createObjectURL(blob)
             mt = document.createElement(this.media.tag)
             mt.controls = true;
             mt.src = url;
             mt.className = "mediareproductor"
             mt.style.width=this.width;
             mt.style.height=this.height;
             $("#"+this.id+"_container").append(mt);
        }
    }

    v.initialize()
    return v;
}


function getAudioRecord(element){
    let id = element.id
    let media = {
                  tag: 'audio',
                  type: 'audio/ogg',
                  ext: '.ogg',
                  gUM: {video: false, audio: true}
                }
    let v= {
        id: id,
        canvas: $("#"+id+"_canvas"),
        btn_control: $("#"+id+"_btn"),
        btn_cancel: $("#"+id+"_cancel"),
        chunks: [],
        recorder: null,
        media: media,
        status: 0,
        initialize: function(){
            this.btn_control.on('click', this.callClick(this));
            this.btn_cancel.on('click', this.callCancel(this));
            this.btn_cancel.hide();
            $(window).on('cancelMedia', this.callCancel(this, trigger=true));

        },
        clickEvent: function(){
            var parent = this;
            if(this.status==0){
                navigator.mediaDevices.getUserMedia(this.media.gUM).then(_stream => {
                    parent.tracks = _stream.getTracks();
                    parent.recorder = new MediaRecorder(_stream);
                    parent.recorder.ondataavailable = e => {
                    parent.chunks.push(e.data);
                    if(parent.recorder.state == 'inactive')  parent.save_media();
                    };
                }).catch(show_errors_media_record);
            }else if(this.status==1){
                this.chunks=[];
                if(this.recorder) this.recorder.start();
            }else{
                if(this.recorder != null && this.recorder.state == 'inactive') this.recorder.stop();
                this.cancel(true)
                this.status = -1;
            }
            this.status = this.status+1;
            this.presentbutton();
        },
        presentbutton: function(){
            if(this.status==0){
                this.btn_cancel.hide();
                $("#"+this.id+"_btn i").attr('class', 'fa fa-video-camera');
                $("#"+this.id+"_btn span").text('Start');
                $("#"+this.id+"_container .mediareproductor").remove();
            }else{
                this.btn_cancel.show();
            }
            if(this.status==1){
                $("#"+this.id+"_btn i").attr('class', 'fa fa-play');
                $("#"+this.id+"_btn span").text('Record');
            }
            if(this.status==2) {
                $("#"+this.id+"_btn i").attr('class', 'fa fa-pause');
                $("#"+this.id+"_btn span").text('Recording...');
            }
        },
        cancel: function(trigger){
            this.status=0;
            if(this.recorder != null && this.recorder.state == 'inactive') this.recorder.stop();
            if(this.tracks) this.tracks.forEach(track => track.stop());
            this.btn_cancel.hide();
            this.presentbutton();
             if(!trigger)$(window).trigger('cancelMedia');

        },

        callCancel: function(instance, trigger=false){
            return () => { instance.cancel(trigger) };
        },
        callClick: function(instance){
             return () => { instance.clickEvent() };
        },
        save_media:function(){
            let file = new File(this.chunks, "record"+this.media.ext, {type: this.media.type , lastModified:new Date().getTime()});
            let container = new DataTransfer();
            container.items.add(file);
            $("#"+this.id)[0].files = container.files;
             let blob = new Blob(this.chunks, {type: this.media.type })
             let url = URL.createObjectURL(blob)
             mt = document.createElement(this.media.tag)
             mt.controls = true;
             mt.src = url;
             mt.className = "mediareproductor"
             $("#"+this.id+"_container").append(mt);
        }
    }

    v.initialize()
    return v;
}



function getMediaRecord(element, mediatype){
    if(mediatype=='photo'){
        return getPhotoRecord(element);
    }
    if(mediatype=='video'){
        return getVideoRecord(element);
    }
    if(mediatype === "audio"){
        return getAudioRecord(element)
    }
}
