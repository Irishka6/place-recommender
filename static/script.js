let currentUser = null;
let searchHistory = [];

async function init() {
    try {
        const response = await fetch('/api/tags');
        const tags = await response.json();
        renderTagDropdown(tags);
        handleSearch();
    } catch (error) {
        console.error("Ошибка инициализации:", error);
        document.getElementById('cardsContainer').innerHTML =
            `<p style="grid-column: 1/-1; text-align: center; color: var(--text-muted); padding: 2rem;">
                Ошибка подключения к серверу. Убедитесь, что FastAPI запущен.
            </p>`;
    }
}

// ==========================================
// ЖИВОЙ ПОИСК ПРИ ВВОДЕ: Обновляет карточки сразу!
// ==========================================
const cityInput = document.getElementById('cityInput');
const visitedInput = document.getElementById('visitedInput');

let searchDebounceTimer = null;

function triggerLiveSearch() {
    clearTimeout(searchDebounceTimer);
    searchDebounceTimer = setTimeout(() => {
        handleSearch();
    }, 200); // Спустя 200 мс после нажатия клавиши карточки обновятся
}

if (cityInput) cityInput.addEventListener('input', triggerLiveSearch);
if (visitedInput) visitedInput.addEventListener('input', triggerLiveSearch);

// ==========================================
// ИНТЕРФЕЙС ФИЛЬТРОВ И МУЛЬТИСЕЛЕКТА
// ==========================================
function toggleDropdown() {
    document.getElementById('multiselectDropdown').classList.toggle('open');
    document.getElementById('tagMultiselectDropdown').classList.remove('open');
}

function toggleTagDropdown() {
    document.getElementById('tagMultiselectDropdown').classList.toggle('open');
    document.getElementById('multiselectDropdown').classList.remove('open');
}

document.addEventListener('click', (e) => {
    const multiselect = document.getElementById('categoryMultiselect');
    const tagMultiselect = document.getElementById('tagMultiselect');

    if (multiselect && !multiselect.contains(e.target)) {
        document.getElementById('multiselectDropdown').classList.remove('open');
    }
    if (tagMultiselect && !tagMultiselect.contains(e.target)) {
        document.getElementById('tagMultiselectDropdown').classList.remove('open');
    }
});

function getSelectedCategories() {
    return Array.from(document.querySelectorAll('#multiselectDropdown input[type="checkbox"]:checked')).map(cb => cb.value);
}

function getSelectedTags() {
    return Array.from(document.querySelectorAll('#tagMultiselectDropdown input[type="checkbox"]:checked')).map(cb => cb.value);
}

function updateMultiselectLabel() {
    const selected = getSelectedCategories();
    const btn = document.getElementById('multiselectBtn');
    btn.textContent = selected.length === 0 ? "Все категории" : (selected.length <= 2 ? selected.join(', ') : `Выбрано: ${selected.length}`);
    handleSearch();
}

function updateTagLabel() {
    const selected = getSelectedTags();
    const btn = document.getElementById('tagMultiselectBtn');
    btn.textContent = selected.length === 0 ? "Любой вайб" : (selected.length <= 2 ? selected.join(', ') : `Выбрано: ${selected.length}`);
    handleSearch();
}

function renderTagDropdown(tags) {
    const container = document.getElementById('tagMultiselectDropdown');
    if (container) {
        container.innerHTML = tags.map(tag => `
            <label class="checkbox-item">
                <input type="checkbox" value="${tag}" onchange="updateTagLabel()"> ${tag}
            </label>
        `).join('');
    }
}

// ==========================================
// ОТРИСОВКА КАРТОЧЕК
// ==========================================
function renderCards(items) {
    const container = document.getElementById('cardsContainer');
    if (items.length === 0) {
        container.innerHTML = `<p style="grid-column: 1/-1; text-align: center; color: var(--text-muted); padding: 2rem;">По вашему запросу ничего не найдено.</p>`;
        return;
    }

    container.innerHTML = items.map(item => {
        const formattedRating = item.rating ? Number(item.rating).toFixed(2) : "5.00";

        return `
        <article class="card" id="card-${item.id}" style="${item.matchType === 'similar' ? 'border: 2px solid var(--tag-bg);' : ''}">
            <div class="card-meta">
                <span>📍 ${item.city || 'Москва'}</span>
                <span class="rating">★ ${formattedRating}</span>
            </div>
            <h3 class="card-title">${item.title}</h3>

            ${item.matchType === 'similar' ? `<span style="font-size: 0.75rem; color: var(--primary); font-weight: bold; margin-bottom: 5px; display: block;">✨ Похоже по вайбу (${item.sharedTagsCount} совпадений)</span>` : ''}

            <p style="font-size: 0.85rem; color: var(--secondary); margin-bottom: 10px;">${item.address}</p>

            <p class="place-summary">${item.desc}</p>
            <button class="toggle-summary-btn" onclick="toggleSummary(${item.id})">Читать далее ▼</button>

            <div class="tags" style="justify-content: space-between; align-items: center;">
                <div style="display:flex; flex-wrap:wrap; gap:0.4rem; flex: 1;">
                    <span class="tag tag-category">${item.category}</span>
                    ${item.tags ? item.tags.map(t => `<span class="tag">${t}</span>`).join('') : ''}
                </div>
            </div>

            <div style="display: flex; gap: 10px; margin-top: 15px; border-top: 1px solid var(--border); padding-top: 15px;">
                <button class="btn btn-outline" style="flex: 1; padding: 0.4rem; font-size: 0.85rem;" onclick="findSimilar('${item.title.replace(/'/g, "\\'")}')">✨ Найти похожее</button>
                ${item.maps_url ? `<a href="${item.maps_url}" target="_blank" class="btn" style="flex: 1; text-align: center; padding: 0.4rem; font-size: 0.85rem; text-decoration: none;">Карта ↗</a>` : ''}
            </div>
        </article>
        `;
    }).join('');
}

function toggleSummary(id) {
    const card = document.getElementById(`card-${id}`);
    const btn = card.querySelector('.toggle-summary-btn');
    card.classList.toggle('expanded');
    btn.textContent = card.classList.contains('expanded') ? 'Свернуть ▲' : 'Читать далее ▼';
}

function findSimilar(title) {
    document.getElementById('cityInput').value = title;
    handleSearch();
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ==========================================
// ПОИСК НА СЕРВЕРЕ (ЗАПРОС К PYTHON)
// ==========================================
async function handleSearch(e) {
    if (e) e.preventDefault();

    const searchString = document.getElementById('cityInput').value.trim();
    const visitedRaw = document.getElementById('visitedInput').value.trim();
    const selectedCategories = getSelectedCategories();
    const selectedTags = getSelectedTags();
    const sortBy = document.getElementById('sortSelect').value;

    const payload = {
        query: searchString,
        visited: visitedRaw,
        categories: selectedCategories,
        tags: selectedTags,
        sortBy: sortBy
    };

    try {
        const response = await fetch('/api/search', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const filteredData = await response.json();
        renderCards(filteredData);
    } catch (error) {
        console.error("Ошибка поиска:", error);
    }

    // Сохраняем в историю только при ручном нажатии на кнопку "Найти"
    if (e && currentUser) {
        searchHistory.unshift({
            time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            searchQuery: searchString || 'Все места',
            excluded: visitedRaw || 'Нет',
            categories: selectedCategories.length ? selectedCategories.join(', ') : 'Все',
            tags: selectedTags.length ? selectedTags.join(', ') : 'Любые'
        });
        renderHistory();
    }
}

// ==========================================
// ВКЛАДКИ И АВТОРИЗАЦИЯ
// ==========================================
function switchTab(tabName) {
    document.querySelectorAll('.tab-btn').forEach((btn, idx) => {
        btn.classList.toggle('active', (tabName === 'search' && idx === 0) || (tabName === 'history' && idx === 1));
    });
    document.getElementById('tab-search').classList.toggle('active', tabName === 'search');
    document.getElementById('tab-history').classList.toggle('active', tabName === 'history');
    if (tabName === 'history') renderHistory();
}

function renderHistory() {
    const container = document.getElementById('historyContainer');
    if (!currentUser) {
        container.innerHTML = `<div class="locked-message"><h3>Раздел доступен только авторизованным пользователям</h3><button class="btn" onclick="handleAuthClick()" style="margin-top: 1rem;">Войти</button></div>`;
        return;
    }
    if (searchHistory.length === 0) {
        container.innerHTML = `<div class="locked-message"><p>История поиска пока пуста.</p></div>`;
        return;
    }
    container.innerHTML = `<h3 style="margin-bottom: 1rem;">Ваши недавние запросы</h3>` + searchHistory.map(item => `
        <div class="history-item">
            <div><strong>Искали:</strong> ${item.searchQuery} | <strong>Теги:</strong> ${item.tags}</div>
            <span style="color: var(--text-muted); font-size: 0.85rem;">${item.time}</span>
        </div>
    `).join('');
}

function handleAuthClick() {
    if (currentUser) {
        currentUser = null;
        searchHistory = [];
        updateAuthUI();
        renderHistory();
    } else {
        document.getElementById('authModal').classList.add('open');
    }
}

function closeModal() { document.getElementById('authModal').classList.remove('open'); }

function login(e) {
    e.preventDefault();
    const username = document.getElementById('username').value.trim();
    if (username) {
        currentUser = username;
        updateAuthUI();
        closeModal();
        renderHistory();
    }
}

function updateAuthUI() {
    document.getElementById('userStatus').textContent = currentUser ? `👤 ${currentUser}` : 'Гость';
    document.getElementById('authBtn').textContent = currentUser ? 'Выйти' : 'Войти';
}

init();