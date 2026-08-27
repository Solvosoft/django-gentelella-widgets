# TODO

## Widgets

- [x] **PDF Viewer Widget** - Widget that displays PDF files from a FileField
  - Uses PDF.js for client-side rendering with page navigation and zoom
  - Extends FileChunkedUpload for chunked PDF uploads with server-side validation
  - PDFFileField validates extension, content type, and magic bytes
  - Usage: `PDFViewerWidget` widget + `PDFFileField` field + chunked upload URLs

## Views & Utilities

- [ ] **HTMX View Utilities** - Create utilities for views that respond to HTMX requests
  - Mixin to detect HTMX requests (`request.headers.get('HX-Request')`)
  - Return partial templates for HTMX, full page for regular requests
  - Helper for common HTMX response headers (HX-Redirect, HX-Refresh, HX-Trigger)
  - Integration with Django messages framework
  - Example: `HTMXResponseMixin`, `htmx_response()` helper function
