function gtforms(index,manager, formList, extra=true)  {
    return {
        index: index,
        order: index,
        manager: manager,
        formList: formList,
        extra: extra,
        instance: null,
        deleteForm: function(){
          if( !this.manager.validateDeleteForm()) {
            this.manager.notify('error', 'You can not delete this form, minimum form validation failed' )
            return;
          }
            this.instance.hide();
            this.instance.find('input[name="'+this.manager.prefix+'-'+this.index+'-DELETE"]').prop( "checked", true );
            this.manager.deleteForm(this.order);
        },
        render: function(){
            var html = this.manager.template.replace(/__prefix__/gi, this.index);
            this.instance = $(html);
            formList.append(this.instance);
            this.initializeWidgets(this.instance);
            this.registerBtns();

        },
        reorder: function(oper){
            var brother = this.manager.getForm(this.order+oper);
            this.manager.switchFrom(this.order, this.order+oper);
            if(brother != null){
                if(oper == 1 ){
                    this.instance.before(brother.instance);
                }else{
                    brother.instance.before(this.instance);
                }
            }
        },
        registerBtns: function(){
            this.instance.find('.deletebtn').on('click', this.callDelete(this));
            // down increment order and up decrement order when forms are inserted in bottom
            this.instance.find('.btndown').on('click', this.callReorder(this, 1));
            this.instance.find('.btnup').on('click', this.callReorder(this, -1));
        },
        callDelete: function(instance){
            return () => { instance.deleteForm() };
        },
        initializeWidgets: function(instance){
            gt_find_initialize(instance);
        },
        callReorder: function(instance, oper){
            return () => { instance.reorder(oper) }
        },
        updateOrder: function(){
            this.instance.find('input[name="'+this.manager.prefix+'-'+this.index+'-ORDER"]').val(this.order);
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
        validateMax: false,
        validateMin: false,
        activeForms: 0,
        forms: [],
        instance: instance,
        formsetControl: instance.find('.formsetcontrol'),
        formList: instance.find('.formlist'),
        template: '',
        prefix: 'form-',
        initialize: function(){
         this.template = this.formsetControl.find(".formsettemplate").contents()[0].data;
         this.prefix = this.formsetControl.data('prefix');
         this.validateMax = this.formsetControl.data('validate-max') == '1';
         this.validateMin = this.formsetControl.data('validate-min') == '1';
         this.loadManagementForm();
         this.instance.find('.formsetadd').on('click', this.addBtnForm(this));
         this.addFormDom();
        },
        addBtnForm: function(instance){
            return () => { instance.addEmtpyForm()  };
        },
        addEmtpyForm: function(){
            if(this.validateAddForm()){
                var form = gtforms(this.index, this, this.formList);
                form.render();
                this.forms.push(form);
                this.index += 1;
                this.updateTotalForms(+1);
            }else{
                this.notify('error', 'You cannot add new form, limit is exceded')
            }
        },
        addForm: function(object){},
        addFormDom: function(){
            this.formList.children().each((i, element) =>{
                 var form = gtforms(this.index, this, this.formList, extra=false);
                 form.instance = $(element);
                 form.registerBtns();
                 this.forms.push(form);
                 this.index += 1;
            });
        },
        deleteForm: function(index){
            if( !this.validateDeleteForm()) return;
            if(index>=0 && index < this.forms.length){
                if(this.forms[index].extra){
                    this.forms.splice(index, 1);
                    this.updateTotalForms(-1);
                    if(index == this.forms.length){
                        this.index -= 1;
                    }else{
                        for(var x=0; x<this.forms.length; x++){
                            this.forms[x].order = x;
                            this.forms[x].updateOrder();
                        }
                    }
                }

            }
        },
        validateAddForm: function(){
            if(!this.validateMax) return true;
            return this.MAX_NUM_FORMS == -1 || this.TOTAL_FORMS < this.MAX_NUM_FORMS;
        },
        validateDeleteForm: function(){
            if(!this.validateMin) return true;
            return this.MIN_NUM_FORMS == -1 || this.TOTAL_FORMS > this.MIN_NUM_FORMS;
        },
        loadManagementForm: function(){
            this.TOTAL_FORMS = parseInt(this.formsetControl.find('input[name="'+this.prefix+'-TOTAL_FORMS"]').val());
            this.INITIAL_FORMS = parseInt(this.formsetControl.find('input[name="'+this.prefix+'-INITIAL_FORMS"]').val());
            this.MIN_NUM_FORMS = parseInt(this.formsetControl.find('input[name="'+this.prefix+'-MIN_NUM_FORMS"]').val());
            this.MAX_NUM_FORMS = parseInt(this.formsetControl.find('input[name="'+this.prefix+'-MAX_NUM_FORMS"]').val());
        },
        updateManagementForm: function(){
            this.formsetControl.find('input[name="'+this.prefix+'-TOTAL_FORMS"]').val(this.TOTAL_FORMS);
            this.formsetControl.find('input[name="'+this.prefix+'-INITIAL_FORMS"]').val(this.INITIAL_FORMS);
            this.formsetControl.find('input[name="'+this.prefix+'-MIN_NUM_FORMS"]').val(this.MIN_NUM_FORMS);
            this.formsetControl.find('input[name="'+this.prefix+'-MAX_NUM_FORMS"]').val(this.MAX_NUM_FORMS);
        },
        updateTotalForms: function(oper){
            this.TOTAL_FORMS = this.TOTAL_FORMS+oper;
            this.formsetControl.find('input[name="'+this.prefix+'-TOTAL_FORMS"]').val(this.TOTAL_FORMS);
        },
        getForm: function(index){
            if(index>=0 && index < this.forms.length){
                return this.forms[index];
            }
            return null;
        },
        switchFrom: function(fref, fswap){
            var freform = this.getForm(fref);
            var fswapform = this.getForm(fswap);
            if(freform != null && fswapform != null){
                var tmporder = freform.order;
                freform.order = fswapform.order;
                fswapform.order = tmporder;
                freform.updateOrder();
                fswapform.updateOrder();

                this.forms.sort((a, b) => a.order - b.order);
                this.redrawOrdering();
            }

        },
        redrawOrdering: function(){
            for(var x=0; x<this.forms.length; x++){
                 this.formList.append(this.forms[x].instance);
            }
        },
        notify: function(type, text){
            console.log(text);
        },
        clean: function(){
            while(this.forms.length>0){
                var f = this.forms.pop();
                f.instance.remove();
            }
            this.TOTAL_FORMS=0;
            this.INITIAL_FORMS=0;
            this.TOTAL_FORMS=0;
            this.index=0;
            this.updateManagementForm();
        }
    }
    obj.initialize();
    return obj;
}
