function build_mapbased_storymap(instance) {
    instance.each(function(index, element) {
        var instanceid = document.getElementById(element.id).id;
        var data_url = element.getAttribute('data-url');

        var storymap = new KLStoryMap.StoryMap(instanceid, data_url);

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