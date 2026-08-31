function convertFileToBase64(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();

        reader.onload = () => {
            const base64String = reader.result.split(',')[1];
            resolve(base64String);
        };

        reader.onerror = (error) => {
            reject(error);
        };

        reader.readAsDataURL(file);
    });
}

/* Push every editor's content back into the textarea it replaced.
 *
 * TinyMCE edits inside an iframe and only writes back to its <textarea> when
 * the form is submitted, through a hook it installs on the form itself. A form
 * that is read by javascript instead of submitted -- which is every modal and
 * every inline form here -- never fires that, so the textarea still holds
 * whatever it had when the editor booted: usually nothing. The field then
 * arrives empty and the server answers "this field cannot be blank" over a box
 * with visible text in it.
 */
function flush_editors(form) {
    if (typeof tinymce === 'undefined') {
        return;
    }
    form.querySelectorAll('textarea[id]').forEach(function (textarea) {
        var editor = tinymce.get(textarea.id);
        if (editor) {
            editor.save();
        }
    });
}

/* Put `value` into the editor that took over `textarea`, if there is one.
 *
 * The write path used to name two widgets, EditorTinymce and TextareaWysiwyg,
 * so any other editor widget -- VoiceEditorTinymce, or one a project subclasses
 * -- had its value written into a textarea nobody can see, and the form opened
 * looking empty over data that was there. Asking TinyMCE whether it manages the
 * element covers every variant, including ones that do not exist yet.
 */
function set_editor_content(inputfield, value) {
    if (typeof tinymce === 'undefined') {
        return false;
    }
    var editor = tinymce.get(inputfield.attr('id'));
    if (!editor) {
        return false;
    }
    editor.setContent(value === null || value === undefined ? '' : value);
    return true;
}


async function obtainFormAsJSON(form, prefix = '', extras = {}, format = true) {
    flush_editors(form);
    const fields = form.elements;
    const formData = {};
    // typeof variable === 'function'
    for (let key in extras) {
        if (typeof extras[key] === 'function') {
            formData[key] = extras[key](form, key, prefix);
        } else {
            formData[key] = extras[key];
        }
    }

    for (let i = 0; i < fields.length; i++) {
        const field = fields[i];

        if (field.type !== 'submit' && field.type !== 'button') {
            const fieldName = field.name.replace(prefix, '');
            if (field.type === 'textarea') {
                formData[fieldName] = $(field).val();
            } else if (field.type === 'checkbox') {
                formData[fieldName] = field.checked;
            } else if (field.type === 'radio') {
                if (field.checked) {
                    formData[fieldName] = $(field).val();
                }
            } else if (field.type === 'file') {
                const files = Array.from(field.files);
                const filesBase64 = [];

                for (let j = 0; j < files.length; j++) {
                    const file = files[j];
                    try {
                        const base64String = await convertFileToBase64(file);
                        filesBase64.push({name: file.name, value: base64String});
                    } catch (error) {
                        console.error('Error converting file:', error);
                    }
                }

                formData[fieldName] = filesBase64;
            } else if (field.multiple) {
                const selectedOptions = Array.from(field.selectedOptions);
                const selectedValues = selectedOptions.map((option) => option.value);
                formData[fieldName] = selectedValues;
            } else {
                formData[fieldName] = field.value;
            }
        }
    }

    if (format) {
        return JSON.stringify(formData);
    }

    return formData;
}

function convertToStringJson(form, prefix = "", extras = {}, format = true) {
    return obtainFormAsJSON(form[0], prefix, extras, format);
}

function load_errors(error_list, obj, parentdiv) {
    ul_obj = "<ul class='errorlist form_errors d-flex justify-content-center'>";
    error_list.forEach((item) => {
        ul_obj += "<li>" + item + "</li>";
    });
    ul_obj += "</ul>"
    $(obj).parents(parentdiv).prepend(ul_obj);
    return ul_obj;
}

function form_field_errors(target_form, form_errors, prefix, parentdiv) {
    var item = "";
    for (const [key, value] of Object.entries(form_errors)) {
        item = " #id_" + prefix + key;
        if (target_form.find(item).length > 0) {
            load_errors(form_errors[key], item, parentdiv);
        }
    }
}

function response_manage_type_data(instance, err_json_fn, error_text_fn) {
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
                response.json().then(data => err_json_fn(instance, data));
            } else {
                response.text().then(data => error_text_fn(instance, data));
            }
            return Promise.resolve(false);
        }

        return Promise.reject(response);  // then it will go to the catch if it is an error code
    }
}

function clear_action_form(form) {
    // Switches used to need unwinding by hand here: switchery painted a
    // <span> next to the input and a native form reset left that span behind.
    // The switch is the input now, so reset repaints it on its own.
    $(form).find('[data-widget="TaggingInput"],[data-widget="EmailTaggingInput"]').each(function (i, e) {
        var tg = $(e).data().tagify;
        if(tg != undefined){
           tg.removeAllTags();
        }

    });
    $(form).find('[data-widget="FileChunkedUpload"],[data-widget="FileInput"]').each(function (i, e) {
        var tg = $(e).data().fileUploadWidget;
        tg.resetEmpty();
    });
    $(form).trigger('reset');
    $(form).find("select option:selected").prop("selected", false);
    $(form).find("select").val(null).trigger('change');
    $(form).find("ul.form_errors").remove();
    $(form).find(".file-link").remove();
}

var gt_form_modals = {}
var gt_detail_modals = {}
var gt_crud_objs = {};

function updateInstanceValuesForm(form, name, value) {
    var item = form.find(
        'input[name="' + name + '"], ' +
        'textarea[name="' + name + '"], ' +
        'select[name="' + name + '"]'
    );
    item.each(function (i, inputfield) {
        let done = false;
        inputfield = $(inputfield);

        if (inputfield.attr('class') === "chunkedvalue") {
            if (value) {
                var chunked = form.find('input[name="' + name + '_widget"]').data('fileUploadWidget');
                chunked.addRemote(value);
            }
            done = true;
        } else if (inputfield.attr('type') === 'file') {
            if (value) {
                var newlink = document.createElement('a');
                newlink.href = value.url;
                newlink.textContent = value.name;
                newlink.target = "_blank";
                newlink.classList.add("link-primary");
                newlink.classList.add("file-link");
                newlink.classList.add("d-block");
                inputfield.before(newlink)
            }
            done = true;
        } else if (inputfield.attr('type') === "checkbox") {
            if (inputfield.data().widget === "YesNoInput") {
                inputfield.prop("checked", !value);
                inputfield.trigger("click");
                done = true;
            } else {
                inputfield.prop("checked", value);
            }
            done = true;
        } else if (inputfield.attr('type') === "radio") {
            var sel = inputfield.filter(function () {
                return this.value === value.toString()
            });
            if (sel.length > 0) {
                sel.prop("checked", true);
            } else {
                inputfield.prop("checked", false);
            }
            done = true;
        }
        if (set_editor_content(inputfield, value)) {
            done = true;
        }
        if (inputfield.data().widget === "TaggingInput" || inputfield.data().widget === "EmailTaggingInput") {
            var tagifyelement = inputfield.data().tagify;
            if(tagifyelement!=undefined){
                tagifyelement.removeAllTags();
                tagifyelement.loadOriginalValues(value);
            }
            done = false;
        }


        // New code for testing  (*** start ***)
        // data loading in select, autocompleteselect, autocompletemultiselect
        else if (inputfield.is('select') && inputfield.data().widget === "Select") {
            inputfield.val(value).trigger('change');
            done = true;
        } else if (inputfield.is('select') && inputfield.data().widget === "AutocompleteSelect") {
            let data = value;

            if (data) {
                let newOption = new Option(data.text, data.id, true, true);
                inputfield.append(newOption).trigger('change');
            }

            done = true;
        } else if (inputfield.is('select') && inputfield.data().widget === "AutocompleteSelectMultiple") {

            if (Array.isArray(value)) {
                value.forEach(item => {
                    let newOption = new Option(item.text, item.id, true, true);
                    inputfield.append(newOption);
                });
                inputfield.trigger('change');
            }
            done = true;
        }
        // New code for testing  (*** end ***)

        if (!done) {
            inputfield.val(value);
        }
    });
}

function updateInstanceForm(form, data) {
    for (let key in data) {
        if (data.hasOwnProperty(key)) {
            updateInstanceValuesForm(form, key, data[key])
        }
    }
}
