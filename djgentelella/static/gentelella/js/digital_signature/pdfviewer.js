document.addEventListener("DOMContentLoaded", function () {
    // Buscar todos los contenedores de componentes
    const containers = document.querySelectorAll(".pdf-signature-container");
    // Creamos un array global para almacenar las instancias
    window.pdfSignatureComponents = [];
    containers.forEach(container => {
        const instance = new PdfSignatureComponent(container);
        window.pdfSignatureComponents.push(instance);
    });
    document.get_document_settings = function (containerSelector) {
        const instance = window.pdfSignatureComponents.find(inst =>
            inst.container.matches(containerSelector)
        );
        return instance ? instance.getDocumentSettings() : null;
    };
});

class PdfSignatureComponent {
    constructor(container) {
        this.container = container;

        // Elementos internos (usando selectores relativos)
        this.signature = container.querySelector('.signature');
        this.canvas = container.querySelector('.pdfviewer');
        this.btn_prev = container.querySelector('.prev');
        this.btn_next = container.querySelector('.next');
        this.page_num = container.querySelector('.page_num');
        this.page_number = container.querySelector('.page_number');
        this.page_count = container.querySelector('.page_count');
        this.sub_canvas_container = container.querySelector('.sub_canvas_container');

        // Verifica que existan todos los elementos requeridos
        if (!this.signature || !this.canvas || !this.btn_prev || !this.btn_next || !this.page_num || !this.page_number || !this.page_count || !this.sub_canvas_container) {
            console.warn("Falta alguno de los elementos requeridos en este componente. Se omite su inicialización.");
            return;
        }

        // Variables propias del componente
        this.pdfDoc = null;
        this.pageNum = 1;
        this.pageRendering = false;
        this.pageNumPending = null;
        this.scale = 1.2;
        this.signX = 0;
        this.signY = 198;
        this.signWidth = 133;
        this.signHeight = 133;

        // Inicializa cada parte
        this.initEvents();
        this.initPDFViewer();
        this.initInteract();
        this.initSignatureSettings();
    }

    initEvents() {
        this.btn_prev.addEventListener('click', () => this.onPrevPage());
        this.btn_next.addEventListener('click', () => this.onNextPage());
        this.page_number.addEventListener('change', (e) => this.renderPage(e.target.value));
        this.page_number.addEventListener('keyup', (e) => this.renderPage(e.target.value));
    }

    initPDFViewer() {
        if (typeof urls['sign_doc'] === 'undefined') {
            console.warn("La variable 'pdf_document' no está definida.");
            return;
        }
        pdfjsLib.getDocument(urls['sign_doc'] ).promise.then((pdfDoc_) => {
            this.pdfDoc = pdfDoc_;
            this.page_count.textContent = pdfDoc_.numPages;
            this.renderPage(this.pageNum);
        });
    }

    onPrevPage() {
        if (this.pageNum <= 1) return;
        this.pageNum--;
        this.queueRenderPage(this.pageNum);
    }

    onNextPage() {
        if (this.pageNum >= this.pdfDoc.numPages) return;
        this.pageNum++;
        this.queueRenderPage(this.pageNum);
    }

    queueRenderPage(num) {
        if (this.pageRendering) {
            this.pageNumPending = num;
        } else {
            this.renderPage(num);
        }
    }

    renderPage(num) {
        this.pageRendering = true;
        this.pdfDoc.getPage(num).then((page) => {
            const viewport = page.getViewport({scale: this.scale});
            this.canvas.height = viewport.height;
            this.canvas.width = viewport.width;

            const renderContext = {
                canvasContext: this.canvas.getContext('2d'), viewport: viewport
            };
            const renderTask = page.render(renderContext);

            renderTask.promise.then(() => {
                this.pageRendering = false;
                if (this.pageNumPending !== null) {
                    this.renderPage(this.pageNumPending);
                    this.pageNumPending = null;
                }
            });
        });
        this.page_num.textContent = num;
        this.page_number.value = num;
    }

    initInteract() {
        // Primera instancia de draggable y resizable con interact.js
        interact(this.signature)
            .draggable({
                inertia: true, modifiers: [interact.modifiers.restrictRect({
                    restriction: this.canvas, endOnly: false
                })], autoScroll: true, listeners: {
                    move: (event) => this.dragMoveListener(event)
                }
            })
            .resizable({
                edges: {left: true, right: true, bottom: true, top: true}, listeners: {
                    move: (event) => {
                        let target = event.target;
                        let x = (parseFloat(target.getAttribute('data-x')) || 0);
                        let y = (parseFloat(target.getAttribute('data-y')) || 0);

                        target.style.width = event.rect.width + 'px';
                        target.style.height = event.rect.height + 'px';

                        x += event.deltaRect.left;
                        y += event.deltaRect.top;

                        target.style.transform = `translate(${x}px, ${y}px)`;
                        target.setAttribute('data-x', x);
                        target.setAttribute('data-y', y);
                        target.textContent = Math.round(event.rect.width) + '\u00D7' + Math.round(event.rect.height);

                        this.signWidth = event.rect.width;
                        this.signHeight = event.rect.height;
                        this.signX = x;
                        this.signY = y;
                    }
                }, modifiers: [interact.modifiers.restrictEdges({outer: 'parent'}), interact.modifiers.restrictSize({
                    min: {
                        width: 100, height: 50
                    }
                })], inertia: true
            });

        // Segunda instancia de draggable con autoScroll sobre el contenedor
        interact(this.signature)
            .draggable({
                inertia: true, modifiers: [interact.modifiers.restrictRect({
                    restriction: this.canvas, endOnly: false
                })], autoScroll: {
                    container: this.sub_canvas_container, margin: 50, distance: 5, interval: 50
                }, listeners: {
                    move: (event) => this.dragMoveListener(event)
                }
            });
    }

    dragMoveListener(event) {
        const target = event.target;
        const x = (parseFloat(target.getAttribute('data-x')) || 0) + event.dx;
        const y = (parseFloat(target.getAttribute('data-y')) || 0) + event.dy;
        this.updatePosition(target, x, y);
    }

    updatePosition(target, x, y) {
        target.style.transform = `translate(${x}px, ${y}px)`;
        const {x: xAdjusted, y: yAdjusted} = this.adjustPositionToFitWithinCanvas(target, x, y);
        target.style.transform = `translate(${xAdjusted}px, ${yAdjusted}px)`;
        target.setAttribute('data-x', xAdjusted);
        target.setAttribute('data-y', yAdjusted);
        this.signX = Math.round(xAdjusted);
        this.signY = Math.round(yAdjusted);
    }

    adjustPositionToFitWithinCanvas(target, x, y) {
        const canvasRect = this.canvas.getBoundingClientRect();
        const targetRect = target.getBoundingClientRect();
        if (targetRect.right > canvasRect.right) {
            x -= targetRect.right - canvasRect.right;
        }
        if (targetRect.bottom > canvasRect.bottom) {
            y -= targetRect.bottom - canvasRect.bottom;
        }
        return {x, y};
    }

    initSignatureSettings() {
        // Se aplica una configuración base clonando el elemento de firma
        const tempSignature = this.signature.cloneNode(true);
        tempSignature.style = '';
        tempSignature.classList.remove("right", "left", "top", "bottom", "full", "none");
        tempSignature.style.visibility = 'visible';
        tempSignature.style.width = 'auto';
        tempSignature.style.height = 'auto';
        tempSignature.style.overflow = 'visible';
        const textElem = tempSignature.querySelector('.text');
        if (textElem) textElem.style.wordBreak = 'break-word';

        this.formatAndLoadContent(tempSignature)
            .then(() => {
                this.signature.className = tempSignature.className;
                this.signature.style.cssText = tempSignature.style.cssText;
                this.signature.innerHTML = tempSignature.innerHTML;
                this.updatePosition(this.signature, 198, 0);
            })
            .catch(error => {
                console.error(gettext("Error when applying setting to signature: "), error);
            });
    }

    async formatAndLoadContent(element, content) {
        const imageContainer = element.querySelector('.image');
        const textContainer = element.querySelector('.text');
        if (imageContainer) imageContainer.innerHTML = '';
        if (textContainer) textContainer.innerHTML = '';
        try {
            // Aquí podrías cargar la imagen o actualizar el texto de la firma
            // Por ejemplo:
            // await this.loadSignatureImage(signatureImageURL, imageContainer);
        } catch (error) {
            console.error(gettext("Error loading content: "), error);
        }
    }

    async createTemporarySignature(content) {
        let tempSignature = window.app.signature.cloneNode(true);
        tempSignature.id = 'temp_signature';
        tempSignature.style.position = 'absolute';
        tempSignature.style.visibility = 'hidden';
        let textElem = tempSignature.querySelector('.text');
        if (textElem) textElem.style.wordBreak = 'break-word';
        this.sub_canvas_container.appendChild(tempSignature);
        await this.formatAndLoadContent(tempSignature, content);
        return tempSignature;
    }

    // Si se requiere, se puede definir un método para cargar una imagen
    loadSignatureImage(signatureImage, imageContainer) {
        return new Promise((resolve, reject) => {
            if (!signatureImage) {
                resolve();
                return;
            }
            const img = new Image();
            img.src = signatureImage;
            img.alt = 'signature-image';
            img.onload = () => {
                if (imageContainer) imageContainer.appendChild(img);
                resolve();
            };
            img.onerror = () => {
                reject(new Error(gettext("Error loading image")));
            };
        });
    }

    getDocumentSettings() {
        return {
            pageNumber: this.pageNum,
            signWidth: this.signWidth,
            signHeight: this.signHeight,
            signX: this.signX,
            signY: this.signY
        };
    }
}
