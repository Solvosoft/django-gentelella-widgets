(function($){
    $.fn.listcrudrest = function(){
        var $this = $(this),
           btn = $this.find('.additemcrudlist'),
           form = $this.find('form'),
           url_add = form.attr('action'),
           del_btn =  $this.find('.gencruddel'),
           def_url = del_btn.data('href'),
           list = $this.find('.gencrudlist');
        var template = '<li> <p><div class="icheckbox_flat-green"  >'+
           '<input type="checkbox" class="flat gencrudcheck" name="__ID__" >'+
           '<ins class="iCheck-helper" ></ins></div> __DESCRIPTION__</p></li>';


        var update_list = function(result){
            var html='';
            for(var x=0; x<result.length; x++){
                html += template.replace('__ID__', result[x].id).replace(
                '__DESCRIPTION__', result[x].name);
            }
            list.html(html);
            list.find('input').iCheck({
                checkboxClass: 'icheckbox_flat-green',
                radioClass: 'iradio_flat-green'
            });
        }
        $(btn).on('click', function(){
            $.ajax({
                url: url_add, // url where to submit the request
                type : "POST", // type of action POST || GET
                dataType : 'json', // data type
                data : $(form).serialize(), // post data || get data
                success : function(result) {
                    form.find('p.error').remove();
                    update_list(result);

                },
                error: function(xhr, resp, text) {
                    if(xhr.status == 400 ){
                        keys = Object.keys(xhr.responseJSON)

                        $.each(keys, function(i, e){
                            var item = form.find('*[name='+e+']');
                            item.after('<p class="text-danger error">'+xhr.responseJSON[e].join("<br>")+'<p>');
                        });
                    }
                }
            });
        });

        $(del_btn).on('click', function( ){
            var todelete=[];
            $(list).find('input:checked').each(function (i,e){
                todelete.push(e.name)
            });

            $.ajax({
                url: def_url, // url where to submit the request
                type : "DELETE", // type of action POST || GET
                headers: {'X-CSRFToken': getCookie('csrftoken') },
                dataType : 'json', // data type
                data : { 'delitems':  todelete}, // post data || get data
                success : function(result) { update_list(result); },
                error: function(xhr, resp, text) {
                    console.log(xhr, resp, text);
                }
            });
        });
    };

})(jQuery)