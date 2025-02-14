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

async function obtainFormAsJSON(form, prefix = '', extras={}) {
  const fields = form.elements;
  const formData = {};
  // typeof variable === 'function'
  for( let key in extras){
    if(typeof extras[key] === 'function'){
        formData[key]=extras[key](form, key, prefix);
    }else{
        formData[key]=extras[key];
    }
  }

  for (let i = 0; i < fields.length; i++) {
    const field = fields[i];

    if (field.type !== 'submit' && field.type !== 'button') {
      const fieldName = field.name.replace(prefix, '');
      if(field.type === 'textarea'){
        formData[fieldName] = $(field).val();
      }else if(field.type === 'checkbox'){
        formData[fieldName] = field.checked;
      }else  if (field.type === 'radio') {
        if(field.checked){
          formData[fieldName] =  $(field).val();
        }
      }else  if (field.type === 'file') {
        const files = Array.from(field.files);
        const filesBase64 = [];

        for (let j = 0; j < files.length; j++) {
          const file = files[j];
          try {
            const base64String = await convertFileToBase64(file);
            filesBase64.push({ name: file.name, value: base64String });
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

  return JSON.stringify(formData);
}

function convertToStringJson(form, prefix="", extras={}){
    result=obtainFormAsJSON(form[0], prefix=prefix, extras=extras);
    return result;
}

function load_errors(error_list, obj, parentdiv){
    ul_obj = "<ul class='errorlist form_errors d-flex justify-content-center'>";
    error_list.forEach((item)=>{
        ul_obj += "<li>"+item+"</li>";
    });
    ul_obj += "</ul>"
    $(obj).parents(parentdiv).prepend(ul_obj);
    return ul_obj;
}

function form_field_errors(target_form, form_errors, prefix, parentdiv){
    var item = "";
    for (const [key, value] of Object.entries(form_errors)) {
        item = " #id_" +prefix+key;
        if(target_form.find(item).length > 0){
            load_errors(form_errors[key], item, parentdiv);
        }
    }
}

function response_manage_type_data(instance, err_json_fn, error_text_fn){
    return function(response) {
        const contentType = response.headers.get("content-type");
        if(response.ok){
             if (contentType && contentType.indexOf("application/json") !== -1) {
                return response.json();
            }else{
                return response.text();
            }
        }else{
            if (contentType && contentType.indexOf("application/json") !== -1) {
                response.json().then(data => err_json_fn(instance, data));
            }else{
                response.text().then(data => error_text_fn(instance, data));
            }
            return Promise.resolve(false);
        }

        return Promise.reject(response);  // then it will go to the catch if it is an error code
    }
}

function clear_action_form(form){
    // clear switchery before the form reset so the check status doesn't get changed before the validation
    $(form).find("input[data-switchery=true]").each(function() {
        if($(this).prop("checked")){  // only reset it if it is checked
            $(this).trigger("click").prop("checked", false);
        }
    });
    $(form).find('[data-widget="TaggingInput"],[data-widget="EmailTaggingInput"]').each(function(i, e) {
         var tg=$(e).data().tagify;
         tg.removeAllTags();
    });
    $(form).find('[data-widget="FileChunkedUpload"],[data-widget="FileInput"]').each(function(i, e) {
         var tg=$(e).data().fileUploadWidget;
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
