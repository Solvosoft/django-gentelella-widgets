class CardList {
  constructor(containerId, apiUrl, actions={}) {
    this.container = document.getElementById(containerId);
    this.apiUrl = apiUrl;
    this.page = 1;
    this.data=null;
    this.page_size = 10;
    this.totalPages = 1;
    this.recordsTotal = 0;
    this.template = '';
    this.filters = {};
    this.actions=actions;
    this.fetchData();

  }

  async fetchData() {
    try {
        const queryParams = new URLSearchParams({
            page: this.page,
            page_size: this.page_size,
            ...(this.filters || {}),
        }).toString();

        const url = `${this.apiUrl}?${queryParams}`;
        const response = await fetch(url);
        if (!response.ok) throw new Error(`Error HTTP: ${response.status}`);

        const data = await response.json();
        this.template =  data.template || this.template;
        this.totalPages = data.totalPages || 1;
        this.recordsTotal = data.recordsTotal || 0;
        this.process_data(data);
        this.render(data);
    } catch (error) {
        console.error('Error fetching data:', error);
    }
  }

  process_data(data){
    this.data={};
    data.data.forEach(item => {
            this.data[item.id]=item;
    })
  }

  render(data) {
    if (!this.template) {
      console.error("No template found!");
      return;
    }
    this.container.innerHTML = Sqrl.render(this.template, data,  Sqrl.getConfig({ tags: ["<%", "%>"] }));
    gt_find_initialize_from_dom(this.container);
    this.doPagination();
    this.dofiltering();
    this.doPageSizeOptions();
    this.doObjActions()
  }

  async getFilters(){
    const form = this.container.querySelectorAll('.filter_form');

    const result = await convertToStringJson(form);
    this.filters = JSON.parse(result);
    this.fetchData();
  }
  dofiltering(){
  /**
    const forminput = this.container.querySelectorAll('.filter_form input, .filter_form select');
    const parent=this;
    forminput.forEach(input => {
            input.onchange=function(event){
                parent.getFilters();
            }
       });
   **/
  }
  doPageSizeOptions(){
    const formselect = this.container.querySelectorAll('.page_size_select');
    const parent=this;
    parent.page_size=parseInt(formselect[0].value);
    formselect.forEach(input => {
            input.onchange=function(event){
                parent.page_size=event.target.value
                parent.getFilters();
            }
       });

  }
  doPagination(){
    const alink = this.container.querySelectorAll('.pagination a');
    const parent=this;
    alink.forEach(link => {
         link.onclick = function(event) {
         parent.page=event.target.dataset.page;
         parent.fetchData();
         }
    });
  }
  doObjActions(){
    const actions = this.container.querySelectorAll('.obj_action');
    const parent=this;
    actions.forEach(action => {
         action.onclick = function(event) {
            event.preventDefault();
            var pk = action.dataset.instance;
            var name = action.dataset.action;
            if (typeof parent.actions[name] === 'function') {
                parent.actions[name](pk, parent.data[pk]);
            }
         }
    })
    const generalactions = this.container.querySelectorAll('.general_action');
    generalactions.forEach(action => {
         action.onclick = function(event) {
            event.preventDefault();
            var name = action.dataset.action;
            if (typeof parent.actions[name] === 'function') {
                parent.actions[name]();
            }else{
                 if (typeof parent[name] === 'function') parent[name]();
            }
         }
    })
  }
  search(){
     this.getFilters();
  }
  clean(){
    const form = this.container.querySelectorAll('.filter_form');
    clear_action_form(form);
    this.container.querySelectorAll('.filter_form input').forEach(i=>{i.value="";});
    this.getFilters();
  }
}
