/* Configures the PDF.js viewer for MFR and opens the document.
 *
 * The template passes the file URL and the asset base as data attributes on <body>. PDF.js
 * dispatches "webviewerloaded" right before it initialises, which is the point where its options
 * can still be changed; the document is then opened explicitly once the viewer is initialised,
 * because the viewer's own start-up only accepts files from its own origin.
 */
;(function () {
    'use strict';

    var body = document.body;
    var fileUrl = body.getAttribute('data-mfr-url');
    var assets = body.getAttribute('data-mfr-assets');
    var configured = false;

    function configure() {
        if (configured) {
            return;
        }
        configured = true;

        var options = window.PDFViewerApplicationOptions;
        var app = window.PDFViewerApplication;

        // do not open anything at start-up; the document is opened below with credentials
        options.set('defaultUrl', '');
        // the options below are final: do not let preferences stored in the browser override them
        options.set('disablePreferences', true);
        // resources are served from the extension's asset path, not relative to this page
        options.set('workerSrc', assets + '/build/pdf.worker.mjs');
        options.set('rendererSrc', assets + '/build/pdf.renderer.mjs');
        options.set('cMapUrl', assets + '/web/cmaps/');
        options.set('standardFontDataUrl', assets + '/web/standard_fonts/');
        options.set('wasmUrl', assets + '/web/wasm/');
        options.set('iccUrl', assets + '/web/iccs/');
        options.set('imageResourcesPath', assets + '/web/images/');
        options.set('enableScripting', false);
        // links open in a new tab
        options.set('externalLinkTarget', 2);
        // the preview is read-only: no annotation editing tools in the toolbar
        options.set('annotationEditorMode', -1);
        // no model downloads for alternative-text suggestions
        options.set('enableGuessAltText', false);
        options.set('enableAltTextModelDownload', false);

        app.initializedPromise.then(function () {
            return app.open({url: fileUrl, withCredentials: true});
        });
    }

    // PDF.js dispatches the event on the parent document when it can reach it, otherwise on its
    // own document; listen on both.
    document.addEventListener('webviewerloaded', configure);
    try {
        if (window.parent !== window) {
            window.parent.document.addEventListener('webviewerloaded', configure);
        }
    } catch (e) {
        // cross-origin parent: the event will arrive on this document
    }

    window.pymChild.sendMessage('embed', 'embed-responsive-pdf');
})();
