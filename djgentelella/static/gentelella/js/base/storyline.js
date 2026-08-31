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
                var storyline = new Storyline(instance_element, msg);
                window.storyline = storyline;
                // Storyline's own init() fetches/builds the chart+slider
                // asynchronously; this.slider does not exist until that
                // promise resolves, so resetWidth() would throw if called
                // right away.
                (function waitForSlider() {
                    if (storyline.slider) {
                        storyline.resetWidth(widget_width, 'scroll');
                    } else {
                        setTimeout(waitForSlider, 20);
                    }
                })();
            });
        });
}