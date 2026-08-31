/* Friconix rescans.
 *
 * Friconix converts <i class="fi-..."> elements into inline SVG. It hooks
 * `document.onreadystatechange` and scans the document exactly once, with no
 * MutationObserver -- so every icon that appears afterwards stays an empty <i>:
 * a formset row, a reopened modal, a DataTables redraw, a select2 dropdown,
 * anything loaded over HTMX. gt_find_initialize() in widgets.js is where this
 * project re-initialises a subtree, and the rescan rides along with it.
 *
 * friconix_update() overwrites icon.innerHTML, so running it again is
 * idempotent. It always scans the whole document -- that is the only entry
 * point friconix exposes -- so there is nothing to scope to the subtree.
 */
function gt_friconix_refresh() {
    if (typeof friconix_update === 'function') {
        friconix_update();
    }
}

/* friconix sets document.onreadystatechange by plain assignment rather than
 * addEventListener, so any other library doing the same wins and its only scan
 * never happens. One extra idempotent pass on load makes that harmless. */
$(window).on('load', gt_friconix_refresh);

window.gt_friconix_refresh = gt_friconix_refresh;
