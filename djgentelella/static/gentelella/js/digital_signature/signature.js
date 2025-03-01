// function responseManageTypeData(instance, err_json_fn, error_text_fn) {
//     return function (response) {
//         const contentType = response.headers.get("content-type");
//         if (response.ok) {
//             if (contentType && contentType.indexOf("application/json") !== -1) {
//                 return response.json();
//             } else {
//                 return response.text();
//             }
//         } else {
//             if (contentType && contentType.indexOf("application/json") !== -1) {
//                 response.json().then(data => err_json_fn(data));
//             } else {
//                 if (response.status === 406) {
//                     // cierre de ventana para ingresar el PIN
//                     error_text_fn(errorInterpreter(4));
//                 } else {
//                     response.text().then(data => error_text_fn(data));
//                 }
//             }
//         }
//         return Promise.reject(response);
//     }
// }
//
// function SocketManager(socket) {
//     // Si ocurre algún error durante la conexión
//     socket.onerror = (event) => {
//         // console.error("WebSocket error");
//         // Aquí puedes invocar tu lógica de error, por ejemplo:
//         alertSimple(errorInterpreter(3), gettext("Error"), "error");
//         socket_error = true;
//     };
//
//     // Si la conexión se cierra
//     socket.onclose = (event) => {
//         // console.warn("WebSocket cerrado");
//     };
//
//     // Si la conexión se abre
//     socket.onopen = (event) => {
//         // console.log("WebSocket conectado");
//         socket_error = false;
//     };
// }
//
// function callFetch(instance, signal) {
//     fetch(instance.url, {
//         method: instance.type,
//         body: instance.data,
//         headers: {
//             'X-CSRFToken': getCookie('csrftoken'),
//             'Content-Type': 'application/json'
//         },
//         cache: 'no-cache', // no usar cache
//         signal: signal,
//     }).then(responseManageTypeData(instance, instance.error_json, instance.error_text))
//         .then(data => instance.success(data))
//         .catch(error => {
//             if (error.name === 'AbortError') {
//                 console.log("Aborted");
//                 return;
//             }
//             instance.error(error);
//         });
// }
//
// function FirmadorLibreLocal(docmanager, abortSignal) {
//     return {
//         "cert_url": "http://localhost:3516/certificates",
//         "sign_url": "http://localhost:3516/sign",
//         "success_get_certificates": function (data) {
//             docmanager.success_certificates(data);
//         },
//         "get_certificates": function () {
//             let parent = this;
//
//             const instance = {
//                 url: this.cert_url,
//                 type: 'GET',
//                 data: null,
//                 success: function (data) {
//                     parent.success_get_certificates(data);
//                 },
//                 error_text: function (message) {
//                     // console.log(message);
//                 },
//                 error_json: function (error) {
//                     // console.log(error);
//                 },
//                 error: function (error) {
//                     // No reconoce el firmador libre
//                     if (String(error) === "TypeError: NetworkError when attempting to fetch resource.") {
//                         addError(1);
//                     }
//                 }
//             }
//             callFetch(instance, abortSignal);
//         },
//         "sign": function (data) {
//             let json = JSON.stringify(data);
//             let manager = docmanager;
//             const fetch_instance = {
//                 'url': this.sign_url,
//                 'type': 'POST',
//                 'data': json,
//                 "success": function (data) {
//                     // si el resultado es diferente a un string, es posible que hay un error
//                     // console.log(data)
//                     if (typeof data !== 'string') { //prevent option call
//                         // console.log("manager.local_done(data)", data);
//                         manager.local_done(data);
//                     }
//
//                 },
//                 "error": function (error) {
//                     // console.log(error);
//                     if (typeof error === "object") {
//                         // cierre de ventana para ingresar el PIN
//                         if (error.status === 406 && error.statusText === "Not Acceptable") {
//                             alertSimple(errorInterpreter(4), gettext("Warning"), "warning");
//                         }
//                     }
//                 },
//                 "error_text": function (message) {
//                     console.error("error_text", message);
//
//                 },
//                 "error_json": function (error) {
//                     console.error("error_json", error);
//                 },
//             };
//
//             callFetch(fetch_instance, abortSignal);
//         }
//     }
// }
//
// function FirmadorLibreWS(docmanager, url) {
//     var firmador = {
//         "url": url,
//         "websocket": null,
//         "firmador_url": "http://localhost:3516",
//         "trans_received": function (instance) {
//             return function (event) {
//
//                 try {
//                     const data = JSON.parse(event.data);
//                     instance.receive_json(data);
//                 } catch (err) {
//                     console.error("Error al parsear mensaje WS:", err);
//                 }
//
//             }
//         },
//         "receive_json": function (data) {
//             // console.log(data);
//             // validar errores del socket
//             if (data.result === false && data.error) {
//
//                  if (typeof data.details === "string") {
//                     // problemas de conexion con la API del firmador libre
//                     if (data.details.includes("Connection refused")) {
//                         addError(3);
//                     }
//                 } else if (data.code) {
//                     switch (data.code) {
//                         case 0:
//                             // cuando ocurre un error desconocido en el servidor
//                             alertSimple(errorInterpreter(0), gettext("Error"), "error");
//                             break;
//                         case 6:
//                             // cuando ocurre un solapamiento de la firma
//                             alertSimple(errorInterpreter(6), gettext("Error"), "error");
//                             break;
//                         case 7:
//                             // cuanda la firma se encuentra fuera de los limites de la pagina
//                             alertSimple(errorInterpreter(7), gettext("Error"), "error");
//                             break;
//                         case 8:
//                             // cuando ocurre un error debido a una libreria incompatible
//                             alertSimple(errorInterpreter(8), gettext("Error"), "error");
//                             break;
//                         case 9:
//                             // cuando ocurre un error debido a un proveedor de criptografía
//                             alertSimple(errorInterpreter(9), gettext("Error"), "error");
//                             break;
//                         case 10:
//                             // cuando ocurre un error debido a un algoritmo de firma
//                             alertSimple(errorInterpreter(10), gettext("Error"), "error");
//                             break;
//                         case 11:
//                         // cuando hay errores al serializar datos
//                             alertSimple(errorInterpreter(11), gettext("Error"), "error");
//                         break;
//                         case 12:
//                         // cuando ocurre un error debido a un servicio de firma
//                             alertSimple(errorInterpreter(12), gettext("Error"), "error");
//                             break;
//                         default:
//                             // cuando ocurre un error desconocido
//                             alertSimple(errorInterpreter(999), gettext("Error"), "error");
//                             break;
//                     }
//                 }
//             }
//
//             docmanager.do_sign_local(data);
//
//         },
//         "inicialize": function () {
//             this.websocket = new WebSocket(url);
//
//             //Manejo de WebSocket
//             SocketManager(this.websocket);
//
//             this.websocket.onmessage = this.trans_received(this);
//         },
//         "local_done": function (data) {
//             // console.log("local_done", data);
//         },
//         "sign": function (data) {
//             data["action"] = "initial_signature";
//             // console.log("sign", data);
//             if(data.card !== undefined){
//                 this.websocket.send(JSON.stringify(data));
//             }else{
//                 // Error cuando no hay tarjeta conectada, pero intenta firmar
//                 alertSimple(errorInterpreter(2), gettext("Error"), "error");
//                 addError(2);
//             }
//
//         },
//         "complete_sign": function (data) {
//             data["action"] = "complete_signature";
//             // console.log("complete_sign", data);
//             try {
//                 this.websocket.send(JSON.stringify(data));
//             } catch (e) {
//                 // console.error("Error de comunicación WS");
//                 alertFunction(errorInterpreter(3), gettext("Error"), "error", false, closeModalSignature);
//             }
//         },
//         "cancel_sign": function () {
//             // Enviar el mensaje "cancel_signature" por WS
//             let data = {action: "cancel_signature"};
//             this.websocket.send(JSON.stringify(data));
//         }
//     };
//     firmador.inicialize();
//     return firmador;
// }
//
// function DocumentClient(modal_id) {
//     const abortController = new AbortController();
//     const docmanager = {
//         "modal_id": modal_id,
//         "remotesigner": null,
//         "localsigner": null,
//         "certificates": null,
//         "org": null,
//         "pk": null,
//         "cancel_sign": function () {
//             // console.log("Cancelando proceso de firma...");
//             clearErrors();
//             this.remotesigner.cancel_sign();
//         },
//         "display_start_modal": function () {
//             let parent = this;
//             let btn = document.getElementById(`${this.modal_id}_sign_btn`);
//             // Agregar el evento si no lo haya agregado
//             if (!btn.dataset.listenerBound) {
//                 btn.addEventListener("click", () => {
//                     clearErrors();
//                     parent.do_sign_remote();
//                 });
//                 btn.dataset.listenerBound = "true";
//             }
//
//         },
//         "start_sign": function (org, pk) {
//             // cuando se abre el modal
//             // console.log("Iniciando firma");
//             this.org = org;
//             this.pk = pk;
//             this.localsigner.get_certificates();
//             this.display_start_modal();
//         },
//         "success_certificates": function (data) {
//             let id_card = document.getElementById('id_card');
//             id_card.innerHTML = "";
//             this.certificates = {};
//             let parent = this;
//
//             // agregar los tarjetas a la lista de opciones
//             data.forEach((element) => {
//                 parent.certificates[element.tokenSerialNumber] = element;
//                 let start_token = element.tokenSerialNumber.substring(0, 4);
//                 let newOption = new Option(`${start_token} ${element.commonName}`, element.tokenSerialNumber, true, true);
//                 id_card.appendChild(newOption);
//                 let eventoCambio = new Event('change');
//                 id_card.dispatchEvent(eventoCambio);
//             });
//
//             if (data.length === 0) {
//                 // no hay tarjeta conectada
//                 addError(2);
//             }
//         },
//         "do_sign_remote": function () {
//             let selected_card = document.querySelector(`#${this.modal_id} form select`).value;
//             const containerSelector = "#signature";
//             if(selected_card && this.certificates) {
//                 let data = {
//                     'organization': this.org,
//                     'instance': this.pk,
//                     'card': this.certificates[selected_card],
//                     // "docsettings": document.get_document_settings()
//                     "docsettings": document.get_document_settings(".pdf-signature-container[data-id='123']")
//                 }
//                 this.remotesigner.sign(data);
//             }else if( !selected_card && !this.certificates){
//                 alertSimple(errorInterpreter(1), gettext("Error"), "error");
//                 addError(1);
//             } else if(!selected_card && this.certificates){
//                 alertSimple(errorInterpreter(2), gettext("Error"), "error");
//                 addError(2);
//             }
//
//         },
//         "do_sign_local": function (data) {
//             // console.log(data);
//             this.localsigner.sign(data);
//             // firmado exitosamente
//             if (data.result === true) {
//                 alertFunction(
//                     gettext("The signing was successfully completed."),
//                     gettext("Success"),
//                     "success", false, reloadPage
//                 );
//             }
//         },
//         "local_done": function (data) {
//             data['organization'] = this.org;
//             data['instance'] = this.pk;
//             this.remotesigner.complete_sign(data);
//             // console.log("local_done", data);
//         },
//         "remote_done": function (data) {
//             // console.log('remote_done', data);
//             if (data.result === true) {
//                 document.location.reload();
//             }
//         },
//         "cancel_sign": function () {
//             // console.log("Cancelar firmado (sin cerrar WebSocket).");
//             this.remotesigner.cancel_sign();
//         }
//     }
//
//     const firmadorRemoto = FirmadorLibreWS(docmanager, urls['sign_ws']);
//     const firmadorLocal = FirmadorLibreLocal(docmanager, abortController.signal);
//
//     docmanager["remotesigner"] = firmadorRemoto
//     docmanager["localsigner"] = firmadorLocal
//     return docmanager;
// }
