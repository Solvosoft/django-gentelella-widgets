# TODO

## Widgets

- [ ] **PDF Viewer Widget** - Create a widget that displays PDF files from a FileField
  - Use PDF.js (already bundled in vendors)
  - Support for navigation (page controls)
  - Optional: zoom controls, fullscreen mode
  - Example usage: `PDFViewerWidget` for FileField displaying uploaded PDFs

## Views & Utilities

- [ ] **HTMX View Utilities** - Create utilities for views that respond to HTMX requests
  - Mixin to detect HTMX requests (`request.headers.get('HX-Request')`)
  - Return partial templates for HTMX, full page for regular requests
  - Helper for common HTMX response headers (HX-Redirect, HX-Refresh, HX-Trigger)
  - Integration with Django messages framework
  - Example: `HTMXResponseMixin`, `htmx_response()` helper function
