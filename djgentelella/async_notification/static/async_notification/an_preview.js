/* Shared preview + helpers for the async_notification admin GUI.
 *
 * Requires window.AN_URLS.preview_template (set inline per page) and the
 * global getCookie() helper from djgentelella.
 */
(function () {
    'use strict';

    window.AN = window.AN || {};

    /* Read TinyMCE content for a [name$="-message"] textarea inside $scope. */
    function getMessage($scope) {
        var $textarea = $scope.find('textarea[name$="-message"]');
        if ($textarea.length && typeof tinymce !== 'undefined') {
            var editor = tinymce.get($textarea.attr('id'));
            if (editor) { return editor.getContent(); }
        }
        return $scope.find('[name$="-message"]').val() || '';
    }

    /* Render the message (+base_template, +context_code) into an iframe.
     * $scope is a modal or container holding the fields and a .preview-frame
     * (or .an-preview-frame). Optionally pass explicit values in `opts`.
     */
    window.AN.preview = function ($scope, opts) {
        opts = opts || {};
        var url = window.AN_URLS && window.AN_URLS.preview_template;
        if (!url) { return; }
        var $iframe = $scope.find('.preview-frame, .an-preview-frame').first();
        var message = (opts.message !== undefined)
            ? opts.message : getMessage($scope);
        var baseTemplate = (opts.base_template !== undefined)
            ? opts.base_template
            : ($scope.find('[name$="-base_template"]').val() || '');
        var contextCode = (opts.context_code !== undefined)
            ? opts.context_code
            : ($scope.find('[name$="-context_code"]').val() || '');

        var body = 'message=' + encodeURIComponent(message) +
            '&base_template=' + encodeURIComponent(baseTemplate) +
            '&context_code=' + encodeURIComponent(contextCode);

        fetch(url, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCookie('csrftoken'),
                'Content-Type': 'application/x-www-form-urlencoded'
            },
            body: body
        }).then(function (r) { return r.json(); })
            .then(function (data) {
                if ($iframe.length) { $iframe[0].srcdoc = data.preview; }
            });
    };

    /* DataTables render helper: a colored status badge.
     * @param {Array} choices - Optional array of [value, label] pairs for translation.
     */
    window.AN.statusBadge = function (choices) {
        return function (data) {
            if (!data) { return ''; }
            var label = data;
            if (choices) {
                for (var i = 0; i < choices.length; i++) {
                    if (choices[i][0] === data) {
                        label = choices[i][1];
                        break;
                    }
                }
            }
            var safe = $('<span>').text(label).html();
            return '<span class="an-badge an-badge-' + data + '">' +
                safe + '</span>';
        };
    };

    /* Wire a .btn-preview-template button inside any modal/container. */
    $(document).on('click', '.btn-preview-template', function () {
        window.AN.preview($(this).closest('.modal, .an-editor-preview'));
    });
})();
