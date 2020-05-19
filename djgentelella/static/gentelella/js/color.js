$(function () {

    $('.color-input-field').colorpicker()

    $('.color-input-field-horizontal').colorpicker({
        horizontal: true,
    })

    $('.color-input-field-vertical-rgb').colorpicker({
        format: 'rgb',
    })

    $('.color-input-field-inline-picker')
        .css("display", "inline-block")
        .colorpicker({
        container: true,
        inline: true
    })

});
