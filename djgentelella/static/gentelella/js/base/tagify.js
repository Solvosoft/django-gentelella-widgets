function build_tagginginput(instances){
    instances.each(function(index, element){
         let tagify = new Tagify(element, {});
         //element.dataset.tagify = JSON.stringify(tagify);
    });
}
function build_tagging_email(instances){
    instances.each(function(index, element){
        let p = /^(([^<>()\[\]\\.,;:\s@"]+(\.[^<>()\[\]\\.,;:\s@"]+)*)|(".+"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))$/;
        let tagify = new Tagify(element, {
            pattern: p
        });
    });
}

function build_remote_tagify_email(inputs){
    inputs.each(function(index, element){
       let url = element.dataset['url'];

       let tagify = new Tagify(element, {whitelist:[],
        pattern: /^\w+([\.-]?\w+)*@\w+([\.-]?\w+)*(\.\w{2,3})*$/,
         dropdown: {
            searchKeys: ["value", "name"] //  fuzzy-search matching for those whitelist items' properties
         }
       }),
        controller;

        function onInput( e ){
            var value = e.detail.value
              tagify.whitelist = null // reset the whitelist
              // https://developer.mozilla.org/en-US/docs/Web/API/AbortController/abort
              controller && controller.abort()
              controller = new AbortController()
              // show loading animation and hide the suggestions dropdown
              tagify.loading(true);
            fetch(url+'?value=' + value, {signal:controller.signal})
                .then(RES => RES.json())
                .then(function(newWhitelist){
                  tagify.whitelist = newWhitelist // update whitelist Array in-place
                  tagify.loading(false); // render the suggestions dropdown
            })
        }
        tagify.on('input', onInput)
    })
}
