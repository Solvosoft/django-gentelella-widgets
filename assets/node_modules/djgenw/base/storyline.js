function build_storyline(instance){
        instance.each(function (index, element) {
            var instance_element = element.id;
            if (element.attributes['width'] != undefined){
                var widget_width = element.attributes['width'].value;
            }else{
                var widget_width = element.parentNode.offsetWidth-100;
            }

            url = element.attributes['data-url'].value;
            $.ajax({
                method: "GET",
                url: url,
                dataType: "json",
                error: function(e) {
                    $(element).html('<div>'+e.responseText+'</div>');
                },
            }).done(function(msg){
                window.storyline = new Storyline(instance_element, msg);
                window.storyline.resetWidth(widget_width, 'scroll');
            });
        });
}