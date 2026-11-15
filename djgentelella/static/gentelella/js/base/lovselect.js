/**
  LOVSelect / LOVSelectMultiple (djgentelella.widgets.lov): a select2 fed by
  `gtapis/lov/<name>/`.

  `data-lov-depends` maps each parameter of the LOV to the form field that
  holds it; the values of those fields go with every request, and when one of
  them changes the select is emptied with the `refresh` dynamic action
  (document.gtdynamic.refresh), so a canton cannot outlive its province.
**/
function gt_lov_select(instance) {
    instance.each(function (i, el) {
        var $el = $(el);
        var depends = {};
        try {
            depends = JSON.parse(el.getAttribute('data-lov-depends') || '{}');
        } catch (e) {
            console.error('LOVSelect: invalid data-lov-depends', e);
        }
        var prefix = el.getAttribute('data-lov-prefix');
        if (prefix === null) {
            // A widget without its LOVChoiceField: its own name minus the field.
            var cut = el.name.lastIndexOf('-');
            prefix = cut === -1 ? '' : el.name.substring(0, cut);
        }
        var scope = $el.closest('form');
        if (!scope.length) scope = $(document.body);
        var fullName = function (name) { return prefix ? prefix + '-' + name : name; };
        var parentValue = function (name) {
            var target = fullName(name);
            var field = scope.find('input, select, textarea').filter(function () {
                return this.name === target;
            });
            if (!field.length) return '';
            if (field[0].type === 'checkbox' || field[0].type === 'radio') {
                return field.filter(':checked').map(function () { return this.value; }).get().join(',');
            }
            var v = field.val();
            if (Array.isArray(v)) return v.join(',');
            return v === null || v === undefined ? '' : v;
        };

        var context = {
            placeholder: gettext('Select an element'),
            allowClear: !el.multiple,
            ajax: {
                url: el.getAttribute('data-url'),
                type: 'GET',
                dataType: 'json',
                delay: 250,
                data: function (params) {
                    var query = {q: params.term || '', page: params.page || 1};
                    Object.keys(depends).forEach(function (param) {
                        query[param] = parentValue(depends[param]);
                    });
                    return query;
                }
            }
        };
        extract_select2_context(context, $el);
        if ($el.hasClass('select2-hidden-accessible')) $el.select2('destroy');
        $el.select2(context);

        // Parent changes empty this select. Remember the parents' values so a
        // `change` that did not change anything (ObjectCRUD and select2
        // re-trigger it) does not wipe a value that is still valid.
        var parents = Object.keys(depends).map(function (param) { return fullName(depends[param]); });
        if (!parents.length) return;
        var last = {};
        parents.forEach(function (name) {
            last[name] = parentValue(name.substring(prefix ? prefix.length + 1 : 0));
        });
        // One namespace per element, kept on it: a re-initialisation (reopened
        // modal, api_list.js) replaces its own handler and nobody else's.
        var ns = $el.data('gtlovns');
        if (!ns) {
            ns = '.gtlov' + (++gt_lov_select.uid);
            $el.data('gtlovns', ns);
        }
        scope.off(ns).on('change' + ns, function (event) {
            var target = event.target;
            if (!target || parents.indexOf(target.name) === -1) return;
            var current = parentValue(target.name.substring(prefix ? prefix.length + 1 : 0));
            if (last[target.name] === current) return;
            last[target.name] = current;
            document.gtdynamic.refresh($el);
        });
    });
}
gt_lov_select.uid = 0;
