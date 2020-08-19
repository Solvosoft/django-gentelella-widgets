
function gtforms(index,manager, formList)  {
    return {
        index: index,
        order: index,
        manager: manager,
        formList: formList,
        instance: null,
        deleteForm: function(){
            this.instance.hide();
            this.instance.find('input[name="'+this.manager.prefix+'-'+this.index+'-DELETE"]').prop( "checked", true );
        },
        render: function(){
            var html = this.manager.template.replace(/__prefix__/gi, this.index);
            this.instance = $(html);
            formList.append(this.instance);
            this.initializeWidgets(this.instance);
            this.registerBtns();

        },
        reorder: function(new_index, oper){},
        registerBtns: function(){
            this.instance.find('.deletebtn').on('click', this.callDelete(this));
            this.instance.find('.btndown').on('click', this.callReorder(this, this.index-1, -1));
            this.instance.find('.btnup').on('click', this.callReorder(this, this.index+1, 1));
        },
        callDelete: function(instance){
            return () => { instance.deleteForm() };
        },
        initializeWidgets: function(instance){},
        callReorder: function(instance, new_index, oper){
            return () => { instance.reorder(new_index, oper) }
        }

    }
}

function gtformSetManager(instance) {
    var obj = {
        index: 0,
        TOTAL_FORMS: 0,
        INITIAL_FORMS: 0,
        MAX_NUM_FORMS: -1,
        MIN_NUM_FORMS: -1,
        forms: [],
        instance: instance,
        formsetControl: instance.find('.formsetcontrol'),
        formList: instance.find('.formlist'),
        template: '',
        prefix: 'form-',
        initialize: function(){
         this.template = this.formsetControl.find(".formsettemplate").contents()[0].data;
         this.prefix = this.formsetControl.data('prefix');
         this.loadManagementForm();
         this.instance.find('.formsetadd').on('click', this.addBtnForm(this));
        },
        addBtnForm: function(instance){
            return () => { instance.addEmtpyForm() };
        },
        addEmtpyForm: function(){
            var form = gtforms(this.index, this, this.formList);
            form.render();
            this.forms.push(this.formList);
            this.index += 1;
        },
        addForm: function(object){},
        deleteForm: function(index){},
        validateAddForm: function(){},
        validateDeleteForm: function(){},
        loadManagementForm: function(){
            this.TOTAL_FORMS = this.formsetControl.find('input[name="'+this.prefix+'-TOTAL_FORMS"]').val();
            this.INITIAL_FORMS = this.formsetControl.find('input[name="'+this.prefix+'-INITIAL_FORMS"]').val();
            this.MIN_NUM_FORMS = this.formsetControl.find('input[name="'+this.prefix+'-MIN_NUM_FORMS"]').val();
            this.MAX_NUM_FORMS = this.formsetControl.find('input[name="'+this.prefix+'-MAX_NUM_FORMS"]').val();
        },
        updateManagementForm: function(){
            this.formsetControl.find('input[name="'+this.prefix+'-TOTAL_FORMS"]').val(this.TOTAL_FORMS);
            this.formsetControl.find('input[name="'+this.prefix+'-INITIAL_FORMS"]').val(this.INITIAL_FORMS);
            this.formsetControl.find('input[name="'+this.prefix+'-MIN_NUM_FORMS"]').val(this.MIN_NUM_FORMS);
            this.formsetControl.find('input[name="'+this.prefix+'-MAX_NUM_FORMS"]').val(this.MAX_NUM_FORMS);
        }

    }
    obj.initialize();
    return obj;
}

$(document).ready(function(){
   $(".formset").each(function(index, elem){
        gtformSetManager($(elem));
   });
});