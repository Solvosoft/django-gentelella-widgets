//  modal de seleccion de tarjeta - firma
window.modal = new bootstrap.Modal(document.getElementById('select_card'));

// btn en el template/samples/closed.html - firma
const signer_btn = document.getElementById('signer_btn');

// proceso de firma
const firmador = DocumentClient("select_card");

// Error al crear el socket
let socket_error = false;

// contenedor de los errores
const signature_errors = document.getElementById('signature-errors');

// evento al recargar la ventana
const refresh_modal_signature = document.getElementById('refresh_modal_signature');
refresh_modal_signature.addEventListener('click', function () {
    startSign();
});

// evento al cerrar la ventana
const close_modal_signature = document.querySelector('.close_modal_signature');

close_modal_signature.addEventListener('click', function () {
    alertFunction(gettext("If you have the PIN authentication window open, please close it before continuing."),
        gettext("Are you sure to cancel the signed?"), "warning", true,
        () => {
            firmador.cancel_sign();
            closeModalSignature();
        });
});


// interpreta los errores por codigo
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

// agregar un error en el modal
function addError(error) {
    let title = document.createElement('p');
    title.classList.add('mt-2', 'text-danger', 'mb-0');
    title.innerHTML = `<i class="fa fa-times-circle" aria-hidden="true"></i> <span class="fw-bold"> ${gettext("Errors")} </span>`;
    let errorElement = document.createElement('p');
    errorElement.classList.add('text-danger', 'mx-3', 'small');
    errorElement.innerHTML = errorInterpreter(error);
    signature_errors.appendChild(title);
    signature_errors.appendChild(errorElement);
}

// limpiar los errores
function clearErrors() {
    signature_errors.innerHTML = '';
}

// funcion para cerrar el modal
function closeModalSignature() {
    setTimeout(() => {
        window.modal.hide();
    }, 500);
}

// funcion para recargar la pagina
function reloadPage() {
    closeModalSignature();
    setTimeout(() => {
        window.location.reload();
    }, 1000);
}

// agrega evento al boton de firma y muestra el modal de seleccion de tarjeta
signer_btn.addEventListener('click', function () {
    startSign();
});


function startSign() {
    if (socket_error) {
        alertSimple(errorInterpreter(3), gettext("Error"), "error");
        return;
    }

    // limpiar los errores
    clearErrors();

    // mostrar el modal
    window.modal.show();
    // seteo de valores en los inputs hidden
    document.getElementById('id_organization').value = signer_btn.dataset.org;
    document.getElementById('id_instance').value = signer_btn.dataset.pk;

    // inicio de firma
    firmador.start_sign(signer_btn.dataset.org, signer_btn.dataset.pk);
}


function alertSimple(text, title="Error", icon = "error") {
    Swal.fire({
        icon: icon,
        title: title,
        text: text,
        confirmButtonText: gettext("Accept")
    });
}

function alertFunction(text, title="Error", icon = "error", cancelButton = false, callback = ()=>{}) {
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
