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
}