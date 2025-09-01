document.addEventListener("DOMContentLoaded", () => {
  const stationSelect = document.getElementById("stationSelect");
  const filterSelect = document.getElementById("filterSelect");

  loadUsers(stationSelect.value, filterSelect.value);

  stationSelect.addEventListener("change", () => {
    loadUsers(stationSelect.value, filterSelect.value);
  });

  filterSelect.addEventListener("change", () => {
    loadUsers(stationSelect.value, filterSelect.value);
  });
});

async function loadUsers(station, filter) {
  try {
    const usersRes = await fetch(`/api/stats/users/${encodeURIComponent(station)}?filter=${encodeURIComponent(filter)}`);
    if (!usersRes.ok) throw new Error("Error al obtener usuarios");
    const users = await usersRes.json();
    renderUsers(users.usuarios || []);
  } catch (e) {
    console.error(e);
  }
}

let currentUsers = [];
let currentPage = 1;
const usersPerPage = 12;

function renderUsers(users) {
  currentUsers = users;
  currentPage = 1;
  showPage(currentPage);
  setupPagination();
}

function showPage(page) {
  const container = document.getElementById("usuariosContainer");
  container.innerHTML = "";

  const start = (page - 1) * usersPerPage;
  const end = start + usersPerPage;
  const pageUsers = currentUsers.slice(start, end);

  pageUsers.forEach(user => {
    const card = document.createElement("div");
    card.classList.add("user-card");
    const tipo = mapVehicleType(user.category);
    const modelo = user.model ? user.model : "-";
    card.innerHTML = `
      <h4>${user.user_name}</h4>
      <p><strong>Cargas:</strong> ${user.total_cargas}</p>
      <p><strong>Energía:</strong> ${user.total_energy_Wh} Wh</p>
      <p><strong>Modelo:</strong> ${modelo}</p>
      <p><strong>Tipo:</strong> ${tipo}</p>
    `;
    container.appendChild(card);
  });

  document.getElementById("pageInfo").textContent =
    `Página ${page} de ${Math.ceil(currentUsers.length / usersPerPage)}`;
}

function mapVehicleType(category) {
  if (!category) return "-";
  const c = String(category).toUpperCase();
  if (c === "EV") return "EV";
  if (c === "PHEV") return "PHEV";
  return "-";
}

function setupPagination() {
  document.getElementById("prevPage").onclick = () => {
    if (currentPage > 1) {
      currentPage--;
      showPage(currentPage);
    }
  };
  document.getElementById("nextPage").onclick = () => {
    if (currentPage < Math.ceil(currentUsers.length / usersPerPage)) {
      currentPage++;
      showPage(currentPage);
    }
  };
}
