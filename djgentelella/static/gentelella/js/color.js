$(function () {
    $('.color-input-field').colorpicker({"color": "#2630a9"})

    $('.color-input-field-horizontal').colorpicker({
        color: "#88cc33",
        horizontal: true,
        //format: 'rgb',
    })

    $('.color-input-field-vertical-rgb').colorpicker({
        color: "#88cc33",
        format: 'rgb',
    })
});
