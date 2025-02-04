
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
