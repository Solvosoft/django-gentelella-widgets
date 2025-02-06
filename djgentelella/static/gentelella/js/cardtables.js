class CardTable {
    constructor(containerId, config, preloadedData = []) {
        this.container = document.getElementById(containerId);
        this.config = config;
        this.data = preloadedData.length > 0 ? preloadedData : [];
        this.filteredData = [...this.data];
        this.currentPage = 1;
        this.itemsPerPage = 6;
        this.sortField = "titulo";
        this.sortOrder = "asc";
        this.init();
    }

    async init() {
        if (this.config.apiUrl !== "#" && this.data.length === 0) {
            await this.fetchData(); // Solo hace fetch si apiUrl está definido y no hay datos precargados
        }
        this.render();
        console.log("Corriendo mi archivo cardtables.js!!!");
    }

    async fetchData() {
        try {
            const response = await fetch(this.config.apiUrl);
            this.data = await response.json();
            this.filteredData = [...this.data];
        } catch (error) {
            console.error("Error cargando datos:", error);
        }
    }

    render() {
        this.container.innerHTML = `
            <div class="container mt-4">
            <!-- Filtros y búsqueda -->
            <div class="row g-2 mb-3">
            <div class="col-md-3">
                <input type="text" id="searchInput" placeholder="Buscar..." class="form-control" onkeyup="cardTable.filterData()">
                </div>
                <div class="col-md-3">
                <input type="date" id="dateStart" class="form-control">
                </div>
                <div class="col-md-3">
                <input type="date" id="dateEnd" class="form-control">
                </div>
                <div class="col-md-2">
                <select id="sortField" class="form-select">
                    <option value="titulo">Título</option>
                    <option value="fecha_creacion">Fecha</option>
                </select>
                </div>
                <div class="col-md-1">
                <button onclick="cardTable.filterData()" class="btn btn-primary w-100">Filtrar</button>
                </div>
            </div>
            <!-- Contenedor de Cards -->
            <div class="row row-cols-1 row-cols-md-3 g-3 " id="cardList"></div>

            <!-- Paginación -->
<div class="row">
    <div class="col-sm-12 col-md-5">
        <div class="dataTables_info" id="datatableelement_info" role="status" aria-live="polite">
            Mostrando 1 a 10 de 10 registros
        </div>
    </div>
    <div class="col-sm-12 col-md-7">
        <div class="dataTables_paginate paging_full_numbers" id="datatableelement_paginate">
            <ul class="pagination justify-content-end">
                <li class="paginate_button page-item first" id="datatableelement_first">
                    <a href="#" onclick="cardTable.changePage('first')" class="page-link">Primero</a>
                </li>
                <li class="paginate_button page-item previous" id="datatableelement_previous">
                    <a href="#" onclick="cardTable.changePage(-1)" class="page-link">Anterior</a>
                </li>
                <li class="paginate_button page-item active">
                    <a href="#" id="pageInfo" class="page-link">1</a>
                </li>
                <li class="paginate_button page-item next" id="datatableelement_next">
                    <a href="#" onclick="cardTable.changePage(1)" class="page-link">Siguiente</a>
                </li>
                <li class="paginate_button page-item last" id="datatableelement_last">
                    <a href="#" onclick="cardTable.changePage('last')" class="page-link">Último</a>
                </li>
            </ul>
        </div>
    </div>
</div>



            <!-- Modal de Confirmación para Eliminar -->
            <div id="modalConfirm" class="modal" tabindex="-1">
            <div class="modal-dialog">
                <div class="modal-content">
                <div class="modal-header">
                <h5 class="modal-title">Eliminacion</h5>
                <button type="button" class="btn-close" onclick="cardTable.closeModal()" aria-label="Close"></button>
                </div>
                <div class="modal-body">
                    <p>¿Seguro que deseas eliminar este formulario?</p>
                    </div>
                    <div class="modal-footer">
                    <button class="btn btn-secondary" onclick="cardTable.confirmDelete(true)">Sí</button>
                    <button class="btn btn-primary" onclick="cardTable.closeModal()">No</button>
                    </div>
                    </div>
                </div>
            </div>

            <!-- Modal Dinámico para Ver o Editar -->
            <div id="modalViewEdit" class="modal" tabindex="-1">
            <div class="modal-dialog">
                <div class="modal-content">
                <div class="modal-header">
                <h5 class="modal-title" id="modalTitle">Modal title</h5>
                    <button type="button" class="btn-close" onclick="cardTable.closeViewEditModal()" aria-label="Close"></button>
                    </div>
                    <div id="modalBody" class="modal-body">
                    </div>
                    <div class="modal-footer">
                    <button class="btn btn-primary" id="saveChangesBtn" onclick="cardTable.saveChanges()">Guardar Cambios</button>
                    </div>
                    </div>
                </div>
            </div>
        `;
        this.updateCards();
    }

    updateCards() {
        const cardList = document.getElementById("cardList");
        cardList.classList.add("row", "row-cols-1", "row-cols-md-3", "g-4", "mb-3");
        cardList.innerHTML = "";

        const startIndex = (this.currentPage - 1) * this.itemsPerPage;
        const endIndex = startIndex + this.itemsPerPage;
        const pageData = this.filteredData.slice(startIndex, endIndex);

        pageData.forEach(item => {
            const separed_card = document.createElement("div");
            separed_card.classList.add("col-12", "col-md-4");
            const card = document.createElement("div");
            let buttons = "";
            card.classList.add("card");
            if(this.config.actions?.view){
                buttons += `<button class="btn btn-sm btn-info view-btn" onclick="cardTable.viewCard(${item.id})">👁 Ver</button>`;
            }
            if(this.config.actions?.edit){
                buttons += `<button class="btn btn-sm btn-warning view-btn" onclick="cardTable.editCard(${item.id})">✏ Editar</button>`;
            }
            if(this.config.actions?.delete){
                buttons += `<button class="delete-btn btn btn-sm btn-warning view-btn" onclick="cardTable.showModal(${item.id})">X</button>`;
            }
            card.innerHTML = `
                <div class="card-body">

                <h5 class="card-title">${item.titulo}</h3>
                <p class="card-text">${item.descripcion}</p>
                    ${buttons}
                </div>
            `;
            separed_card.appendChild(card);
            cardList.appendChild(separed_card);
        });

        document.getElementById("pageInfo").innerText = `Página ${this.currentPage}`;
        this.updatePagination();
    }

    filterData() {
        const searchText = document.getElementById("searchInput").value.toLowerCase();
        const dateStart = document.getElementById("dateStart").value;
        const dateEnd = document.getElementById("dateEnd").value;
        const sortField = document.getElementById("sortField").value;

        this.filteredData = this.data.filter(item => {
            const matchesSearch = item.titulo.toLowerCase().includes(searchText);
            const matchesDate = (!dateStart || item.fecha_creacion >= dateStart) &&
                                (!dateEnd || item.fecha_creacion <= dateEnd);
            return matchesSearch && matchesDate;
        });

        this.filteredData.sort((a, b) => {
            return this.sortOrder === "asc" ? a[sortField] > b[sortField] ? 1 : -1 : a[sortField] < b[sortField] ? 1 : -1;
        });

        this.currentPage = 1;
        this.updateCards();
    }

    changePage(direction) {
        const totalPages = Math.ceil(this.filteredData.length / this.itemsPerPage);

    if (direction === "first") {
        this.currentPage = 1;
    } else if (direction === "last") {
        this.currentPage = totalPages;
    } else {
        this.currentPage = Math.min(Math.max(this.currentPage + direction, 1), totalPages);
    }
    console.log("Cambiando a la página:", this.currentPage); // 🛠 Agregar log para depuración
    this.updateCards();
    this.updatePagination();
    }

    updatePagination() {
    const totalItems = this.filteredData.length;
    const totalPages = Math.ceil(totalItems / this.itemsPerPage);

    const pageInfo = document.getElementById("datatableelement_info");
    const firstBtn = document.getElementById("datatableelement_first");
    const prevBtn = document.getElementById("datatableelement_previous");
    const nextBtn = document.getElementById("datatableelement_next");
    const lastBtn = document.getElementById("datatableelement_last");

    // Actualizar el texto "Mostrando X a Y de Z registros"
    const startIndex = (this.currentPage - 1) * this.itemsPerPage + 1;
    const endIndex = Math.min(this.currentPage * this.itemsPerPage, totalItems);
    pageInfo.innerText = `Mostrando ${startIndex} a ${endIndex} de ${totalItems} registros`;

    // Control de botones
    firstBtn.classList.toggle("disabled", this.currentPage === 1);
    prevBtn.classList.toggle("disabled", this.currentPage === 1);
    nextBtn.classList.toggle("disabled", this.currentPage >= totalPages);
    lastBtn.classList.toggle("disabled", this.currentPage >= totalPages);

    // Actualizar número de página
    document.getElementById("pageInfo").innerText = this.currentPage;
}

    showModal(id) {
        this.deleteId = id;
        document.getElementById("modalConfirm").style.display = "block";
    }

    closeModal() {
        document.getElementById("modalConfirm").style.display = "none";
    }

    confirmDelete(confirm) {
        if (confirm) this.deleteCard(this.deleteId);
        this.closeModal();
    }

    async deleteCard(id) {
        try {
            await fetch(`${this.config.apiUrl}/${id}/`, { method: "DELETE" });
            this.data = this.data.filter(item => item.id !== id);
            this.filteredData = [...this.data];
            this.updateCards();
        } catch (error) {
            console.error("Error eliminando:", error);
        }
    }

    viewCard(id) {
        const item = this.data.find(form => form.id === id);
        if (!item) return;

        document.getElementById("modalTitle").innerText = "Detalles del Formulario";
        document.getElementById("modalBody").innerHTML = `
            <p><strong>Título:</strong> ${item.titulo}</p>
            <p><strong>Descripción:</strong> ${item.descripcion}</p>
            <p><strong>Fecha de Creación:</strong> ${item.fecha_creacion}</p>
        `;
        document.getElementById("saveChangesBtn").style.display = "none"; // Ocultar botón de Guardar
        document.getElementById("modalViewEdit").style.display = "block";
    }

    editCard(id) {
        const item = this.data.find(form => form.id === id);
        if (!item) return;

        document.getElementById("modalTitle").innerText = "Editar Formulario";
        document.getElementById("modalBody").innerHTML = `
        <div class="mb-3">
            <label class="form-label">Título:</label>
            <input type="text" class="form-control" id="editTitulo" value="${item.titulo}">
            </div>
            <div class="mb-3">
            <label class="form-label">Descripción:</label>
            <textarea class="form-control" row="3" id="editDescripcion">${item.descripcion}</textarea>
            </div>
        `;
        document.getElementById("saveChangesBtn").style.display = "block";
        document.getElementById("saveChangesBtn").setAttribute("data-id", id);
        document.getElementById("modalViewEdit").style.display = "block";
    }

    saveChanges() {
        const id = document.getElementById("saveChangesBtn").getAttribute("data-id");
        const newTitulo = document.getElementById("editTitulo").value;
        const newDescripcion = document.getElementById("editDescripcion").value;

        const item = this.data.find(form => form.id == id);
        if (item) {
            item.titulo = newTitulo;
            item.descripcion = newDescripcion;
            this.updateCards();
            this.closeViewEditModal();
        }
    }

    closeViewEditModal() {
        document.getElementById("modalViewEdit").style.display = "none";
    }
}
