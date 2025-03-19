///////////////////////////////////////////////
//  Init widgets digital signature
///////////////////////////////////////////////
build_digital_signature = function (instance) {

    const widgetId = instance.getAttribute("id");
    const url_ws = instance.getAttribute("data-ws-url");
    const container = instance.closest(".widget-digital-signature");
    const container_tag = `container-${widgetId}`;
    container.setAttribute("data-widget-id", container_tag);

    // pdfviewer
    const defaultPage = instance.getAttribute("data-default-page") || "first";
    // Crear una nueva instancia del visor de PDF con la configuración adecuada
    const pdfInstance = new PdfSignatureComponent(container, defaultPage);

    if (!doc_instance) {
        console.error("You must define the doc_instance variable.");
        return;
    }

    // Signature
    let signatureManager = new SignatureManager(container, url_ws);
    signatureManager.startSign(doc_instance, urls['logo']);

    // Store the instance in a global object with key per widget ID
    if (!window.pdfSignatureComponents) {
        window.pdfSignatureComponents = {};
    }

    // Agregar la instancia al objeto global si no existe
    if (!window.pdfSignatureComponents[container_tag]) {
        window.pdfSignatureComponents[container_tag] = pdfInstance;
    }

}

///////////////////////////////////////////////
//  PDF preview Digtal Signature
///////////////////////////////////////////////
class PdfSignatureComponent {
    constructor(container, defaultPage) {
        this.container = container;
        this.defaultPage = defaultPage;
        this.widgetId = container.getAttribute("data-widget-id");


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
            console.warn("The variable 'sign_doc' is not defined.");
            return;
        }
        pdfjsLib.getDocument(urls['sign_doc']).promise.then((pdfDoc_) => {
            this.pdfDoc = pdfDoc_;
            this.page_count.textContent = pdfDoc_.numPages;

            // define page number
            if (this.defaultPage === "last") {
                this.pageNum = this.pdfDoc.numPages;
            } else if (this.defaultPage === "first") {
                this.pageNum = 1;
            } else {
                let numPage = parseInt(this.defaultPage, 10);
                if (!isNaN(numPage) && numPage > 0 && numPage <= this.pdfDoc.numPages) {
                    this.pageNum = numPage;
                } else {
                    console.warn("Invalid page number, starting on the first page.");
                    this.pageNum = 1;
                }
            }


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

///////////////////////////////////////////////
//  Signature manager Digital Signature
///////////////////////////////////////////////
class SignatureManager {
    constructor(container, url_ws) {
        this.container = container;
        this.modal = new bootstrap.Modal(container.querySelector("#loading_sign"));
        this.firmador = new DocumentClient(container, container.getAttribute("data-widget-id"), this, url_ws, this.doc_instance);
        this.signerBtn = container.querySelector(".btn_signer");
        this.errorsContainer = container.querySelector(".errors_signer");
        this.refreshBtn = container.querySelector(".btn_signer_refresh");
        this.socketError = false;

        this.initEvents();
    }

    initEvents() {
        if (this.signerBtn) {
            this.signerBtn.addEventListener('click', () => this.sign());
        }
        if (this.refreshBtn) {
            this.refreshBtn.addEventListener('click', () => this.refresh());
        }
    }

    startSign(doc_instance, logo_url = null) {
        if (this.socketError) {
            alertSimple(errorInterpreter(3), gettext("Error"), "error");
            return;
        }

        this.doc_instance = doc_instance;
        this.logo_url = logo_url;

        this.clearErrors();

        this.firmador.start_sign(doc_instance, logo_url)
    }

    refresh() {
        this.socketError = false;
        // this.firmador.inicialize();
        this.firmador.remotesigner.inicialize();

        this.clearErrors();
        this.firmador.start_sign(this.doc_instance, this.logo_url);
    }

    sign() {
        this.firmador.do_sign_remote();
    }

    addError(errorCode) {
        let title = document.createElement('p');
        title.classList.add('mt-2', 'text-danger', 'mb-0');
        title.innerHTML = `<i class="fa fa-times-circle" aria-hidden="true"></i> <span class="fw-bold"> ${gettext("Errors")} </span>`;
        let errorElement = document.createElement('p');
        errorElement.classList.add('text-danger', 'mx-3', 'small');
        errorElement.innerHTML = errorInterpreter(errorCode);
        this.errorsContainer.appendChild(title);
        this.errorsContainer.appendChild(errorElement);
    }

    clearErrors() {
        this.errorsContainer.innerHTML = '';
    }

    reloadPage() {
        window.location.reload();
    }

    showLoading() {
        this.modal.show();
    }

    hideLoading() {
        setTimeout(() => {
            this.modal.hide();
        }, 500);
    }
}

///////////////////////////////////////////////
//   Socket Digital Signature
///////////////////////////////////////////////
function responseManageTypeData(instance, err_json_fn, error_text_fn) {
    return function (response) {
        const contentType = response.headers.get("content-type");
        if (response.ok) {
            if (contentType && contentType.indexOf("application/json") !== -1) {
                return response.json();
            } else {
                return response.text();
            }
        } else {
            if (contentType && contentType.indexOf("application/json") !== -1) {
                response.json().then(data => err_json_fn(data));
            } else {
                if (response.status === 406) {
                    // cierre de ventana para ingresar el PIN
                    error_text_fn(errorInterpreter(4));
                } else {
                    response.text().then(data => error_text_fn(data));
                }
            }
        }
        return Promise.reject(response);
    }
}

function SocketManager(socket, signatureManager) {
    // Si ocurre algún error durante la conexión
    socket.onerror = (event) => {
        // console.error("WebSocket error");
        signatureManager.hideLoading();
        alertSimple(errorInterpreter(3), gettext("Error"), "error");
        signatureManager.socketError = true;
    };

    // Si la conexión se cierra
    socket.onclose = (event) => {
        // console.warn("WebSocket cerrado");
    };

    // Si la conexión se abre
    socket.onopen = (event) => {
        // console.log("WebSocket conectado");
        signatureManager.socket_error = false;
    };
}

function callFetch(instance) {
    fetch(instance.url, {
        method: instance.type,
        body: instance.data,
        headers: {
            'X-CSRFToken': getCookie('csrftoken'),
            'Content-Type': 'application/json'
        },
        cache: 'no-cache', // no usar cache
    }).then(responseManageTypeData(instance, instance.error_json, instance.error_text))
        .then(data => instance.success(data))
        .catch(error => {
            instance.error(error);
        });
}

function FirmadorLibreLocal(docmanager, signatureManager) {
    return {
        "cert_url": "http://localhost:3516/certificates",
        "sign_url": "http://localhost:3516/sign",
        "success_get_certificates": function (data) {
            docmanager.success_certificates(data);
        },
        "get_certificates": function () {
            let parent = this;

            const instance = {
                url: this.cert_url,
                type: 'GET',
                data: null,
                success: function (data) {
                    parent.success_get_certificates(data);
                },
                error_text: function (message) {
                    // console.log(message);
                },
                error_json: function (error) {
                    // console.log(error);
                },
                error: function (error) {
                    // No reconoce el firmador libre
                    if (String(error) === "TypeError: NetworkError when attempting to fetch resource.") {
                        signatureManager.addError(1);
                    }
                }
            }
            callFetch(instance);
        },
        "sign": function (data) {
            let json = JSON.stringify(data);
            let manager = docmanager;

            const fetch_instance = {
                'url': this.sign_url,
                'type': 'POST',
                'data': json,
                "success": function (data) {
                    // si el resultado es diferente a un string, es posible que hay un error
                    // console.log(data)
                    if (typeof data !== 'string') { //prevent option call
                        // console.log("manager.local_done(data)", data);
                        manager.local_done(data);
                    }
                    // signatureManager.hideLoading();
                },
                "error": function (error) {
                    // console.log(error);
                    signatureManager.hideLoading();
                    if (typeof error === "object") {
                        // cierre de ventana para ingresar el PIN
                        if (error.status === 406 && error.statusText === "Not Acceptable") {
                            alertSimple(errorInterpreter(4), gettext("Warning"), "warning");
                        }
                    }
                },
                "error_text": function (message) {
                    console.error("error_text", message);
                    signatureManager.hideLoading();
                },
                "error_json": function (error) {
                    console.error("error_json", error);
                    signatureManager.hideLoading();
                },
            };

            callFetch(fetch_instance);
        }
    }
}

function FirmadorLibreWS(docmanager, url, signatureManager) {
    var firmador = {
        "url": url,
        "websocket": null,
        "firmador_url": "http://localhost:3516",
        "trans_received": function (instance) {
            return function (event) {
                try {
                    const data = JSON.parse(event.data);
                    instance.receive_json(data);
                } catch (err) {
                    console.error("Error al parsear mensaje WS:", err);
                }
            };
        },
        "receive_json": function (data) {
            // console.log(data);
            // validar errores del socket
            if (data.result === false && data.error) {
                signatureManager.hideLoading();
                if (typeof data.details === "string") {
                    // problemas de conexion con la API del firmador libre
                    if (data.details.includes("Connection refused")) {
                        signatureManager.addError(3);
                    }
                } else if (data.code) {
                    switch (data.code) {
                        case 0:
                            // cuando ocurre un error desconocido en el servidor
                            alertSimple(errorInterpreter(0), gettext("Error"), "error");
                            break;
                        case 6:
                            // cuando ocurre un solapamiento de la firma
                            alertSimple(errorInterpreter(6), gettext("Error"), "error");
                            break;
                        case 7:
                            // cuanda la firma se encuentra fuera de los limites de la pagina
                            alertSimple(errorInterpreter(7), gettext("Error"), "error");
                            break;
                        case 8:
                            // cuando ocurre un error debido a una libreria incompatible
                            alertSimple(errorInterpreter(8), gettext("Error"), "error");
                            break;
                        case 9:
                            // cuando ocurre un error debido a un proveedor de criptografía
                            alertSimple(errorInterpreter(9), gettext("Error"), "error");
                            break;
                        case 10:
                            // cuando ocurre un error debido a un algoritmo de firma
                            alertSimple(errorInterpreter(10), gettext("Error"), "error");
                            break;
                        case 11:
                            // cuando hay errores al serializar datos
                            alertSimple(errorInterpreter(11), gettext("Error"), "error");
                            break;
                        case 12:
                            // cuando ocurre un error debido a un servicio de firma
                            alertSimple(errorInterpreter(12), gettext("Error"), "error");
                            break;
                        default:
                            // cuando ocurre un error desconocido
                            alertSimple(errorInterpreter(999), gettext("Error"), "error");
                            break;
                    }
                }
            }

            docmanager.do_sign_local(data);
        },
        "inicialize": function () {
            this.websocket = new WebSocket(url);
            SocketManager(this.websocket, signatureManager);
            this.websocket.onmessage = this.trans_received(this);
        },
        "local_done": function (data) {
            // console.log("local_done", data);
        },
        "sign": function (data) {
            data["action"] = "initial_signature";
            if (data.card !== undefined) {
                this.websocket.send(JSON.stringify(data));
                signatureManager.showLoading();
            } else {
                alertSimple(errorInterpreter(2), gettext("Error"), "error");
                signatureManager.addError(2);
            }
        },
        "complete_sign": function (data) {
            data["action"] = "complete_signature";

            try {
                this.websocket.send(JSON.stringify(data));
            } catch (e) {
                // console.error("Error de comunicación WS");
               signatureManager.hideLoading();
                alertFunction(errorInterpreter(3), gettext("Error"), "error", false, closeModalSignature);
            }
        },
    };
    firmador.inicialize();
    return firmador;
}

function DocumentClient(container, widgetId, signatureManager, url_ws) {
    const docmanager = {
        "widgetId": widgetId,
        "container": container,
        "signatureManager": signatureManager,
        "remotesigner": null,
        "localsigner": null,
        "certificates": null,
        "doc_instance": null,
        "logo_url": null,

        "start_sign": function (doc_instance, logo_url = null) {
            this.doc_instance = doc_instance;
            this.logo_url = logo_url;
            this.localsigner.get_certificates();
            this.signatureManager.clearErrors();
        },
        "success_certificates": function (data) {

            if (data.length > 0) {
                container.querySelector("#container_select_card").classList.remove("d-none");
                container.querySelector("#container_select_card_tem").classList.add("d-none");

                let id_card = container.querySelector("#select_card_id_update-file");

                if (!id_card) {
                    console.error(`No se encontró el select para el widget ${widgetId}`);
                    return;
                }
                id_card.innerHTML = "";
                this.certificates = {};

                data.forEach((element) => {
                    this.certificates[element.tokenSerialNumber] = element;
                    let start_token = element.tokenSerialNumber.substring(0, 4);
                    let newOption = new Option(
                        `${start_token} ${element.commonName}`,
                        element.tokenSerialNumber,
                        false, false
                    );
                    id_card.appendChild(newOption);
                });
            } else {
                container.querySelector("#container_select_card").classList.add("d-none");
                container.querySelector("#container_select_card_tem").classList.remove("d-none");
                this.signatureManager.addError(2);
            }
        },

        "do_sign_remote": function () {
            let select = container.querySelector("#select_card_id_update-file");
            let selected_card = select ? select.value : null;

            if (selected_card && this.certificates) {
                let data = {
                    'logo_url': this.logo_url,
                    'instance': this.doc_instance,
                    'card': this.certificates[selected_card],
                    "docsettings": window.pdfSignatureComponents[widgetId].getDocumentSettings()
                };
                this.remotesigner.sign(data);
            } else if (!selected_card && !this.certificates) {
                signatureManager.hideLoading();
                alertSimple(errorInterpreter(1), gettext("Error"), "error");
                this.signatureManager.addError(1);
            } else if (!selected_card && this.certificates) {
              signatureManager.hideLoading();
                alertSimple(errorInterpreter(2), gettext("Error"), "error");
                this.signatureManager.addError(2);
            }

        },
        "do_sign_local": function (data) {
            // console.log(data);
            this.localsigner.sign(data);
            // firmado exitosamente
            if (data.result === true) {
                alertFunction(
                    gettext("The signing was successfully completed."),
                    gettext("Success"),
                    "success", false, this.signatureManager.reloadPage
                );
            }
           // signatureManager.hideLoading();
        },
        "local_done": function (data) {
            data['instance'] = this.doc_instance;
            data['logo_url'] = this.logo_url;
            this.remotesigner.complete_sign(data);
        },
        "remote_done": function (data) {
            // console.log('remote_done', data);
            if (data.result === true) {
                document.location.reload();
            }
        },

    };

    docmanager["remotesigner"] = new FirmadorLibreWS(docmanager, url_ws, signatureManager);
    docmanager["localsigner"] = new FirmadorLibreLocal(docmanager, signatureManager);

    return docmanager;
}

///////////////////////////////////////////////
//  Manage Errors Digital Signature
///////////////////////////////////////////////
function errorInterpreter(error) {

    let textError = "";

    switch (error) {
        case 0:
            // cuando ocurre un error no controlado en el servidor de firma
            textError = gettext("An error has occurred in the internal server of the uncontrolled 'Firmador Libre'.");
            break;
        case 1:
            // cuando no abre la aplicación firmador libre
            textError = gettext("Make sure to start the 'Firmador Libre' application. If it is already running, please press the reload button.");
            break;
        case 2:
            // cuando no hay tarjeta conectada
            textError = gettext("There is no card connected to the device. Please press the reload button and connect your card.");
            break;
        case 3:
            // cuando el servicio de firma no funciona
            textError = gettext("The internal signature service does not work. Please contact the support.");
            break;
        case 4:
            // cuando cierra el modal y deja la ventana abierta del PIN (Firmador Libre)
            textError = gettext("Authentication failed because the PIN entry window was detected closed, please try again.");
            break;
        case 5:
            // cuando desconecta la tarjeta
            //! Este error debe solucionarse en el Firmador Libre
            textError = gettext("The device was disconnected, possibly the window was closed for signature. Please close the window for the authentication PIN.");
            break;
        case 6:
            // cuando ocurre un solapamiento de la firma
            textError = gettext("The new signature field position overlaps with an existing signature.");
            break;
        case 7:
            // cuanda la firma se encuentra fuera de los limites de la pagina
            textError = gettext("The new signature field position is outside the page dimensions.");
            break;
        case 8:
            // cuando ocurre un error debido a una libreria incompatible
            textError = gettext("The version of one or more libraries is incompatible.");
            break;
        case 9:
            // cuando ocurre un error debido a un proveedor de criptografía
            textError = gettext("The cryptographic provider is not available.");
            break;
        case 10:
            // cuando ocurre un error debido a un algoritmo de firma
            textError = gettext("The signing algorithm is not available.");
            break;
        case 11:
            // cuando hay errores al serializar datos
            textError = gettext("Errors have been encountered in the data to be sent to the 'Free Signer'. Please press the reload button and try again.");
            break;
        case 12:
            // cuando ocurre un error debido a un servicio de firma por tiempo de espera
            textError = gettext("The request to the signing service timed out. Please, press the reload button and try again.");
            break;
        default:
            // cuando ocurre un error desconocido
            textError = gettext("We're sorry, an unexpected error occurred. Please, press the reload button and try again.");
    }

    return textError;

}

///////////////////////////////////////////////
//  Alerts Digital Signature
///////////////////////////////////////////////
function alertSimple(text, title = "Error", icon = "error") {
    Swal.fire({
        icon: icon,
        title: title,
        text: text,
        confirmButtonText: gettext("Accept")
    });
}

function alertFunction(text, title = "Error", icon = "error", cancelButton = false,
                       callback = () => {
                       }) {
    Swal.fire({
        icon: icon,
        title: title,
        text: text,
        confirmButtonText: gettext("Accept"),
        showCancelButton: cancelButton,
        cancelButtonText: gettext("Cancel"),
        confirmButtonColor: '#3085d6',
        cancelButtonColor: '#d33',
    }).then((result) => {
        if (result.isConfirmed) {
            callback();
        }
    });
}

///////////////////////////////////////////////
//  End widgets digital signature
///////////////////////////////////////////////


////////////////////////////////////////////////////////////////
// copy action
////////////////////////////////////////////////////////////////
document.addEventListener("DOMContentLoaded", function () {
    document.getElementById("copy-command-line").addEventListener("click", function () {
        let commandText = document.getElementById("command-line").innerText.trim();

        navigator.clipboard.writeText(commandText)
            .then(() => {
                let text = document.getElementById("text-copy")
                text.classList.remove("d-none")
                setTimeout(() => {
                    text.classList.add("d-none")
                }, 1500)
            })
            .catch(err => {
                console.error("Error al copiar el texto: ", err);
            });
    });

    document.getElementById("show-command-line").addEventListener("click", () => {
        let container = document.getElementById("container-command-line")

        if (container.classList.contains("d-none")) {
            container.classList.remove("d-none");
        } else {
            container.classList.add("d-none");
        }
    })
});
