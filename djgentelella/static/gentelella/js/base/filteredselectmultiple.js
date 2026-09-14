/**
  FilteredSelectMultiple: the two panel layout django admin draws for
  filter_horizontal, on top of two native <select multiple>. The right hand one
  is the real form field, so what is inside it at submit time is what posts --
  moving an option is literally moving the DOM node, and there is no submit
  hook to forget.

  Widgets are registered by the id of the real select. A re-render (formset
  clone, reopened modal, api_list.js) runs gt_find_initialize over the same ids
  on brand new nodes, so the previous widget has to be torn down first or its
  handlers keep firing against detached elements.
*/
var _gt_filtered_select_widgets = {};

function gt_fsm_option_group(option){
    var group = option.parentNode;
    if (group && group.tagName === 'OPTGROUP') return group.getAttribute('label');
    return null;
}

function gt_fsm_group_target(list, label){
    /** Where an option has to land in `list` so its optgroup survives. */
    if (!label) return list;
    var group = null;
    $(list).children('optgroup').each(function(i, g){
        if (g.getAttribute('label') === label) group = g;
    });
    if (group === null){
        group = document.createElement('optgroup');
        group.setAttribute('label', label);
        list.appendChild(group);
    }
    return group;
}

function gt_fsm_drop_empty_groups(list){
    $(list).children('optgroup').each(function(i, g){
        if (g.children.length === 0) g.remove();
    });
}

function getFilteredSelectMultipleWidget(element){
    var id = element.id;
    var previous = _gt_filtered_select_widgets[id];
    if (previous){
        previous.destroy();
        delete _gt_filtered_select_widgets[id];
    }

    var chosen = $(element);
    var container = document.getElementById(id + '_container');
    if (!container) return null;

    var widget = {
        id: id,
        chosen: chosen,
        chosenEl: element,
        container: $(container),
        available: $('#' + $.escapeSelector(id) + '_available'),
        filter: $('#' + $.escapeSelector(id) + '_filter'),
        url: chosen.data('url'),
        page: 1,
        more: false,
        loading: false,
        term: '',
        requestToken: 0,
        xhr: null,
        debounce: null,

        init: function(){
            if (this.url){
                this.reload();
            } else {
                this.split_static_options();
            }
            this.bind();
            this.refresh();
        },

        /** No endpoint: the template rendered every option inside the real
            select, so the unselected ones belong on the available side. */
        split_static_options: function(){
            var self = this;
            var availableEl = this.available[0];
            $(this.chosenEl).find('option').each(function(i, option){
                if (option.selected) return;
                var label = gt_fsm_option_group(option);
                gt_fsm_group_target(availableEl, label).appendChild(option);
            });
            gt_fsm_drop_empty_groups(this.chosenEl);
            self.apply_filter();
        },

        chosen_values: function(){
            var values = [];
            $(this.chosenEl).find('option').each(function(i, option){
                if (option.value !== '') values.push(option.value);
            });
            return values;
        },

        /** Endpoint mode: throw the available panel away and ask for page 1
            with the current search term. */
        reload: function(){
            this.page = 1;
            this.more = false;
            this.available.empty();
            this.load_page();
        },

        load_page: function(){
            if (!this.url || this.loading) return;
            var self = this;
            this.loading = true;
            this.requestToken += 1;
            var token = this.requestToken;
            var data = {
                page: this.page,
                selected: this.chosen_values().join(',')
            };
            if (this.term) data.term = this.term;
            this.xhr = $.ajax({url: this.url, type: 'GET', dataType: 'json', data: data})
                .done(function(payload){
                    // A slower answer to an older term must not overwrite the
                    // list the user is looking at now.
                    if (token !== self.requestToken) return;
                    self.append_results(payload);
                })
                .fail(function(jqxhr, status){
                    if (status === 'abort') return;
                    console.error('FilteredSelectMultiple: ' + self.url + ' failed', status);
                })
                .always(function(){
                    if (token === self.requestToken) self.loading = false;
                    self.refresh();
                });
        },

        append_results: function(payload){
            var self = this;
            var results = (payload && payload.results) || [];
            var already = this.chosen_values();
            var availableEl = this.available[0];
            $.each(results, function(i, item){
                var value = String(item.id);
                // The endpoint flags what the widget already holds instead of
                // dropping it (unless the view sets exclude_selected), and a
                // page can also repeat across reloads.
                if (already.indexOf(value) !== -1) return;
                if (self.available.find('option[value="' + $.escapeSelector(value) + '"]').length) return;
                var option = new Option(item.text, value, false, false);
                if (item.disabled) option.disabled = true;
                availableEl.appendChild(option);
            });
            this.more = !!(payload && payload.pagination && payload.pagination.more);
            this.apply_filter();
        },

        /** Client side filtering, the only kind the static mode needs. With an
            endpoint the term goes to the server instead. */
        apply_filter: function(){
            if (this.url) return;
            var term = (this.filter.val() || '').toLowerCase();
            this.available.find('option').each(function(i, option){
                option.hidden = term !== '' &&
                    option.textContent.toLowerCase().indexOf(term) === -1;
            });
            gt_fsm_drop_empty_groups(this.available[0]);
        },

        move: function(options, target){
            var targetEl = target[0];
            var toChosen = targetEl === this.chosenEl;
            $.each(options, function(i, option){
                if (option.disabled) return;
                var label = gt_fsm_option_group(option);
                option.selected = toChosen;
                gt_fsm_group_target(targetEl, label).appendChild(option);
            });
            gt_fsm_drop_empty_groups(this.chosenEl);
            gt_fsm_drop_empty_groups(this.available[0]);
            // Anything listening on the field (a related chain, a formset) has
            // to see the field change, and select2 style widgets only react to
            // an explicit trigger.
            this.chosen.trigger('change');
            this.apply_filter();
            this.refresh();
        },

        picked: function(list){
            return $(list).find('option:checked').filter(function(i, option){
                return !option.hidden && !option.disabled;
            });
        },

        movable: function(list){
            return $(list).find('option').filter(function(i, option){
                return !option.hidden && !option.disabled;
            });
        },

        refresh: function(){
            var availableCount = this.available.find('option').not('[hidden]').length;
            var chosenCount = $(this.chosenEl).find('option').length;
            $('#' + $.escapeSelector(this.id) + '_available_count').text(availableCount);
            $('#' + $.escapeSelector(this.id) + '_chosen_count').text(chosenCount);
            this.container.find('.gt-fsm-add, .gt-fsm-addall')
                .prop('disabled', availableCount === 0);
            this.container.find('.gt-fsm-remove, .gt-fsm-removeall')
                .prop('disabled', chosenCount === 0);
        },

        bind: function(){
            var self = this;
            // Namespaced so destroy() unbinds ours without touching a handler
            // some other widget put on the same node.
            this.container.on('click.gtfsm', '.gt-fsm-add', function(){
                self.move(self.picked(self.available), self.chosen);
            });
            this.container.on('click.gtfsm', '.gt-fsm-remove', function(){
                self.move(self.picked(self.chosenEl), self.available);
            });
            this.container.on('click.gtfsm', '.gt-fsm-addall', function(){
                self.move(self.movable(self.available), self.chosen);
            });
            this.container.on('click.gtfsm', '.gt-fsm-removeall', function(){
                self.move(self.movable(self.chosenEl), self.available);
            });
            this.available.on('dblclick.gtfsm', function(){
                self.move(self.picked(self.available), self.chosen);
            });
            this.chosen.on('dblclick.gtfsm', function(){
                self.move(self.picked(self.chosenEl), self.available);
            });
            this.filter.on('input.gtfsm', function(){
                var term = $(this).val() || '';
                if (self.url){
                    clearTimeout(self.debounce);
                    self.debounce = setTimeout(function(){
                        self.term = term;
                        if (self.xhr) self.xhr.abort();
                        self.loading = false;
                        self.reload();
                    }, 300);
                } else {
                    self.apply_filter();
                    self.refresh();
                }
            });
            // Enter in the filter box must not submit the surrounding form.
            this.filter.on('keydown.gtfsm', function(event){
                if (event.which === 13) event.preventDefault();
            });
            this.available.on('scroll.gtfsm', function(){
                if (!self.url || !self.more || self.loading) return;
                var el = this;
                if (el.scrollTop + el.clientHeight >= el.scrollHeight - 20){
                    self.page += 1;
                    self.load_page();
                }
            });
            this.container.on('click.gtfsm', '.gt-fsm-create', function(){
                self.open_create_modal($(this).data('addurl'));
            });
        },

        /** Optional `add_url`: a view answering GET with {result: "<form html>"}
            and POST with {result: {id, text}}. The modal id is derived from the
            field id, so several widgets on one page never share one. */
        open_create_modal: function(url){
            if (!url) return;
            var self = this;
            var modal = $('#' + $.escapeSelector(this.id) + '_modal');
            if (modal.length === 0) return;
            $.ajax({url: url, type: 'GET', dataType: 'json'})
                .done(function(payload){
                    modal.html(payload.result);
                    if (typeof gt_find_initialize === 'function') gt_find_initialize(modal);
                    modal.off('click.gtfsmsave').on('click.gtfsmsave', '.save_data_btn', function(){
                        self.send_create_form(url, modal);
                    });
                    new bootstrap.Modal(modal[0]).show();
                })
                .fail(function(){
                    console.error('FilteredSelectMultiple: cannot load ' + url);
                });
        },

        send_create_form: function(url, modal){
            var self = this;
            var form = modal.find('form')[0];
            if (!form) return;
            var payload = Object.fromEntries(new FormData(form).entries());
            $.ajax({
                url: url,
                type: 'POST',
                dataType: 'json',
                contentType: 'application/json',
                headers: {'X-CSRFToken': getCookie('csrftoken')},
                data: JSON.stringify(payload)
            }).done(function(answer){
                if (!answer || !answer.result) return;
                var option = new Option(answer.result.text, String(answer.result.id), false, false);
                self.available[0].appendChild(option);
                bootstrap.Modal.getInstance(modal[0]).hide();
                self.apply_filter();
                self.refresh();
            }).fail(function(){
                console.error('FilteredSelectMultiple: cannot post to ' + url);
            });
        },

        destroy: function(){
            clearTimeout(this.debounce);
            this.requestToken += 1;
            if (this.xhr) this.xhr.abort();
            this.container.off('.gtfsm');
            this.available.off('.gtfsm');
            this.chosen.off('.gtfsm');
            this.filter.off('.gtfsm');
            $('#' + $.escapeSelector(this.id) + '_modal').off('.gtfsmsave');
        }
    };

    widget.init();
    _gt_filtered_select_widgets[id] = widget;
    return widget;
}

function build_filtered_select_multiple(instances){
    instances.each(function(index, element){
        getFilteredSelectMultipleWidget(element);
    });
}
