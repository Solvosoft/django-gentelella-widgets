/* Registers the djgentelella service worker (djgentelella.pwa,
 * GT_PWA_SERVICE_WORKER). window.gt_pwa_registration is the promise of the
 * registration, null when the browser has no service workers. */
(function () {
    'use strict';
    var script = document.currentScript;
    window.gt_pwa_registration = null;
    if (!script || !('serviceWorker' in navigator)) { return; }
    window.gt_pwa_registration = navigator.serviceWorker.register(
        script.dataset.sw, {scope: script.dataset.scope || '/'}
    ).catch(function (error) {
        if (window.console) { console.warn('Service worker not registered', error); }
        return null;
    });
})();
