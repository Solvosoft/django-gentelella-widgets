function build_timeline(instances){
    instances.each(function (index, element) {
        var instanceid = element.id;
        var instance = $(element);
        var dataoptions = instance.data();
        var keys = Object.keys(dataoptions);
        var options = {}
        for (var x=0; x<keys.length; x++){
            if(keys[x].startsWith('option_')){
                 options[keys[x].replace('option_', '')] = dataoptions[keys[x]]
            }
        }
        timeline = new TL.Timeline(instanceid, instance.data('url'), options);
        window.addEventListener('resize', function() {
            var embed = document.getElementById(instanceid);
            embed.style.height = getComputedStyle(document.body).height;
            timeline.updateDisplay();
        })
    });
}