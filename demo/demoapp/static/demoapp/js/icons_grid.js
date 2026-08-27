/* Shared searchable grid for the icon reference pages.
 *
 * None of the icon sets ship a name list: friconix declares a `paths` global,
 * Font Awesome and MDI declare one CSS rule per icon, and the flags sprite is a
 * document of <symbol> elements. Each page reads its own set from whatever it
 * already loaded, so a grid can never drift from the version loaddevstatic
 * downloaded.
 */

/* Every icon name a stylesheet declares, from rules like `.mdi-abacus::before`.
 * Same-origin only -- a cross-origin sheet throws on .cssRules and is skipped,
 * which is fine because every icon set here is served from our own static. */
function gt_icons_from_css(pattern) {
    var names = {};
    for (var i = 0; i < document.styleSheets.length; i++) {
        var rules;
        try {
            rules = document.styleSheets[i].cssRules;
        } catch (e) {
            continue;
        }
        if (!rules) continue;
        for (var j = 0; j < rules.length; j++) {
            var selector = rules[j].selectorText;
            if (!selector) continue;
            var parts = selector.split(',');
            for (var k = 0; k < parts.length; k++) {
                var match = pattern.exec(parts[k].trim());
                if (match) names[match[1]] = true;
            }
        }
    }
    return Object.keys(names).sort();
}

/* options:
 *   names    -> array of icon names, or a Promise of one
 *   markup   -> function(name) returning the icon's HTML
 *   grid     -> selector of the container (default '#icon-grid')
 *   search   -> selector of the filter input (default '#icon-search')
 *   count    -> selector of the counter (default '#icon-count')
 *   controls -> extra selectors that also trigger a re-render
 *   empty    -> message when nothing matches
 */
function gt_icons_grid(options) {
    var $grid = $(options.grid || '#icon-grid');
    var $search = $(options.search || '#icon-search');
    var $count = $(options.count || '#icon-count');
    var all = [];

    function render() {
        var term = $search.val().trim().toLowerCase();
        var shown = term ? all.filter(function (name) {
            return name.indexOf(term) !== -1;
        }) : all;
        $grid.html(shown.map(function (name) {
            return '<div class="col-6 col-md-3 col-lg-2 text-center mb-3">' +
                   '<div style="font-size:2rem;min-height:2.4rem">' +
                   options.markup(name) + '</div>' +
                   '<code class="small">' + name + '</code></div>';
        }).join('') || '<div class="col-12 text-muted">' +
                       (options.empty || 'No icon matches.') + '</div>');
        // Friconix converts <i> to SVG only on page load; the grid is built
        // afterwards and rebuilt on every keystroke.
        if (typeof gt_friconix_refresh === 'function') {
            gt_friconix_refresh();
        }
    }

    function start(names) {
        all = names;
        $count.text(names.length);
        $search.add(options.controls || '').on('input', render);
        render();
    }

    if (options.names && typeof options.names.then === 'function') {
        options.names.then(start);
    } else {
        start(options.names);
    }
    return {refresh: render};
}
