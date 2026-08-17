/* Recipient autocomplete for [name$="-recipients"], -bcc, -cc fields.
 *
 * Reads the endpoint from window.AN_URLS.autocomplete (set inline per page).
 * Shared by newsletter.html and email_notification.html.
 */
(function () {
    'use strict';

    function getUrl() {
        return (window.AN_URLS && window.AN_URLS.autocomplete) || '';
    }

    var timer = null;

    function getOrCreateDropdown($input) {
        var $dd = $input.next('.ac-dropdown');
        if (!$dd.length) {
            $dd = $('<div class="ac-dropdown"></div>').css({
                width: $input.outerWidth() + 'px',
                display: 'none'
            });
            $input.after($dd);
        }
        return $dd;
    }

    $(document).on('input',
        '[name$="-recipients"], [name$="-bcc"], [name$="-cc"]', function () {
            var url = getUrl();
            if (!url) { return; }
            var $input = $(this);
            clearTimeout(timer);
            timer = setTimeout(function () {
                var parts = $input.val().split(',');
                var query = parts[parts.length - 1].trim();
                var $dd = getOrCreateDropdown($input);
                if (query.length < 2) { $dd.hide(); return; }
                fetch(url + '?q=' + encodeURIComponent(query))
                    .then(function (r) { return r.text(); })
                    .then(function (html) {
                        if (!html.trim()) { $dd.hide(); return; }
                        $dd.html(html).show();
                    });
            }, 300);
        });

    $(document).on('click', '.ac-dropdown .autocomplete-item', function () {
        var value = $(this).data('value');
        var $dd = $(this).closest('.ac-dropdown');
        var $input = $dd.prev('input');
        var parts = $input.val().split(',');
        parts[parts.length - 1] = ' ' + value;
        $input.val(parts.join(',') + ', ');
        $dd.hide();
        $input.focus();
    });

    $(document).on('focusout',
        '[name$="-recipients"], [name$="-bcc"], [name$="-cc"]', function () {
            var $dd = $(this).next('.ac-dropdown');
            setTimeout(function () { $dd.hide(); }, 200);
        });
})();
