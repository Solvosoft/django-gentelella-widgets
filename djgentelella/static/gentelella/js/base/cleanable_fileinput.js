build_cleanable_fileinput = function (instance) {
    document.addEventListener("DOMContentLoaded", function () {
        const container = instance.closest(".widget-cleanable-fileinput");
        const btnClear = container.querySelector("#btn-{{ widget.id }}");

        if (!btnClear) {
            return;
        }

        const filename = container.querySelector("#filename-{{ widget.id }}");
        const hiddenInput = container.querySelector("#input-{{ widget.id }}");
        btnClear.addEventListener("click", function (e) {

            if (hiddenInput) {
                if (hiddenInput.value === "false" || hiddenInput.value === "") {
                    hiddenInput.value = "true";
                    if (filename) {
                        filename.classList.add("file-deleted");
                    }
                } else {
                    hiddenInput.value = "false";
                    if (filename) {
                        filename.classList.remove("file-deleted");
                    }
                }
            }
        });

    });

}

