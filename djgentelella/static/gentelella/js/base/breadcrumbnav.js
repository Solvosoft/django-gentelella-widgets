/* Hierarchical path for the {% block breadcrumbs %} of base.html and
 * plain.html, which have shipped empty since the theme was ported.
 *
 * Server-rendered markup from gentelella/blocks/breadcrumb.html is optional:
 * given the same container this takes it over, so the path is already there
 * before javascript runs and stays correct after.
 *
 * Same shape as PositionsGrid and CardList: a class, delegated listeners, one
 * repaint per change.
 */

var BN_DEFAULTS = {
    levels: [],            // [{id, label, icon?, href?}]
    onNavigate: null,      // (level, index) -> void
    autoTruncate: true,    // a click drops the levels after the one clicked
    label: null,           // aria-label of the <nav>
    moreLabel: null
};

class BreadcrumbNav {

    constructor(el, options) {
        this.el = (typeof el === 'string') ? document.getElementById(el) : el;
        if (!this.el) throw new Error('BreadcrumbNav: container not found');
        this.cfg = Object.assign({}, BN_DEFAULTS, options || {});
        this.cfg.label = this.cfg.label ||
            ((typeof gettext === 'function') ? gettext('Breadcrumb') : 'Breadcrumb');
        this.cfg.moreLabel = this.cfg.moreLabel ||
            ((typeof gettext === 'function') ? gettext('Show hidden levels')
                                             : 'Show hidden levels');
        this.levels = (this.cfg.levels || []).slice();
        this.el.classList.add('gt-breadcrumb');
        this.el.setAttribute('aria-label', this.cfg.label);
        this._onClick = this._handleClick.bind(this);
        this.el.addEventListener('click', this._onClick);
        this._observe();
        this.render();
    }

    /* ------------------------------------------------------------------ *
     * public API                                                          *
     * ------------------------------------------------------------------ */

    set(levels) { this.levels = (levels || []).slice(); this.render(); return this; }
    push(level) { this.levels.push(level); this.render(); return this; }
    pop() { var level = this.levels.pop(); this.render(); return level; }

    // Keeps 0..index and returns what it dropped, so a host can undo.
    truncateTo(index) {
        var cut = this.levels.splice(index + 1);
        this.render();
        return cut;
    }

    get(index) { return this.levels[index]; }
    get length() { return this.levels.length; }

    destroy() {
        this.el.removeEventListener('click', this._onClick);
        if (this._ro) { this._ro.disconnect(); }
        else if (this._onResize) { window.removeEventListener('resize', this._onResize); }
        this.el.innerHTML = '';
        this.el.classList.remove('gt-breadcrumb', 'gt-breadcrumb-collapsed');
    }

    /* ------------------------------------------------------------------ *
     * rendering                                                           *
     * ------------------------------------------------------------------ */

    render() {
        var ol = document.createElement('ol');
        ol.className = 'breadcrumb';
        this.levels.forEach(function (level, i) {
            ol.appendChild(this._renderItem(level, i, i === this.levels.length - 1));
        }, this);
        this.el.innerHTML = '';
        this.el.appendChild(ol);
        this.ol = ol;
        this._fit();
    }

    _renderItem(level, index, last) {
        var li = document.createElement('li');
        li.className = 'breadcrumb-item' + (last ? ' active' : '');
        li.dataset.bnIndex = index;
        if (last) { li.setAttribute('aria-current', 'page'); }
        // A button, not an anchor: navigation here is a callback, and an <a>
        // with href="#" is a broken link for anyone using a screen reader or
        // middle-clicking. An anchor is used only when the level carries a
        // real href.
        var tag = last ? 'span' : (level.href ? 'a' : 'button');
        var node = document.createElement(tag);
        if (tag === 'button') { node.type = 'button'; node.className = 'btn btn-link '; }
        if (tag === 'a') { node.href = level.href; }
        node.className = (node.className || '') + 'gt-breadcrumb-label';
        node.textContent = level.label;
        node.title = level.label;
        if (level.icon) {
            var icon = document.createElement('i');
            icon.className = level.icon;
            icon.setAttribute('aria-hidden', 'true');
            node.prepend(icon, ' ');
        }
        li.appendChild(node);
        return li;
    }

    // Two states, never an iterative squeeze: expanded, or first + ellipsis +
    // last. Anything finer thrashes, because collapsing changes the width that
    // decided to collapse. What still does not fit is ellipsised in CSS.
    _fit() {
        this.el.classList.remove('gt-breadcrumb-collapsed');
        var more = this.ol.querySelector('.gt-breadcrumb-more');
        if (more) { more.remove(); }
        this.ol.querySelectorAll('.gt-breadcrumb-hidden').forEach(function (li) {
            li.classList.remove('gt-breadcrumb-hidden');
        });
        if (this.levels.length < 3) { return; }
        if (this.ol.scrollWidth <= this.ol.clientWidth) { return; }
        this.el.classList.add('gt-breadcrumb-collapsed');
        this._insertEllipsis();
    }

    _insertEllipsis() {
        var items = this.ol.querySelectorAll('.breadcrumb-item');
        var hidden = [];
        for (var i = 1; i < items.length - 1; i++) {
            items[i].classList.add('gt-breadcrumb-hidden');
            hidden.push(this.levels[i]);
        }
        if (!hidden.length) { return; }

        // bootstrap.min.js is already in the header bundle, so the dropdown
        // costs no new dependency.
        var li = document.createElement('li');
        li.className = 'breadcrumb-item dropdown gt-breadcrumb-more';
        var btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'btn btn-link gt-breadcrumb-label';
        btn.setAttribute('data-bs-toggle', 'dropdown');
        btn.setAttribute('aria-expanded', 'false');
        btn.setAttribute('aria-label', this.cfg.moreLabel);
        btn.textContent = '…';
        var menu = document.createElement('ul');
        menu.className = 'dropdown-menu';
        hidden.forEach(function (level, offset) {
            var entry = document.createElement('li');
            var action = document.createElement('button');
            action.type = 'button';
            action.className = 'dropdown-item';
            action.textContent = level.label;
            entry.dataset.bnIndex = offset + 1;
            entry.appendChild(action);
            menu.appendChild(entry);
        });
        li.appendChild(btn);
        li.appendChild(menu);
        this.ol.insertBefore(li, items[1]);
    }

    _observe() {
        if (typeof ResizeObserver !== 'undefined') {
            this._ro = new ResizeObserver(this._fit.bind(this));
            this._ro.observe(this.el);
        } else {
            this._onResize = this._fit.bind(this);
            window.addEventListener('resize', this._onResize);
        }
    }

    _handleClick(event) {
        var node = event.target.closest('[data-bn-index]');
        if (!node || !this.el.contains(node)) { return; }
        var index = parseInt(node.dataset.bnIndex, 10);
        if (index === this.levels.length - 1) { return; }   // already here
        var level = this.levels[index];
        if (!level) { return; }
        if (!level.href) { event.preventDefault(); }
        if (this.cfg.autoTruncate && !level.href) { this.truncateTo(index); }
        this.el.dispatchEvent(new CustomEvent('bn:navigate', {
            detail: {nav: this, level: level, index: index}, bubbles: true}));
        if (typeof this.cfg.onNavigate === 'function') {
            this.cfg.onNavigate(level, index);
        }
    }
}

window.BreadcrumbNav = BreadcrumbNav;
