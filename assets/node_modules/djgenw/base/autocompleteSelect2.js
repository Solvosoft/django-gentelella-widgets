function build_select2_init(instance){
    var autocompleteselect2 = {
        'remote': [],
        'related': {}
    };
    instance.each(function(index, elem){

        let ins=$(this);
        let obj = {
            'id': "#"+ins.attr('id'),
            'url':  ins.data('url'),
            'start_empty': ins.data('start_empty')
        };
        let isrelated = ins.data('related');
        if (isrelated != undefined){
            obj['position'] = parseInt(ins.data('pos'));
            let groupname = ins.data('groupname');
            if (!autocompleteselect2['related'].hasOwnProperty(groupname)){
                autocompleteselect2['related'][groupname]=[];
            }
            autocompleteselect2['related'][groupname].push(obj);
        }else{
            autocompleteselect2['remote'].push(obj);
        }
    })
    $(window).select2related('remote', autocompleteselect2['remote']);
    $.each(autocompleteselect2['related'], function(index, value) {
        function compare(a, b) {
          if (a.position > b.position) return 1;
          if (b.position > a.position) return -1;
          return 0;
        }
        $(window).select2related('related', value.sort(compare));
    });
}

