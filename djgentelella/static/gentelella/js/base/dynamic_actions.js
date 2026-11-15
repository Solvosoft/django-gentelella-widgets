/**
  Dynamic actions runtime (djgentelella.forms.dynamic).

  GTForm renders its rules as json in a `data-gt-dynamic` attribute, on a
  hidden `.gt-dynamic-actions` element inside the form (or on the <form> tag
  itself through `form.dynamic_actions_attrs`). gt_find_initialize() calls
  gt_dynamic_initialize() for every container it boots, so the rules start on
  page load, in a formset row cloned by formset.js and in anything else
  re-initialised; a form inside a modal is evaluated again each time the modal
  opens, after ObjectCRUD has filled it.

  Fields are looked up by name, `<prefix>-<field>` when the form has a prefix,
  inside the closest <form>.

  Everything that reaches the page from the rules is treated as data: values go
  through .val()/.prop(), messages through textContent, never through html.

  document.gtdynamic.register(name, fn) registers the functions the `call`
  action runs; fn receives a context object (see `context()` below).
**/
(function () {
    var REVERSE = {
        'show': 'hide', 'hide': 'show', 'enable': 'disable', 'disable': 'enable',
        'require': 'unrequire', 'add_class': 'remove_class', 'remove_class': 'add_class'
    };
    var CONDITIONS = ['equals', 'not_equals', 'in', 'gt', 'lt', 'is_empty', 'is_checked'];
    var MAX_DEPTH = 10;
    var uid = 0;

    function parseJSON(text, fallback) {
        if (text === null || text === undefined || text === '') return fallback;
        try {
            return JSON.parse(text);
        } catch (e) {
            console.error('gtdynamic: invalid json', e);
            return fallback;
        }
    }

    function isEmpty(v) {
        return v === null || v === undefined || v === '' || v === false ||
            (Array.isArray(v) && v.length === 0);
    }

    function toNumber(v) {
        if (v === null || v === undefined || v === '' || typeof v === 'boolean') return NaN;
        var text = String(v).trim();
        if (text.indexOf('.') === -1) text = text.replace(',', '.');
        return Number(text);
    }

    function equals(expected, v) {
        if (Array.isArray(v)) {
            return v.map(String).indexOf(String(expected)) !== -1;
        }
        if (typeof v === 'boolean') {
            if (typeof expected === 'boolean') return v === expected;
            return String(v) === String(expected).toLowerCase();
        }
        if (v === null || v === undefined) v = '';
        if (expected === null) expected = '';
        return String(v) === String(expected);
    }

    function test(trigger, expected, v) {
        switch (trigger) {
            case 'equals': return equals(expected, v);
            case 'not_equals': return !equals(expected, v);
            case 'in': return (expected || []).some(function (item) { return equals(item, v); });
            case 'gt': var n = toNumber(v); return !isNaN(n) && n > Number(expected);
            case 'lt': var m = toNumber(v); return !isNaN(m) && m < Number(expected);
            case 'is_empty': return isEmpty(v);
            case 'is_checked': return v === true || (Array.isArray(v) && v.length > 0);
        }
        return false;
    }

    function csrfToken(scope) {
        var input = scope.find('input[name="csrfmiddlewaretoken"]').first();
        if (input.length) return input.val();
        var match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
        return match ? decodeURIComponent(match[1]) : '';
    }

    function askConfirm(message) {
        if (typeof Swal !== 'undefined' && Swal.fire) {
            return Swal.fire({
                // `text`, not `html`: the message is data.
                text: message,
                icon: 'question',
                showCancelButton: true,
                confirmButtonText: gettext('Yes'),
                cancelButtonText: gettext('Cancel'),
                customClass: {container: 'gt-dynamic-confirm'}
            }).then(function (result) { return !!result.isConfirmed; });
        }
        return Promise.resolve(window.confirm(message));
    }

    function GTDynamicForm(marker) {
        this.id = ++uid;
        this.marker = $(marker);
        this.rules = parseJSON(marker.getAttribute('data-gt-dynamic'), []);
        this.prefix = marker.getAttribute('data-gt-dynamic-prefix') || '';
        this.fields = parseJSON(marker.getAttribute('data-gt-dynamic-fields'), []);
        this.url = marker.getAttribute('data-gt-dynamic-url');
        this.scope = marker.tagName === 'FORM' ? this.marker : this.marker.closest('form');
        if (!this.scope.length) this.scope = this.marker.parent();
        // The depth of the change being handled while setValue() runs: the
        // `change` it triggers belongs to the same cascade, one level deeper.
        this.cascade = null;
        this.previous = {};
        // The value each watched field had when its last change was handled:
        // the date picker reports a pick with `dp.change` *and* the input then
        // fires `change`, and select2/ObjectCRUD re-trigger `change` with the
        // same value. Only a real change runs the rules.
        this.seen = {};
        this.watched = {};
        var self = this;
        this.rules.forEach(function (rule) {
            (rule.when || []).forEach(function (name) { self.watched[name] = true; });
        });
    }

    GTDynamicForm.prototype = {
        fullName: function (name) {
            return this.prefix ? this.prefix + '-' + name : name;
        },
        bareName: function (fullname) {
            if (!this.prefix) return fullname;
            var start = this.prefix + '-';
            return fullname.indexOf(start) === 0 ? fullname.substring(start.length) : null;
        },
        elements: function (name) {
            var fullname = this.fullName(name);
            return this.scope.find('input, select, textarea').filter(function () {
                return this.name === fullname;
            });
        },
        container: function (name) {
            var els = this.elements(name);
            var box = els.first().closest('.gtformfield');
            if (!box.length) box = els.first().closest('.form-group, .mb-3, .row');
            return box.length ? box : els;
        },
        value: function (name) {
            var els = this.elements(name);
            if (!els.length) return null;
            var first = els[0];
            if (first.type === 'checkbox') {
                if (els.length === 1) return first.checked;
                return els.filter(':checked').map(function () { return this.value; }).get();
            }
            if (first.type === 'radio') {
                var checked = els.filter(':checked');
                return checked.length ? checked.val() : '';
            }
            var v = $(first).val();
            if (first.multiple) return v || [];
            return v === undefined ? null : v;
        },
        collect: function () {
            var data = {};
            var self = this;
            this.fields.forEach(function (name) {
                if (self.elements(name).length) data[name] = self.value(name);
            });
            return data;
        },
        // `depth`: how many rule-driven changes led here. It travels with the
        // `change` event this triggers, through promises and server calls
        // too, so a cycle of rules stops after MAX_DEPTH changes.
        setValue: function (name, v, depth) {
            var els = this.elements(name);
            if (!els.length) return;
            var outer = this.cascade;
            if (depth !== undefined) this.cascade = depth;
            try {
                this.writeValue(els, v);
                els.first().trigger('change');
            } finally {
                this.cascade = outer;
            }
        },
        writeValue: function (els, v) {
            var first = els[0];
            if (first.type === 'checkbox' && els.length === 1) {
                $(first).prop('checked', v === true || v === 'true' || v === 'on' || v === 1);
            } else if (first.type === 'checkbox' || first.type === 'radio') {
                var wanted = (Array.isArray(v) ? v : [v]).map(String);
                els.each(function () { $(this).prop('checked', wanted.indexOf(this.value) !== -1); });
            } else if (first.tagName === 'SELECT') {
                var values = (Array.isArray(v) ? v : [v]).filter(function (x) {
                    return x !== null && x !== undefined && x !== '';
                }).map(String);
                values.forEach(function (x) {
                    var exists = $(first).find('option').filter(function () { return this.value === x; });
                    if (!exists.length) first.appendChild(new Option(x, x, false, false));
                });
                $(first).val(first.multiple ? values : (values.length ? values[0] : null));
            } else {
                $(first).val(v === null || v === undefined ? '' : v);
            }
        },
        context: function (rule, action, event, depth) {
            var self = this;
            return {
                form: self,
                scope: self.scope,
                prefix: self.prefix,
                rule: rule,
                args: action.args || [],
                event: event || null,
                field: function (name) { return self.elements(name); },
                value: function (name) { return self.value(name); },
                setValue: function (name, v) { self.setValue(name, v, (depth || 0) + 1); }
            };
        },
        state: function (rule) {
            var self = this;
            return (rule.when || []).every(function (name) {
                return test(rule.trigger, rule.value, self.value(name));
            });
        },
        // Reversible actions: apply them, or their inverses in reverse order.
        applyReversible: function (rule, positive) {
            var actions = rule.actions.filter(function (a) { return REVERSE[a.action]; });
            if (!positive) actions = actions.slice().reverse();
            for (var i = 0; i < actions.length; i++) {
                var name = positive ? actions[i].action : REVERSE[actions[i].action];
                this.simple(name, actions[i]);
            }
        },
        simple: function (name, action) {
            var self = this;
            (action.fields || []).forEach(function (field) {
                var els = self.elements(field);
                switch (name) {
                    case 'show': self.container(field).show(); break;
                    case 'hide': self.container(field).hide(); break;
                    case 'enable': els.prop('disabled', false); break;
                    case 'disable': els.prop('disabled', true); break;
                    case 'require':
                    case 'unrequire':
                        var on = name === 'require';
                        els.prop('required', on);
                        els.each(function () {
                            var id = this.id;
                            if (!id) return;
                            self.scope.find('label').filter(function () {
                                return this.htmlFor === id;
                            }).toggleClass('gt-required', on);
                        });
                        break;
                    case 'add_class': els.addClass(action.css); break;
                    case 'remove_class': els.removeClass(action.css); break;
                }
            });
        },
        // Runs `actions` one after the other; resolves false when a confirm
        // was declined, which stops the rest.
        run: function (rule, actions, event, depth) {
            var self = this;
            var chain = Promise.resolve(true);
            actions.forEach(function (action) {
                chain = chain.then(function (go) {
                    if (!go) return false;
                    return self.runAction(rule, action, event, depth || 0);
                });
            });
            return chain;
        },
        runAction: function (rule, action, event, depth) {
            var self = this;
            if (REVERSE[action.action]) {
                this.simple(action.action, action);
                return true;
            }
            switch (action.action) {
                case 'confirm':
                    return askConfirm(action.message);
                case 'refresh':
                    var outer = this.cascade;
                    this.cascade = depth + 1;
                    try {
                        (action.fields || []).forEach(function (name) {
                            document.gtdynamic.refresh(self.elements(name));
                        });
                    } finally {
                        this.cascade = outer;
                    }
                    return true;
                case 'call':
                    var fn = document.gtdynamic.functions[action.name];
                    if (typeof fn !== 'function') {
                        console.warn('gtdynamic: no function registered as', action.name);
                        return true;
                    }
                    return Promise.resolve(fn(self.context(rule, action, event, depth))).then(function (r) {
                        return r !== false;
                    });
                case 'set_value':
                    var target = (action.fields || [])[0];
                    if (action.server) return this.serverValue(action, depth);
                    if (action.hasOwnProperty('from')) {
                        this.setValue(target, this.value(action.from), depth + 1);
                    } else {
                        this.setValue(target, action.value, depth + 1);
                    }
                    return true;
            }
            return true;
        },
        serverValue: function (action, depth) {
            var self = this;
            if (!this.url) return true;
            return fetch(this.url, {
                method: 'POST',
                credentials: 'same-origin',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken(this.scope),
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify({token: action.server, data: this.collect()})
            }).then(function (response) {
                return response.json().then(function (body) {
                    if (!response.ok) {
                        console.error('gtdynamic: set_value failed', response.status, body);
                        self.scope.trigger('gtdynamic:error', [body]);
                        return true;
                    }
                    Object.keys(body).forEach(function (name) {
                        if (self.fields.indexOf(name) !== -1) self.setValue(name, body[name], depth + 1);
                    });
                    return true;
                });
            }).catch(function (error) {
                console.error('gtdynamic: set_value failed', error);
                return true;
            });
        },
        // Evaluates every condition (and on_load) without a user change.
        evaluate: function (initial) {
            var self = this;
            this.rules.forEach(function (rule) {
                if (CONDITIONS.indexOf(rule.trigger) !== -1) {
                    self.applyReversible(rule, self.state(rule));
                } else if (initial && rule.trigger === 'on_load') {
                    self.run(rule, rule.actions, null);
                }
            });
            this.remember();
        },
        remember: function () {
            var self = this;
            Object.keys(this.watched).forEach(function (name) {
                self.previous[name] = self.value(name);
                self.seen[name] = JSON.stringify(self.previous[name]);
            });
        },
        // `depth` is 0 for a change of the user and grows by one for each
        // change a rule makes in reaction (see setValue).
        onChange: function (name, event, depth) {
            var self = this;
            depth = depth || 0;
            if (depth >= MAX_DEPTH) {
                console.warn('gtdynamic: dynamic actions nested too deep, stopping at', name);
                return;
            }
            var chain = Promise.resolve(true);
            this.rules.forEach(function (rule) {
                if ((rule.when || []).indexOf(name) === -1) return;
                chain = chain.then(function (go) {
                    if (!go) return false;
                    if (rule.trigger === 'changes') {
                        return self.run(rule, rule.actions, event, depth);
                    }
                    if (CONDITIONS.indexOf(rule.trigger) === -1) return true;
                    var positive = self.state(rule);
                    self.applyReversible(rule, positive);
                    if (!positive) return true;
                    var others = rule.actions.filter(function (a) { return !REVERSE[a.action]; });
                    return self.run(rule, others, event, depth);
                });
            });
            chain.then(function (go) {
                if (go === false) {
                    // A confirm was declined: put the old value back.
                    var old = self.previous[name];
                    self.reverting = true;
                    try {
                        self.setValue(name, old);
                    } finally {
                        self.reverting = false;
                    }
                    self.evaluate(false);
                } else {
                    self.previous[name] = self.value(name);
                }
            });
        },
        bind: function () {
            var self = this;
            var ns = '.gtdynamic' + this.id;
            this.scope.off(ns).on('change' + ns + ' dp.change' + ns, function (event) {
                var target = event.target;
                if (!target || !target.name) return;
                var name = self.bareName(target.name);
                if (name === null || !self.watched[name]) return;
                var current = JSON.stringify(self.value(name));
                if (self.reverting) {
                    self.seen[name] = current;
                    return;
                }
                if (self.seen[name] === current) return;
                self.seen[name] = current;
                self.onChange(name, event, self.cascade || 0);
            });
            this.scope.on('reset' + ns, function () {
                setTimeout(function () { self.evaluate(false); }, 0);
            });
            var modal = this.scope.closest('.modal');
            if (modal.length) {
                modal.off(ns).on('show.bs.modal' + ns, function (event) {
                    if (event.target === modal[0]) self.evaluate(false);
                });
            }
        }
    };

    function initialize(container) {
        var root = $(container);
        var markers = root.find('[data-gt-dynamic]').addBack('[data-gt-dynamic]');
        markers.each(function (i, marker) {
            if ($(marker).data('gtdynamicform')) return;
            var dform = new GTDynamicForm(marker);
            $(marker).data('gtdynamicform', dform);
            dform.bind();
            dform.evaluate(true);
        });
    }

    function refresh(elements) {
        $(elements).each(function (i, el) {
            var $el = $(el);
            if (el.tagName === 'SELECT') {
                // Drop the stale choices, keep the blank one select2 needs.
                $el.find('option').filter(function () { return this.value !== ''; }).remove();
                $el.val(el.multiple ? [] : null);
            } else {
                $el.val('');
            }
            $el.trigger('change');
            $el.trigger('gtdynamic:refresh');
        });
    }

    document.gtdynamic = {
        functions: {},
        forms: GTDynamicForm,
        register: function (name, fn) {
            if (typeof fn !== 'function') throw new TypeError('gtdynamic.register needs a function');
            this.functions[name] = fn;
        },
        initialize: initialize,
        refresh: refresh,
        test: test
    };
    window.gt_dynamic_initialize = initialize;
})();
