function build_gigapixel_storymap(instance) {
    instance.each(function(index, element) {
        var instanceid = document.getElementById(element.id).id;
        var data_url = element.getAttribute('data-url');
        var storymap_options = element.getAttribute('storymap_options');

        var storymap = new VCO.StoryMap(instanceid, data_url, storymap_options);

        var e = $(window).height(),
        t = $(`#${instanceid}`);
        t.height(e - 20);

        $(window).resize(function() {
            e = $(window).height();
            t.height(e - 20);
            storymap.updateDisplay();
        });
    })
}