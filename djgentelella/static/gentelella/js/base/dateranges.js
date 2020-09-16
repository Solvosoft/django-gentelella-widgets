function load_date_range(instance) {
    var options = {
        'startDate': moment().startOf('hour'),
        'endDate': moment().startOf('hour').add(32, 'hour'),
        'locale': {
            format: 'DD/MM/YYYY',
        }
    };
    if ($(instance).val().length > 0) {
        let days = $(instance).val().split('-');
        options = {
            "startDate": days[0],
            "endDate": days[1],
            'locale': {
                format: 'DD/MM/YYYY',
            }
        }
    }
    return options;
}
function load_datetime_range(instance) {
    var options = {
        'timePicker': true,
        'timePicker24Hour': true,
        'startDate': moment().startOf('hour'),
        'endDate': moment().startOf('hour').add(32, 'hour'),
        'locale': {
            format: 'DD/MM/YYYY HH:mm A'
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
                format: 'DD/MM/YYYY HH:mm A'
            }
        }
    }
    return options;
}
function load_date_range_custom(instance) {
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
            format: 'DD/MM/YYYY',
        }
    }
    if ($(instance).val().length > 0) {
        let days = $(instance).val().split('-');
        options = {
            "startDate": days[0],
            "endDate": days[1],
            'ranges': {
                'Last 7 Days': [moment(days[0], "DD/MM/YYYY").subtract(6, 'days'), moment(days[0], "DD/MM/YYYY")],
                'Next Week': [moment(days[0], "DD/MM/YYYY"), moment(days[0], "DD/MM/YYYY").add(7, 'days')],
                'Last 30 Days': [moment(days[0], "DD/MM/YYYY").subtract(29, 'days'), moment(days[0], "DD/MM/YYYY")],
                'This Month': [moment(days[0], "DD/MM/YYYY").startOf('month'), moment(days[0], "DD/MM/YYYY").endOf('month')],
                'Last Month': [moment(days[0], "DD/MM/YYYY").subtract(1, 'month').startOf('month'), moment(days[0], "DD/MM/YYYY").subtract(1, 'month').endOf('month')]
            },
            'locale': {
                format: 'DD/MM/YYYY',
            }
        }
    }
    return options;
}

