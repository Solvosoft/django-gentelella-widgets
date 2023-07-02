function create_identifiers(items){
     var descriptors=[];
     for(var x=0; x<items.length; x++){
        if(items[x].charAt(0) == '#' || items[x].charAt(0) == '.' ){
            descriptors.push(items[x]);
        }else{
            descriptors.push('input[name="'+items[x]+'"],textarea[name="'+items[x]+'"],select[name="'+items[x]+'"]');
        }
     }
     return descriptors;
}

function showHideRelatedFormFields(instance){
    var rel = instance.data('rel');
    var parentclass = instance.data('shparent');
    if(parentclass == undefined) parentclass = '.row'
    if(rel != undefined ){
        var relateditems = create_identifiers(instance.data('rel').split(';'));
        instance.on('change', function(){
            for(var x=0; x<relateditems.length; x++){
                if(this.checked){
                    $(relateditems[x]).closest(parentclass).show();
                }else{
                    $(relateditems[x]).closest(parentclass).hide();
                }
            }
        });
        instance.trigger('change');
    }
    var relh = instance.data('relhidden');
    if(relh != undefined ){
        var relateditemsh = create_identifiers(relh.split(';'));
        instance.on('change', function(e){
            for(var x=0; x<relateditemsh.length; x++){
                if(this.checked){
                    $(relateditemsh[x]).closest(parentclass).hide();
                }else{
                    $(relateditemsh[x]).closest(parentclass).show();
                }
            }
        });
         instance.trigger('change');
    }
}
