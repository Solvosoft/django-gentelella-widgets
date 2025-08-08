document.addEventListener("DOMContentLoaded", function () {
    function updatePreview(inputId, previewId) {
                    const input = document.getElementById(inputId);
                    const img = document.getElementById(previewId);
                    if (input && img) {
                        input.addEventListener("change", function () {
                            const file = input.files[0];
                            if (file && file.type.startsWith("image/")) {
                                            const reader = new FileReader();
                                            reader.onload = e => img.src = e.target.result;
                                            reader.readAsDataURL(file);
                            }
                        });
                    }
    }

    updatePreview("id_image", "image-preview");
});

// auto remove messages
document.addEventListener("DOMContentLoaded", function () {
    setTimeout(function () {
        document.querySelectorAll(".alert-success").forEach(function (message) {
            message.style.transition = "opacity 0.5s";
            message.style.opacity = "0";
            setTimeout(() => message.remove(), 500);
        });
    }, 1500);
});
