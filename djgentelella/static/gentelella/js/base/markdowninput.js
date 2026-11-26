/**
  MarkdownInput (djgentelella.widgets.markdown): toolbar and "Preview" tab.

  The preview is the html the server answers from gtapis/markdown/preview/,
  already cleaned by nh3 (djgentelella.markdown.render_markdown). The browser
  never turns the text into markup itself.
**/
function gt_markdown_wrap(textarea, before, after, placeholder) {
    var start = textarea.selectionStart;
    var end = textarea.selectionEnd;
    var value = textarea.value;
    var selected = value.substring(start, end) || placeholder;
    textarea.value = value.substring(0, start) + before + selected + after
        + value.substring(end);
    textarea.focus();
    textarea.setSelectionRange(start + before.length,
                               start + before.length + selected.length);
}

function gt_markdown_prefix(textarea, prefix) {
    var start = textarea.value.lastIndexOf('\n', textarea.selectionStart - 1) + 1;
    var end = textarea.selectionEnd;
    var lines = textarea.value.substring(start, end).split('\n');
    var block = lines.map(function (line, index) {
        return (typeof prefix === 'function' ? prefix(index) : prefix) + line;
    }).join('\n');
    textarea.value = textarea.value.substring(0, start) + block
        + textarea.value.substring(end);
    textarea.focus();
    textarea.setSelectionRange(start, start + block.length);
}

function gt_markdown_tool(textarea, tool) {
    switch (tool) {
        case 'bold': gt_markdown_wrap(textarea, '**', '**', gettext('bold text')); break;
        case 'italic': gt_markdown_wrap(textarea, '_', '_', gettext('italic text')); break;
        case 'code': gt_markdown_wrap(textarea, '`', '`', 'code'); break;
        case 'link': gt_markdown_wrap(textarea, '[', '](https://)', gettext('link text')); break;
        case 'heading': gt_markdown_prefix(textarea, '## '); break;
        case 'list': gt_markdown_prefix(textarea, '- '); break;
        case 'numbered': gt_markdown_prefix(textarea, function (i) { return (i + 1) + '. '; }); break;
        case 'quote': gt_markdown_prefix(textarea, '> '); break;
        default: return;
    }
    textarea.dispatchEvent(new Event('input', {bubbles: true}));
}

function gt_markdown_input(instance) {
    instance.each(function (i, textarea) {
        if (!gt_widget_once(textarea, 'Markdown')) return;
        var wrapper = textarea.closest('.gt-markdown');
        var preview = wrapper.querySelector('.gt-markdown-preview');
        var writeTab = wrapper.querySelector('.gt-markdown-write');
        var previewTab = wrapper.querySelector('.gt-markdown-preview-tab');
        var toolbar = wrapper.querySelector('.gt-markdown-toolbar');
        // Bumped by each tab change: a late preview answer is dropped.
        var request = 0;

        var showWrite = function () {
            request++;
            writeTab.classList.add('active');
            previewTab.classList.remove('active');
            preview.classList.add('d-none');
            textarea.classList.remove('d-none');
            if (toolbar) toolbar.classList.remove('d-none');
        };
        var showPreview = function () {
            previewTab.classList.add('active');
            writeTab.classList.remove('active');
            textarea.classList.add('d-none');
            if (toolbar) toolbar.classList.add('d-none');
            preview.classList.remove('d-none');
            preview.textContent = gettext('Loading...');
            var current = ++request;
            // The token of the form first: a project with CSRF_COOKIE_HTTPONLY
            // has no readable cookie.
            var tokenInput = textarea.form
                ? textarea.form.querySelector('[name="csrfmiddlewaretoken"]') : null;
            var token = tokenInput ? tokenInput.value : getCookie('csrftoken');
            var body = new FormData();
            body.append('text', textarea.value);
            fetch(textarea.getAttribute('data-preview-url'), {
                method: 'POST', body: body, credentials: 'same-origin',
                headers: {'X-CSRFToken': token}
            }).then(function (response) {
                return response.json().then(function (data) {
                    if (!response.ok) throw new Error(data.error || response.status);
                    return data;
                });
            }).then(function (data) {
                if (current !== request) return;
                // Cleaned on the server by nh3: see render_markdown().
                preview.innerHTML = data.html;
                preview.classList.add('gt-markdown-rendered');
            }).catch(function (error) {
                if (current !== request) return;
                preview.textContent = error.message;
            });
        };
        writeTab.addEventListener('click', showWrite);
        previewTab.addEventListener('click', showPreview);
        if (toolbar) {
            toolbar.querySelectorAll('[data-md]').forEach(function (button) {
                button.addEventListener('click', function () {
                    gt_markdown_tool(textarea, button.getAttribute('data-md'));
                });
            });
        }
    });
}
