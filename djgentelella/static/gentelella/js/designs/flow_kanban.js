/* flow_kanban (djgentelella.designs): the objects of a flow as cards in
 * columns, one per state.
 *
 * Moving a card -- dragging it (HTML5 drag and drop) or with its "Move to"
 * menu -- never changes a state here: the server is asked which transitions
 * take the object from its column to the other one, for this user, now.
 * None: the card goes back and the reason is shown. One: it runs (through
 * its form in a modal when it has one). Several: the user picks one. Any
 * refusal -- permission, condition, invalid form, somebody else moved it
 * first -- puts the card back in its column with the message.
 *
 * The configuration comes from the server as JSON (data-gtconfig); the cards
 * come as HTML rendered (and escaped) by the server.
 */
(function () {
    'use strict';

    function readJSON(id) {
        var element = document.getElementById(id);
        return element ? JSON.parse(element.textContent) : null;
    }

    function csrfToken(root) {
        var input = root.querySelector('input[name="csrfmiddlewaretoken"]');
        if (input) { return input.value; }
        var match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
        return match ? decodeURIComponent(match[1]) : '';
    }

    function format(text, values) {
        return text.replace(/%\((\w+)\)s/g, function (all, key) {
            return values[key] === undefined ? all : values[key];
        });
    }

    function fragment(html) {
        var template = document.createElement('template');
        template.innerHTML = html;
        return template.content;
    }

    function Board(root) {
        this.root = root;
        this.config = readJSON(root.getAttribute('data-gtconfig'));
        this.base = this.config.urls.base;
        this.message = root.querySelector('.gtkanban-message');
        this.modalElement = root.querySelector('.gtkanban-modal');
        this.dragged = null;
        this.bind();
    }

    Board.prototype.column = function (state) {
        return this.root.querySelector('.gtkanban-column[data-state="' + CSS.escape(state) + '"]');
    };

    Board.prototype.columns = function () {
        return Array.prototype.slice.call(this.root.querySelectorAll('.gtkanban-column'));
    };

    Board.prototype.request = function (method, url, body) {
        var options = {method: method, credentials: 'same-origin',
                       headers: {'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json'}};
        if (method !== 'GET') {
            options.headers['X-CSRFToken'] = csrfToken(this.root);
            options.body = body;
        }
        return fetch(url, options).then(function (response) {
            return response.json().catch(function () { return {}; }).then(function (data) {
                return {status: response.status, data: data};
            });
        });
    };

    Board.prototype.say = function (text, kind) {
        this.message.innerHTML = '';
        if (!text) { return; }
        var alert = document.createElement('div');
        alert.className = 'alert alert-' + (kind || 'info') + ' alert-dismissible';
        alert.setAttribute('role', kind === 'danger' ? 'alert' : 'status');
        alert.textContent = text;
        var close = document.createElement('button');
        close.type = 'button';
        close.className = 'btn-close';
        close.setAttribute('data-bs-dismiss', 'alert');
        alert.appendChild(close);
        this.message.appendChild(alert);
    };

    Board.prototype.count = function (state, delta) {
        var column = this.column(state);
        if (!column) { return; }
        var total = column.querySelector('.gtkanban-total');
        var value = parseInt(total.textContent, 10) + delta;
        total.textContent = value;
        if (this.config.limit) {
            column.classList.toggle('gtkanban-over', value > this.config.limit);
        }
    };

    /* -- marking the columns while dragging ---------------------------------- */
    Board.prototype.mark = function (state) {
        var allowed = this.config.moves[state] || [];
        this.columns().forEach(function (column) {
            var target = column.getAttribute('data-state');
            if (target === state) { return; }
            var ok = allowed.indexOf(target) !== -1;
            column.classList.add(ok ? 'gtkanban-allowed' : 'gtkanban-forbidden');
            column.setAttribute('data-gtkanban-allowed', ok ? '1' : '0');
        });
    };

    Board.prototype.unmark = function () {
        this.columns().forEach(function (column) {
            column.classList.remove('gtkanban-allowed', 'gtkanban-forbidden', 'gtkanban-drop');
            column.removeAttribute('data-gtkanban-allowed');
        });
    };

    /* -- moving --------------------------------------------------------------- */
    /* Put the card in the target column while the server decides, and
     * remember where it was, to put it back on a refusal. */
    Board.prototype.attempt = function (cardElement, target) {
        var self = this;
        var source = cardElement.getAttribute('data-state');
        if (source === target || cardElement.classList.contains('gtkanban-pending')) { return; }
        var move = {card: cardElement, source: source, target: target,
                    pk: cardElement.getAttribute('data-pk'),
                    parent: cardElement.parentNode, next: cardElement.nextSibling};
        var targetColumn = this.column(target);
        targetColumn.querySelector('.gtkanban-cards').prepend(cardElement);
        cardElement.classList.add('gtkanban-pending');
        this.say('');
        var url = this.base + encodeURIComponent(move.pk) + '/transitions/?target=' + encodeURIComponent(target);
        this.request('GET', url).then(function (result) {
            var data = result.data;
            if (result.status !== 200) {
                return self.revert(move, data.detail || self.config.messages.error);
            }
            if (!data.transitions.length) {
                return self.revert(move, data.detail || self.config.messages.error);
            }
            if (data.transitions.length === 1) {
                return self.proceed(move, data.transitions[0]);
            }
            self.choose(move, data.transitions);
        }).catch(function () { self.revert(move, self.config.messages.error); });
    };

    Board.prototype.revert = function (move, reason) {
        move.card.classList.remove('gtkanban-pending');
        if (move.next && move.next.parentNode === move.parent) {
            move.parent.insertBefore(move.card, move.next);
        } else {
            move.parent.appendChild(move.card);
        }
        this.say(reason, 'danger');
        move.card.focus();
    };

    Board.prototype.proceed = function (move, transition) {
        if (transition.form) {
            return this.openForm(move, transition);
        }
        var body = new FormData();
        body.append('transition', transition.name);
        this.post(move, body);
    };

    Board.prototype.post = function (move, body, onInvalid) {
        var self = this;
        var url = this.base + encodeURIComponent(move.pk) + '/move/';
        return this.request('POST', url, body).then(function (result) {
            if (result.status === 200) {
                self.done(move, result.data);
                return true;
            }
            if (result.status === 400 && onInvalid) {
                onInvalid(result.data);
                return false;
            }
            self.revert(move, result.data.detail || self.config.messages.error);
            return true;
        }).catch(function () {
            self.revert(move, self.config.messages.error);
            return true;
        });
    };

    /* The flow ran: the card goes where the object is now -- not always the
     * column it was dropped on, automatic transitions may take it further --
     * or leaves the board. */
    Board.prototype.done = function (move, data) {
        this.count(move.source, -1);
        var messages = this.config.messages;
        if (data.card && this.column(data.state)) {
            var cards = this.column(data.state).querySelector('.gtkanban-cards');
            var fresh = fragment(data.card).firstElementChild;
            move.card.remove();
            cards.prepend(fresh);
            this.count(data.state, 1);
            fresh.focus();
        } else {
            move.card.remove();
        }
        if (data.error) {
            this.say(format(messages.stopped, {error: data.error}), 'warning');
        } else {
            this.say(format(messages.moved, {state: data.state_label}), 'success');
        }
    };

    /* -- the modal: which transition, and a transition's form ------------------ */
    Board.prototype.modal = function (title, content, onClose) {
        var self = this;
        this.modalElement.querySelector('.modal-title').textContent = title;
        var body = this.modalElement.querySelector('.modal-body');
        body.innerHTML = '';
        body.appendChild(content);
        var modal = bootstrap.Modal.getOrCreateInstance(this.modalElement);
        this.closing = onClose;
        if (!this.modalBound) {
            this.modalBound = true;
            this.modalElement.addEventListener('hidden.bs.modal', function () {
                var callback = self.closing;
                self.closing = null;
                if (callback) { callback(); }
            });
        }
        modal.show();
        return modal;
    };

    /* Close the modal; ``then`` runs once it is hidden (another modal can
     * only open after that). */
    Board.prototype.closeModal = function (then) {
        this.closing = then || null;
        bootstrap.Modal.getOrCreateInstance(this.modalElement).hide();
    };

    Board.prototype.choose = function (move, transitions) {
        var self = this;
        var list = document.createElement('div');
        list.className = 'd-grid gap-2 gtkanban-choices';
        transitions.forEach(function (transition) {
            var button = document.createElement('button');
            button.type = 'button';
            button.className = 'btn ' + (transition.css_class || 'btn-primary');
            button.setAttribute('data-transition', transition.name);
            button.textContent = transition.label;
            button.addEventListener('click', function () {
                self.closeModal(function () { self.proceed(move, transition); });
            });
            list.appendChild(button);
        });
        this.modal(this.config.messages.choose, list, function () {
            self.revert(move, '');
        });
    };

    Board.prototype.openForm = function (move, transition) {
        var self = this;
        var url = this.base + encodeURIComponent(move.pk) + '/form/?transition=' + encodeURIComponent(transition.name);
        this.request('GET', url).then(function (result) {
            if (result.status !== 200) {
                return self.revert(move, result.data.detail || self.config.messages.error);
            }
            var container = document.createElement('div');
            self.modal(result.data.title, container, function () { self.revert(move, ''); });
            self.fillForm(move, container, result.data.html);
        }).catch(function () { self.revert(move, self.config.messages.error); });
    };

    Board.prototype.fillForm = function (move, container, html) {
        var self = this;
        container.innerHTML = '';
        container.appendChild(fragment(html));
        if (typeof gt_find_initialize === 'function' && window.jQuery) {
            gt_find_initialize(window.jQuery(container));
        }
        var form = container.querySelector('form');
        form.addEventListener('submit', function (event) {
            event.preventDefault();
            var submit = form.querySelector('[type="submit"]');
            submit.disabled = true;
            // The modal is closed only once the server answered: an invalid
            // form stays open with its errors, anything else ends the move.
            self.post(move, new FormData(form), function (data) {
                self.fillForm(move, container, data.html);
            }).then(function (finished) {
                if (finished) { self.closeModal(); }
            });
        });
    };

    /* -- "load more" ------------------------------------------------------------ */
    Board.prototype.more = function (column) {
        var self = this;
        var state = column.getAttribute('data-state');
        var cards = column.querySelector('.gtkanban-cards');
        var button = column.querySelector('.gtkanban-more');
        var offset = cards.querySelectorAll('.gtkanban-card').length;
        button.disabled = true;
        this.request('GET', this.base + 'cards/?state=' + encodeURIComponent(state) + '&offset=' + offset)
            .then(function (result) {
                button.disabled = false;
                if (result.status !== 200) { return; }
                var known = {};
                cards.querySelectorAll('.gtkanban-card').forEach(function (element) {
                    known[element.getAttribute('data-pk')] = true;
                });
                Array.prototype.slice.call(fragment(result.data.html).children).forEach(function (element) {
                    if (!known[element.getAttribute('data-pk')]) { cards.appendChild(element); }
                });
                button.hidden = !result.data.has_more;
            });
    };

    /* -- events ----------------------------------------------------------------- */
    Board.prototype.bind = function () {
        var self = this;
        var root = this.root;
        root.addEventListener('dragstart', function (event) {
            var cardElement = event.target.closest && event.target.closest('.gtkanban-card');
            if (!cardElement || !cardElement.draggable) { return; }
            self.dragged = cardElement;
            cardElement.classList.add('gtkanban-dragging');
            event.dataTransfer.effectAllowed = 'move';
            event.dataTransfer.setData('text/plain', cardElement.getAttribute('data-pk'));
            self.mark(cardElement.getAttribute('data-state'));
        });
        root.addEventListener('dragend', function () {
            if (self.dragged) { self.dragged.classList.remove('gtkanban-dragging'); }
            self.dragged = null;
            self.unmark();
        });
        root.addEventListener('dragover', function (event) {
            var column = event.target.closest && event.target.closest('.gtkanban-column');
            if (!self.dragged || !column) { return; }
            event.preventDefault();
            event.dataTransfer.dropEffect = 'move';
            self.columns().forEach(function (item) { item.classList.toggle('gtkanban-drop', item === column); });
        });
        root.addEventListener('drop', function (event) {
            var column = event.target.closest && event.target.closest('.gtkanban-column');
            var cardElement = self.dragged;
            if (!cardElement || !column) { return; }
            event.preventDefault();
            cardElement.classList.remove('gtkanban-dragging');
            self.dragged = null;
            self.unmark();
            self.attempt(cardElement, column.getAttribute('data-state'));
        });
        root.addEventListener('click', function (event) {
            var item = event.target.closest('.gtkanban-move-to');
            if (item) {
                self.attempt(item.closest('.gtkanban-card'), item.getAttribute('data-target'));
                return;
            }
            var more = event.target.closest('.gtkanban-more');
            if (more) { self.more(more.closest('.gtkanban-column')); }
        });
    };

    function start() {
        document.querySelectorAll('.gtdesign-kanban[data-gtconfig]').forEach(function (root) {
            if (!root.gtkanban) { root.gtkanban = new Board(root); }
        });
    }

    window.GTFlowKanban = {start: start, Board: Board};
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', start);
    } else {
        start();
    }
}());
