class CardList {
  constructor(containerId, apiUrl) {
    this.container = document.getElementById(containerId);
    this.apiUrl = apiUrl;
    this.page = 1;
    this.page_size = 10;
    this.totalPages = 1;
    this.recordsTotal = 0;
    this.template = '';
    this.filters = {};
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
        this.template = this.template || data.template;
        this.totalPages = data.totalPages || 1;
        this.recordsTotal = data.recordsTotal || 0;

        this.render(data);
    } catch (error) {
        console.error('Error fetching data:', error);
    }
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
  }

  getFilters(){
    const form = this.container.querySelectorAll('.filter_form');

  }
  dofiltering(){
    const forminput = this.container.querySelectorAll('.filter_form input');
        const parent=this;
        forminput.forEach(input => {
            input.onchange=function(event){
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
}
