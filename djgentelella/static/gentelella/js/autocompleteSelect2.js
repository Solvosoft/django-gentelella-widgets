(function ( $ ) {
    function build_select2_init(){
        var autocompleteselect2 = {
            'remote': [],
            'related': {}
        };
        if(window.hasOwnProperty('autocompleteselect2')){
            return // call this method only one time or remove autocompleteselect2 from window.
        }else{
            window.autocompleteselect2 = autocompleteselect2;
        }

        $('[data-widget="AutocompleteSelectMultiple"], [data-widget="AutocompleteSelect"]').each(function(index, elem){
                /**
            [{ 'id': '#myfield',
              'url': '/myendpoint', * ignored on simple
              'start_empty': true   * only on related action
            }]
        **/
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
    build_select2_init();
}( jQuery ));
