
// Live engines by container id, same reason maplib.js keeps _gt_maps: a
// container re-render (modal reopened, formset row cloned) calls
// build_calendar again for a node FullCalendar already owns, and re-creating
// it on the same element leaks the old listeners.
var _gt_calendars = {};

function _gt_calendar_pad(n) {
    return n < 10 ? '0' + n : '' + n;
}

// FullCalendar hands the detail popover a Date; the add/edit POSTs need a
// "YYYY-MM-DD" / "HH:MM" pair back for their own date/time inputs.
function _gt_calendar_date_str(date) {
    return date.getFullYear() + '-' + _gt_calendar_pad(date.getMonth() + 1) +
        '-' + _gt_calendar_pad(date.getDate());
}

function _gt_calendar_time_str(date) {
    return _gt_calendar_pad(date.getHours()) + ':' + _gt_calendar_pad(date.getMinutes());
}

// Matches DateInput/TimeInput's own init (widgets.js): sideBySide time icons,
// format read from data-format. Guarded so a rebuild doesn't attach the
// plugin twice to the same, still-live modal input.
function _gt_calendar_init_picker(selector, format) {
    var el = $(selector);
    if (el.length && !el.data('DateTimePicker')) {
        el.datetimepicker({
            format: format,
            sideBySide: format.indexOf('H') !== -1,
            icons: {time: "fa fa-clock-o", up: "fa fa-arrow-up", down: "fa fa-arrow-down"}
        });
    }
}

// .val(string) alone leaves the plugin's own moment object stale, so the
// next time it opens it can highlight the wrong day/hour even though the
// text reads right -- go through its API when the plugin is attached.
function _gt_calendar_set_picker_value(selector, value) {
    var el = $(selector);
    var picker = el.data('DateTimePicker');
    if (picker) {
        picker.date(value);
    } else {
        el.val(value);
    }
}

function build_calendar(instance){
    instance.each(function (index, element) {
            if (_gt_calendars[element.id]) {
                _gt_calendars[element.id].destroy();
            }

            var calendarEl = document.getElementById(element.id);
            var element_name = element.getAttribute('name')
            var widget_name = element_name.substring(0, element_name.length-8);
            var add_url = element.getAttribute('data-add-url');
            var update_url = element.getAttribute('data-update-url');
            var delete_url = element.getAttribute('data-delete-url');

            events = window['events' + widget_name];
            calendar_options = window['calendar_options' + widget_name];
            calendar_options.events = events;

            // A day cell caps its own height (see the widget's <style>) and
            // scrolls once it has more events than fit, rather than growing
            // and dragging every other row in the month down with it.
            calendar_options.dayMaxEvents = false;

            // The description lives in extendedProps, not a core FullCalendar
            // field, so it never shows in the day cell -- only here, on
            // hover, via a Bootstrap tooltip torn down and rebuilt with the
            // event each time (Tooltip instances don't survive their trigger
            // element being re-rendered).
            calendar_options.eventDidMount = function (info) {
                var description = info.event.extendedProps &&
                    info.event.extendedProps.description;
                if (description) {
                    info.el.setAttribute('data-bs-toggle', 'tooltip');
                    info.el.setAttribute('title', description);
                    new bootstrap.Tooltip(info.el);
                }
            };

            // Set once per build, read by the Save/Delete handlers below --
            // eventClick is the only place that knows which FullCalendar
            // Event is open in the (single, reused) detail modal.
            var openEvent = null;

            calendar_options.eventClick = function (info) {
                info.jsEvent.preventDefault();
                var event = info.event;
                openEvent = event;
                var modalEl = document.getElementById(widget_name + '_detail_modal');
                modalEl.dataset.eventId = event.id;

                if (update_url) {
                    $('#' + widget_name + '_detail_title_input').val(event.title || '');
                    $('#' + widget_name + '_detail_color_input').val(
                        event.backgroundColor || '#4e73df');
                    $('#' + widget_name + '_detail_description_input').val(
                        (event.extendedProps && event.extendedProps.description) || '');
                    if (event.start) {
                        _gt_calendar_set_picker_value(
                            '#' + widget_name + '_detail_date_input',
                            _gt_calendar_date_str(event.start));
                        _gt_calendar_set_picker_value(
                            '#' + widget_name + '_detail_time_input',
                            _gt_calendar_time_str(event.start));
                    }
                } else {
                    $('#' + widget_name + '_detail_title').text(event.title || '');
                    $('#' + widget_name + '_detail_start').text(
                        event.start ? event.start.toLocaleString() : '');
                    if (event.end) {
                        $('#' + widget_name + '_detail_end').text(event.end.toLocaleString());
                        $('#' + widget_name + '_detail_end_p').show();
                    } else {
                        $('#' + widget_name + '_detail_end_p').hide();
                    }
                }
                new bootstrap.Modal(modalEl).show();
            };

            if (add_url) {
                calendar_options.dateClick = function (info) {
                    var modalEl = document.getElementById(widget_name + '_add_modal');
                    $('#' + widget_name + '_add_title').val('');
                    _gt_calendar_set_picker_value('#' + widget_name + '_add_date', info.dateStr);
                    _gt_calendar_set_picker_value('#' + widget_name + '_add_time', '08:00');
                    $('#' + widget_name + '_add_color').val('#4e73df');
                    $('#' + widget_name + '_add_description').val('');
                    new bootstrap.Modal(modalEl).show();
                };
            }

            _gt_calendar_init_picker('#' + widget_name + '_add_date', 'YYYY-MM-DD');
            _gt_calendar_init_picker('#' + widget_name + '_add_time', 'HH:mm');
            _gt_calendar_init_picker('#' + widget_name + '_detail_date_input', 'YYYY-MM-DD');
            _gt_calendar_init_picker('#' + widget_name + '_detail_time_input', 'HH:mm');

            var calendar = new FullCalendar.Calendar(calendarEl, calendar_options);
            calendar.render();
            _gt_calendars[element.id] = calendar;

            if (add_url) {
                // Rebound every build_calendar call (a re-render swaps the
                // modal's DOM node too), so no stale closure over a dead
                // `calendar` from a previous instance.
                $('#' + widget_name + '_add_save').off('click').on('click', function () {
                    var modalEl = document.getElementById(widget_name + '_add_modal');
                    var title = $('#' + widget_name + '_add_title').val();
                    var date = $('#' + widget_name + '_add_date').val();
                    var time = $('#' + widget_name + '_add_time').val() || '00:00';
                    var color = $('#' + widget_name + '_add_color').val();
                    var description = $('#' + widget_name + '_add_description').val();
                    if (!title || !date) return;
                    $.ajax({
                        url: add_url,
                        type: 'POST',
                        data: {
                            title: title, start: date + 'T' + time,
                            color: color, description: description
                        },
                        headers: {'X-CSRFToken': getCookie('csrftoken')},
                        success: function (data) {
                            calendar.addEvent(data);
                            bootstrap.Modal.getInstance(modalEl).hide();
                        },
                        error: function (error) {
                            console.log(error);
                        }
                    });
                });
            }

            if (update_url) {
                $('#' + widget_name + '_detail_save').off('click').on('click', function () {
                    var modalEl = document.getElementById(widget_name + '_detail_modal');
                    var title = $('#' + widget_name + '_detail_title_input').val();
                    var date = $('#' + widget_name + '_detail_date_input').val();
                    var time = $('#' + widget_name + '_detail_time_input').val() || '00:00';
                    var color = $('#' + widget_name + '_detail_color_input').val();
                    var description = $('#' + widget_name + '_detail_description_input').val();
                    if (!title || !date || !openEvent) return;
                    $.ajax({
                        url: update_url,
                        type: 'POST',
                        data: {
                            id: modalEl.dataset.eventId, title: title,
                            start: date + 'T' + time, color: color,
                            description: description
                        },
                        headers: {'X-CSRFToken': getCookie('csrftoken')},
                        success: function (data) {
                            openEvent.setProp('title', data.title);
                            openEvent.setStart(data.start);
                            openEvent.setProp('backgroundColor', data.color);
                            openEvent.setProp('borderColor', data.color);
                            openEvent.setExtendedProp('description', data.description);
                            bootstrap.Modal.getInstance(modalEl).hide();
                        },
                        error: function (error) {
                            console.log(error);
                        }
                    });
                });
            }

            if (delete_url) {
                $('#' + widget_name + '_detail_delete').off('click').on('click', function () {
                    var modalEl = document.getElementById(widget_name + '_detail_modal');
                    if (!openEvent) return;
                    $.ajax({
                        url: delete_url,
                        type: 'POST',
                        data: {id: modalEl.dataset.eventId},
                        headers: {'X-CSRFToken': getCookie('csrftoken')},
                        success: function () {
                            openEvent.remove();
                            bootstrap.Modal.getInstance(modalEl).hide();
                        },
                        error: function (error) {
                            console.log(error);
                        }
                    });
                });
            }

            $(element).closest("form").on("submit", function (event) {
                $(`#${widget_name}_events-input-src`).val(JSON.stringify(calendar.getEvents()));
            });
        });
}
