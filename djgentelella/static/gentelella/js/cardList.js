class CardList {
  constructor(containerId, apiUrl) {
    this.container = document.getElementById(containerId);
    this.apiUrl = apiUrl;
    this.page = 1;
    this.paginate = 10;
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
            paginate: this.paginate,
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

    this.container.innerHTML = Sqrl.render(this.template, data);
  }

  changePage(newPage) {
    if (newPage >= 1 && newPage <= this.totalPages) {
      this.page = newPage;
      this.fetchData();
    }
  }
}
