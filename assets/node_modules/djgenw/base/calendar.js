
function build_calendar(instance){
    instance.each(function (index, element) {
            var calendarEl = document.getElementById(element.id);
            var element_name = element.getAttribute('name')
            var widget_name = element_name.substring(0, element_name.length-8);
            events = window['events' + widget_name];
            calendar_options = window['calendar_options' + widget_name];
            calendar_options.events = events;
            var calendar = new FullCalendar.Calendar(calendarEl, calendar_options);
            calendar.render();
            $(element).closest("form").on("submit", function (event) {
                $(`#${widget_name}_events-input-src`).val(JSON.stringify(calendar.getEvents()));
            });
        });
}