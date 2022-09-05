function load_date_range(instance, format='DD/MM/YYYY') {
    var options = {
        'autoUpdateInput': false,
         'locale': {
            format: format,
        }
    };
    if ($(instance).val().length > 0) {
        let days = $(instance).val().split('-');
        options["startDate"] =  days[0];
        options["endDate"] = days[1];
    }
    return options;
}

function load_datetime_range(instance, format='DD/MM/YYYY HH:mm A') {
    var options = {
        'timePicker': true,
        'timePicker24Hour': true,
        'startDate': moment().startOf('hour'),
        'endDate': moment().startOf('hour').add(32, 'hour'),
        'locale': {
            format: format
        }
    };
    if ($(instance).val().length > 0) {
        let days = $(instance).val().split('-');
        options = {
            'timePicker': true,
            'timePicker24Hour': true,
            'startDate': days[0],
            'endDate': days[1],
            'locale': {
                format: format
            }
        }
    }
    return options;
}

function load_date_range_custom(instance, format='DD/MM/YYYY') {
    var options = {
        startDate: moment().startOf('hour'),
        endDate: moment().startOf('hour').add(32, 'hour'),
        ranges: {
            'Last 7 Days': [moment().subtract(6, 'days'), moment()],
            'Next Week': [moment(), moment().add(7, 'days')],
            'Last 30 Days': [moment().subtract(29, 'days'), moment()],
            'This Month': [moment().startOf('month'), moment().endOf('month')],
            'Last Month': [moment().subtract(1, 'month').startOf('month'), moment().subtract(1, 'month').endOf('month')]
        },
        locale: {
            format: format,
        }
    }
    if ($(instance).val().length > 0) {
        let days = $(instance).val().split('-');
        options = {
            "startDate": days[0],
            "endDate": days[1],
            'ranges': {
                'Last 7 Days': [moment(days[0], format).subtract(6, 'days'), moment(days[0], format)],
                'Next Week': [moment(days[0], format), moment(days[0], format).add(7, 'days')],
                'Last 30 Days': [moment(days[0], format).subtract(29, 'days'), moment(days[0], format)],
                'This Month': [moment(days[0], format).startOf('month'), moment(days[0], format).endOf('month')],
                'Last Month': [moment(days[0], format).subtract(1, 'month').startOf('month'), moment(days[0], format).subtract(1, 'month').endOf('month')]
            },
            'locale': {
                format: format,
            }
        }
    }
    return options;
}

function grid_slider(instance) {
    let obj = $(instance[0]);

    let to = obj.attr('data-from_max');

    let from = obj.attr('data-from_min');

    if ($("input[name=" + obj.attr('data-target-to') + "]").val() > 200) {
        to = $("input[name=" + obj.attr('data-target-to') + "]").val()
    }

    if ($("input[name=" + obj.attr('data-target-from') + "]").val() > 200) {
        from = $("input[name=" + obj.attr('data-target-from') + "]").val()
    }

    let option = {
        'min': obj.attr('data-min'),
        'max': obj.attr('data-max'),
        'from': from,
        'to': to,
        'type': 'double',
        'step': obj.attr('data-step'),
        'prefix': obj.attr('data-prefix'),
        'from_fixed': obj.attr('data-from_fixed') === 'true',
        'to_fixed': obj.attr('data-to_fixed') === 'true',
        'to_max': obj.attr('data-to_max'),
        'hide_min_max': obj.attr('data-hide_min_max'),
        'grid': true,
        'onChange': function (data) {
            $("input[name=" + obj.attr('data-target-from') + "]").val(data.from);
            $("input[name=" + obj.attr('data-target-to') + "]").val(data.to);
            console.log(obj.attr('data-target-to'));
        }
    }
    return option;
}
function grid_slider_single(instance) {
    let obj = $(instance[0]);


    let from = obj.attr('data_from');

    if ($("input[name=" + obj.attr('data-target') + "]").val() > 0) {
        from = $("input[name=" + obj.attr('data-target') + "]").val()
    }

    let option = {
        'min': obj.attr('data-min'),
        'max': obj.attr('data-max'),
        'from': from,
        'type': 'single',
        'prefix': obj.attr('data-prefix'),
        'grid': true,
        'onChange': function (data) {
            $("input[name=" + obj.attr('data-target') + "]").val(data.from);
        }
    }
    return option;
}
function date_grid_slider(instance) {

    let obj = $(instance);
    let input = $("input[name=" + obj.attr('data-target') + "]").val();

    function dateToTS(date) {
        return date.valueOf();
    }

    function tsToDate(ts) {
        var lang = "en-US";
        var d = new Date(ts);

        return d.toLocaleDateString(lang, {
            year: 'numeric',
            month: 'long',
            day: 'numeric',
            hour: 'numeric',
            minute: 'numeric',
            hour12: false,


        });
    }

    instance.ionRangeSlider({
        type: "single",
        hide_min_max: false,
        min: dateToTS(new Date(obj.attr('data_min'))),
        max: dateToTS(new Date(obj.attr('data_max'))),
        from: dateToTS(new Date(input != undefined ? input : obj.attr('data_from'))),
        prettify: tsToDate,
        onChange: function (data) {
            var day = new Date(data.from);
            day = day.getFullYear() + "-" + (day.getMonth() + 1) + "-" + day.getDate() + " " + day.getHours() + ":" + day.getMinutes()
            $("input[name=" + obj.attr('data-target') + "]").val(day);
        }
    })
}
