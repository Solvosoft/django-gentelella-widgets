$(document).ready(function () {
    // Initialize iCheck for main checkboxes
    $('.mainCheckbox').iCheck({
        checkboxClass: 'icheckbox_flat-green'
    });

    // Initialize variables
    let selected_user_or_group = false;
    let option = 1;
    let group_id = 0;
    let user_id = 0;

    const Toast = Swal.mixin({
        toast: true,
        position: 'top-end',
        showConfirmButton: false,
        timer: 3000,
        timerProgressBar: true,
        didOpen: (toast) => {
            toast.addEventListener('mouseenter', Swal.stopTimer);
            toast.addEventListener('mouseleave', Swal.resumeTimer);
        }
    });

    // Function to load related permissions and restore checkbox states
    function loadRelatedPermissions(permissionId, internalCheckboxes) {
        // Get related permissions from the API
        const urlrelated = apiRelatedPermissionsUrl.replace("0", permissionId);

        $.ajax({
            url: urlrelated,
            type: 'GET',
            success: function (data) {
                console.log('Related permissions data:', data);

                // Verify if related permissions exist
                if (data && data.related_permissions && data.related_permissions.length > 0) {
                    const relatedPermissions = data.related_permissions;
                    let relatedPermissionsHtml = '';

                    for (let i = 0; i < relatedPermissions.length; i++) {
                        const relatedPermissionId = relatedPermissions[i].id;
                        const isChecked = localStorage.getItem('checkbox_' + relatedPermissionId) === 'true' ? ' checked' : '';

                        relatedPermissionsHtml += '<div class="checkboxContainer">' +
                            '<div class="internalCheckboxContainer">' +
                            '<input type="checkbox" name="permission" class="flat internalCheckbox" id="internal' + relatedPermissionId + '" name="internal' + relatedPermissionId + '" value="' + relatedPermissionId + '"' + isChecked + '>' +
                            '<label class="internalCheckboxLabel" for="internal' + relatedPermissionId + '">' + relatedPermissions[i].name + '</label>' +
                            '</div>' +
                            '</div>';
                    }

                    internalCheckboxes.html(relatedPermissionsHtml).show();

                    // Initialize iCheck for related permissions
                    internalCheckboxes.find('.internalCheckbox').iCheck({
                        checkboxClass: 'icheckbox_flat-green'
                    });

                    // Add ifChecked and ifUnchecked events to the new related permissions
                    internalCheckboxes.find('.internalCheckbox').on('ifChecked', function (event) {
                        const internalPermissionId = $(this).attr('id').replace('internal', '');

                        // Update checkbox state in localStorage
                        localStorage.setItem('checkbox_' + internalPermissionId, true);

                        const relatedRelatedCheckboxes = $(this).closest('.row').find('.relatedRelatedCheckboxes');

                        // Load related permissions of related permissions (recursion)
                        loadRelatedPermissions(internalPermissionId, relatedRelatedCheckboxes);
                    });

                    internalCheckboxes.find('.internalCheckbox').on('ifUnchecked', function (event) {
                        const internalPermissionId = $(this).attr('id').replace('internal', '');

                        // Update checkbox state in localStorage
                        localStorage.setItem('checkbox_' + internalPermissionId, false);

                        // Hide the checkboxes
                        $(this).closest('.row').find('.relatedRelatedCheckboxes').empty().hide();
                    });
                } else {
                    // If there are no related permissions, display that message
                    internalCheckboxes.html('No related permissions for this main permission.').show();
                }
            },
            error: function (error) {
                console.error('Error fetching related permissions:', error);
            }
        });
    }

    // Add ifChecked event to the main checkboxes
    $('.mainCheckbox').on('ifChecked', function (event) {
        // Get the id of main permissions
        const permissionId = $(this).attr('id').replace('checkbox', '');

        const internalCheckboxes = $(this).closest('.row').find('.internalCheckboxes');

        // Load related permissions and restore checkbox states
        loadRelatedPermissions(permissionId, internalCheckboxes);
    });

    $('.mainCheckbox').on('ifUnchecked', function (event) {
        $(this).closest('.row').find('.internalCheckboxes').empty().hide();
    });

    let selectuser = $('#select_user');
    let selectgroup = $('#select_group');

    if (selectuser.length > 0) {
        let selectusercontext = {
            ajax: {
                url: permission_context.select_user_url,
                dataType: 'json',
            },
            width: '100%'
        };
        extract_select2_context(selectusercontext, selectuser);
        selectusercontext.placeholder = permission_context.user_placeholder;
        selectuser.select2(selectusercontext);
        $("#group_container").hide();
        $('#btn_user').click(function () {
            selected_user_or_group = false;
            $("#user_container").show();
            $("#group_container").hide();
            const checkboxes = $('input[type="checkbox"][name="permission"]');
            checkboxchecked = checkboxes.filter(':checked');
            checkboxchecked.iCheck('uncheck');
            $("#select_user").empty().trigger('change')
            $("#select_group").empty().trigger('change')
            option = 1;
        });
    }

    if (selectgroup.length > 0) {
        let selectgroupcontext = {
            ajax: {
                url: permission_context.select_group_url,
                dataType: 'json',
            },
            width: '100%'
        };

        extract_select2_context(selectgroupcontext, selectgroup);
        selectgroupcontext.placeholder = permission_context.group_placeholder;
        selectgroup.select2(selectgroupcontext);
        $("#btn_group").click(function () {
            $("#group_container").show();
            selected_user_or_group = false;
            $("#user_container").hide();
            const checkboxes = $('input[type="checkbox"][name="permission"]');
            checkboxchecked = checkboxes.filter(':checked');
            checkboxchecked.iCheck('uncheck');
            $("#select_user").empty().trigger('change')
            $("#select_group").empty().trigger('change')
            option = 2;
        });
        if (selectuser.length == 0) {
            option = 2;
        }
    }

    $('.btn-bs-toggle').click(function () {
        $(this).find('.btn').toggleClass('active');
        if ($(this).find('.btn-primary').length > 0) {
            $(this).find('.btn').toggleClass('btn-primary');
        }
        $(this).find('.btn').toggleClass('btn-default');
    });

    $('#select_user, #select_group').on('select2:select', function (evt) {
        selected_user_or_group = true;
        if (option == 1) {
            user_id = evt.params.data.id;
        } else {
            group_id = evt.params.data.id;
        }
        const url = permission_context.get_permissions.replace("/0", "/" + evt.params.data.id);
        const urlname = encodeURIComponent($('#btn_perms').data("urlname"));
        const get_permissions_url = url + "?option=" + option + "&urlname=" + urlname;
        $.ajax({
            url: get_permissions_url,
            method: 'GET',
            dataType: "json",
            success: function (data) {
                const checkboxes = $('input[type="checkbox"][name="permission"]');
                if (data['result'].length > 0) {
                    checkboxchecked = checkboxes.filter(':checked');
                    checkboxchecked.iCheck('uncheck');
                    data['result'].forEach(function (i) {
                        $('input[type="checkbox"][value="' + i.id + '"]').iCheck('check');
                    });
                    const relatedPermissions = data['related_permissions'];
                    if (relatedPermissions && relatedPermissions.length > 0) {
                        relatedPermissions.forEach(function (relatedPerm) {
                            $('input[type="checkbox"][value="' + relatedPerm.id + '"]').iCheck('check');
                        });
                    }
                } else {
                    checkboxchecked = checkboxes.filter(':checked');
                    checkboxchecked.iCheck('uncheck');
                }
            },
            error: function (xhr, ajaxOptions, thrownError) {
                if (xhr.status == 404) {
                    const object = (option == 2) ? permission_context.group_label : permission_context.user_label;
                    const message = permission_context.not_found_object + " " + object.toLowerCase()
                }
            }
        });
    });

    function update_categorieicon_collapsed() {
        Array.from($('a.categories')).forEach(function (categorie) {
            categorie.addEventListener('click', function () {
                let icon = null;
                if ($(this).children()) {
                    icon = $(this).children()[0];
                }
                if ($($(this).data('target')).is(":visible") == true) {
                    if (icon) {
                        $(icon).removeClass('fa fa-minus');
                        $(icon).addClass('fa fa-plus');
                    }
                } else {
                    if (icon) {
                        $(icon).removeClass('fa fa-plus');
                        $(icon).addClass('fa fa-minus');
                    }
                }
            });
        });
    }

    $('#permission_modal').on('show.bs.modal', function (e) {
        const urltarget = $(e.relatedTarget).data('parameter');

        $.ajax({
            url: urltarget,
            method: 'GET',
            dataType: "json",
            success: function (data) {
                const result = data['result'];
                if (result == "") {
                    result = permission_context.not_found_permissions_label;
                }
                $('#permissionbody').html(result);
                $('input[type="checkbox"][name="permission"]').iCheck({
                    checkboxClass: 'icheckbox_flat-green',
                    radioClass: 'iradio_flat-green',
                    increaseArea: '20%' // optional
                });
                update_categorieicon_collapsed();
            },
            error: function (xhr, ajaxOptions, thrownError) {
                if (xhr.status == 404) {
                    $('#permissionbody').html(permission_context.not_found_permissions_label);
                }
            }
        });
    });

    $("#btn_savepermissions").click(function () {
        if ($('#btn_perms').data("urlname") != "") {
            if (selected_user_or_group) {
                const permsurl_save = permission_context.save_permissions;
                const selected = [];
                const inputs_selected = $('input[type="checkbox"][name="permission"]').filter(":checked");
                for (let i = 0; i < inputs_selected.length; i++) {
                    selected.push($(inputs_selected[i]).val());
                }
                const data_save = {
                    "option": option,
                    "permissions": selected,
                    "urlname": $('#btn_perms').data("urlname"),
                };
                if (option == 2) {
                    data_save['group'] = group_id;
                } else {
                    data_save['user'] = user_id;
                }

                $.ajax({
                    url: permsurl_save,
                    method: "POST",
                    dataType: "json",
                    data: data_save,
                    traditional: true,
                    headers: { 'X-CSRFToken': getCookie('csrftoken') },
                    success: function (data) {

                        if (data.result == 'error') {
                            Toast.fire({
                                icon: 'error',
                                title: permission_context.validation_error
                            });
                            return;
                        }
                        const checkboxes = $('input[type="checkbox"][name="permission"]');
                        checkboxchecked = checkboxes.filter(':checked');
                        checkboxchecked.iCheck('uncheck');
                        $("#select_user").empty().trigger('change')
                        $("#select_group").empty().trigger('change')
                        Toast.fire({
                            icon: 'success',
                            title: permission_context.save_messages
                        });
                        selected_user_or_group = false;
                        $('#permission_modal').modal('hide');
                    },
                    error: function (xhr, ajaxOptions, thrownError) {
                        let message = permission_context.error
                        if (xhr.status == 404) {
                            const object = (option == 2) ? permission_context.group_label : permission_context.user_label;
                            message = permission_context.not_found_object + " " + object.toLowerCase()
                        }
                        Toast.fire({
                            icon: 'error',
                            title: message,
                        });
                    }
                });
            } else {

                Toast.fire({
                    icon: 'error',
                    title: permission_context.not_select_valid_option
                });
            }
        } else {
            Toast.fire({
                icon: 'error',
                title: permission_context.not_found_permissions_label
            });
        }

    });
});
