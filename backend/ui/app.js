const API_BASE = "http://127.0.0.1:8123/api";

const STATUS_BUTTONS = [
    { key: "stock", label: "Есть на складе" },
    { key: "printing", label: "Печать" },
    { key: "delay", label: "Отложить" },
    { key: "done", label: "Готово" }
];

async function loadItems() {
    const res = await fetch(`${API_BASE}/items`);
    const data = await res.json();

    const tbody = document.querySelector("#items-table tbody");
    tbody.innerHTML = "";

    data.items.forEach(item => {
        const tr = document.createElement("tr");

        // IMAGE
        const imgTd = document.createElement("td");
        if (item.image_url) {
            const img = document.createElement("img");
            img.src = item.image_url;
            img.className = "product-image";
            imgTd.appendChild(img);
        }
        tr.appendChild(imgTd);

        tr.innerHTML += `
            <td>${item.offer_id}</td>
            <td>${item.category || ""}</td>
            <td>${item.quantity || 1}</td>
            <td class="status">${item.status}</td>
        `;

        // ACTIONS
        const actionsTd = document.createElement("td");
        actionsTd.className = "actions";

        STATUS_BUTTONS.forEach(btn => {
            const b = document.createElement("button");
            b.textContent = btn.label;
            b.onclick = () => updateStatus(item.item_id, btn.key);
            actionsTd.appendChild(b);
        });

        tr.appendChild(actionsTd);
        tbody.appendChild(tr);
    });
}

async function updateStatus(itemId, newStatus) {
    await fetch(`${API_BASE}/item/update`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            item_id: itemId,
            new_status: newStatus,
            user: "designer"
        })
    });

    loadItems(); // refresh
}

loadItems();
