// ==========================================
// ДИНАМИЧЕСКИЙ РЕНДЕР ВСЕХ СЕКЦИЙ ИЗ БД
// ==========================================
function renderCatalogFromDB() {
  // 1. Рендер секции "Сегодня"
  const todayEvents = DATABASE.events.filter(ev => ev.section === 'today');
  const todayListEl = document.getElementById('todayList');
  const todayCountBadge = document.getElementById('todayCountBadge');

  if (todayCountBadge) {
    todayCountBadge.textContent = String(todayEvents.length).padStart(2, '0');
  }

  if (todayListEl) {
    todayListEl.innerHTML = todayEvents.map(ev => `
      <article class="today-event" data-event-id="${ev.id}">
        <time>${ev.time}</time>
        <div>
          <span class="tag ${ev.isFree ? 'free' : ''}">${ev.tag}</span>
          <h3>${ev.title}</h3>
          <p>${ev.place}</p>
        </div>
        <b>${ev.price}</b>
        <button type="button" class="event-open-btn" aria-label="Подробнее">↗</button>
      </article>
    `).join('');
  }

  // 2. Рендер секции "Выходные"
  const weekendEvents = DATABASE.events.filter(ev => ev.section === 'weekend');
  const eventGridEl = document.getElementById('eventGrid');

  if (eventGridEl) {
    eventGridEl.innerHTML = weekendEvents.map(ev => `
      <article class="event-card" data-event-id="${ev.id}" data-day="${ev.dayCode}" data-type="${ev.category}">
        <div class="event-visual ${ev.visualClass}">
          <span>${ev.visualDate}</span>
          <b>${(ev.visualTitle || ev.title).replace(/\n/g, '<br>')}</b>
        </div>
        <div class="event-info">
          <span class="tag ${ev.isFree ? 'free' : ''}">${ev.tag}</span>
          <h3>${ev.title}</h3>
          <p>${ev.place}</p>
          <b>${ev.price} <button type="button" class="event-open-btn" aria-label="Подробнее">↗</button></b>
        </div>
      </article>
    `).join('');
  }

  // 3. Рендер секции "Событие недели"
  const featureEv = DATABASE.events.find(ev => ev.section === 'feature');
  const featureEl = document.getElementById('feature');

  if (featureEv && featureEl) {
    const scheduleHtml = (featureEv.schedule || [])
      .map(item => `<li><time>${item.time}</time> ${item.text}</li>`)
      .join('');

    featureEl.innerHTML = `
      <div class="feature-image">
        <img src="${featureEv.image}" alt="${featureEv.title}">
        <span>${featureEv.badgeDate}</span>
      </div>
      <div class="feature-copy">
        <div class="eyebrow">${featureEv.eyebrow}</div>
        <h2>${featureEv.title}<span class="accent">.</span></h2>
        <p>${featureEv.desc}</p>
        <ul>${scheduleHtml}</ul>
        <button type="button" class="button button-dark" data-event-id="${featureEv.id}">
          Записаться и выбрать билет ↗
        </button>
        <small>${featureEv.note}</small>
      </div>
    `;
  }

  // 4. Рендер секции "Площадки"
  const venueGridEl = document.getElementById('venueGrid');
  if (venueGridEl) {
    venueGridEl.innerHTML = DATABASE.venues.map(v => `
      <article class="venue-card" data-venue-id="${v.id}">
        <img src="${v.image}" alt="${v.title}">
        <div>
          <span>${v.code}</span>
          <h3>${v.title}</h3>
          <p>${v.address}</p>
          <b>${v.countLabel}</b>
        </div>
      </article>
    `).join('');
  }
}

function openEventModalById(eventId) {
  const dbEvent = getEventById(eventId);
  if (!dbEvent) return;

  const eventData = {
    id: dbEvent.id,
    title: dbEvent.title,
    date: dbEvent.dateLabel || dbEvent.time,
    place: dbEvent.place,
    price: dbEvent.isFree ? 'Бесплатно' : dbEvent.price,
    tag: dbEvent.tag || 'СОБЫТИЕ',
    thumb: dbEvent.thumb || 'АФИША',
    desc: dbEvent.desc || ''
  };

  currentModalEvent = eventData;
  trackViewedEvent(eventData);

  document.getElementById('modalTag').textContent = eventData.tag;
  document.getElementById('modalTitle').textContent = eventData.title;
  document.getElementById('modalMeta').textContent = `${eventData.date} · ${eventData.place}`;
  document.getElementById('modalDesc').textContent = eventData.desc;
  document.getElementById('modalPrice').textContent = eventData.price;
  document.getElementById('modalFeedback').textContent = '';

  const isBooked = state.bookings.some(b => b.id === eventData.id);
  document.getElementById('modalBookBtn').textContent = isBooked
    ? 'Вы уже записаны ✓'
    : 'Записаться на мероприятие ↗';

  const isSaved = state.saved.some(s => s.id === eventData.id);
  document.getElementById('modalSaveBtn').textContent = isSaved
    ? 'В избранном ★'
    : 'В избранное';

  eventModal.classList.remove('hidden');
}

function closeEventModal() {
  eventModal.classList.add('hidden');
  currentModalEvent = null;
}

// Единый обработчик клика по любому объявлению (делегирование)
document.getElementById('mainView').addEventListener('click', e => {
  const eventTrigger = e.target.closest('[data-event-id]');
  if (eventTrigger) {
    openEventModalById(eventTrigger.dataset.eventId);
  }
});

const STORAGE_KEY = 'vne_afishi_user_state_v1';

const defaultState = {
  isLoggedIn: true,
  user: {
    name: 'Анна Ковалёва',
    email: 'anna.k@mail.ru',
    phone: '+7 (912) 450-18-90',
    district: 'Центральный район',
    alerts: {
      weekly: true,
      reminder: true,
      nearby: false
    }
  },
  bookings: [
    {
      id: 'wk-jazz',
      title: 'Летний джаз на набережной',
      date: 'Пт 12 июня · 20:00',
      place: 'Летняя сцена у моста · 2 билета, ряд 6',
      price: 'от 1 400 ₽',
      thumb: 'JAZZ',
      status: 'Оплачено',
      statusClass: 'paid'
    },
    {
      id: 'wk-sisters',
      title: '«Три сестры». Премьера сезона',
      date: 'Сб 13 июня · 19:00',
      place: 'Театр на набережной · 2 билета, партер',
      price: 'от 1 800 ₽',
      thumb: 'ТРИ СЕСТРЫ',
      status: 'Ожидает оплаты',
      statusClass: 'pending'
    },
    {
      id: 'feat-roof',
      title: 'Ночь короткого метра на крыше «Северная»',
      date: 'Сб 13 июня · 20:30',
      place: 'Крыша «Северная» · 1 билет',
      price: '1 200 ₽',
      thumb: 'КИНО',
      status: 'Оплачено',
      statusClass: 'paid'
    }
  ],
  viewed: [
    {
      id: 'wk-art',
      title: 'Выставка «Город после дождя»',
      date: '12–14 июня · 11:00–21:00',
      place: 'Галерея «Свет» · ул. Тихая, 7',
      price: 'от 600 ₽',
      thumb: 'ART'
    },
    {
      id: 'today-1',
      title: 'Экскурсия «Крыши и дворы»',
      date: 'Пт 12 июня · 18:30',
      place: 'Дом наций · Центральный район',
      price: 'от 900 ₽',
      thumb: 'КРЫШИ'
    }
  ],
  saved: [
    {
      id: 'wk-art',
      title: 'Выставка «Город после дождя»',
      date: '12–14 июня · 11:00–21:00',
      place: 'Галерея «Свет» · ул. Тихая, 7',
      price: 'от 600 ₽',
      thumb: 'ART'
    },
    {
      id: 'wk-food',
      title: 'Фестиваль уличной еды',
      date: 'Вс 14 июня · 12:00',
      place: 'Старый рынок',
      price: 'Бесплатно',
      thumb: 'FOOD'
    }
  ]
};

function loadState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return structuredClone(defaultState);
    return { ...structuredClone(defaultState), ...JSON.parse(raw) };
  } catch {
    return structuredClone(defaultState);
  }
}

let state = loadState();
let currentModalEvent = null;

function saveState() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    // Игнорируем ошибку квоты хранилища в приватном режиме
  }
}

function getInitials(fullName) {
  const parts = (fullName || '').trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return 'ВН';
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[1][0]).toUpperCase();
}
document.getElementById('accountDropdownMenu').addEventListener('click', e => {
  const jumpBtn = e.target.closest('[data-account-jump]');
  if (jumpBtn) {
    const targetTab = jumpBtn.dataset.accountJump;
    if (document.activeElement instanceof HTMLElement) {
      document.activeElement.blur();
    }
    openAccountView(targetTab);
    return;
  }

  if (e.target.closest('#dropdownLogoutBtn')) {
    if (document.activeElement instanceof HTMLElement) {
      document.activeElement.blur();
    }
    state.isLoggedIn = false;
    saveState();
    renderAccount();
    openAccountView('bookings', 'login');
  }
});
// ==========================================
// НАВИГАЦИЯ МЕЖДУ ГЛАВНОЙ И ЛИЧНЫМ КАБИНЕТОМ
// ==========================================
const mainView = document.getElementById('mainView');
const accountView = document.getElementById('accountView');
const headerBackBtn = document.getElementById('headerBackBtn');

function openAccountView(tabName = 'bookings', authMode = 'login') {
  mainView.classList.add('hidden');
  accountView.classList.remove('hidden');
  headerBackBtn.classList.remove('hidden');
  window.scrollTo({ top: 0, behavior: 'smooth' });

  if (!state.isLoggedIn) {
    switchAuthTab(authMode);
  } else {
    switchAccountTab(tabName);
  }
  renderAccount();
}

function openHomeView(sectionId = null) {
  accountView.classList.add('hidden');
  mainView.classList.remove('hidden');
  headerBackBtn.classList.add('hidden');

  if (sectionId) {
    const target = document.getElementById(sectionId);
    if (target) {
      target.scrollIntoView({ behavior: 'smooth' });
      return;
    }
  }
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

document.getElementById('headerAccountBtn').addEventListener('click', () => openAccountView('bookings'));
document.getElementById('heroAccountBtn').addEventListener('click', () => openAccountView('bookings'));
document.getElementById('headerBackBtn').addEventListener('click', () => openHomeView());
document.getElementById('accountBackBtn').addEventListener('click', () => openHomeView());
document.getElementById('addMoreFromAccountBtn').addEventListener('click', () => openHomeView('weekend'));

document.querySelectorAll('[data-go-home]').forEach(el => {
  el.addEventListener('click', e => {
    e.preventDefault();
    openHomeView();
  });
});

document.querySelectorAll('[data-nav-section]').forEach(el => {
  el.addEventListener('click', e => {
    e.preventDefault();
    const section = el.dataset.navSection;
    openHomeView(section);
  });
});

document.querySelectorAll('[data-open-account]').forEach(el => {
  el.addEventListener('click', e => {
    e.preventDefault();
    openAccountView('bookings');
  });
});

// ==========================================
// ОТРИСОВКА ШАПКИ И ЛИЧНОГО КАБИНЕТА
// ==========================================
function renderHeader() {
  const avatar = document.getElementById('headerAvatar');
  const label = document.getElementById('headerAccountLabel');
  const badge = document.getElementById('headerBookingsCount');
  const heroBtn = document.getElementById('heroAccountBtn');
  const dropdownMenu = document.getElementById('accountDropdownMenu');

  if (state.isLoggedIn) {
    avatar.textContent = getInitials(state.user.name);
    label.textContent = 'Кабинет';
    badge.textContent = state.bookings.length;
    badge.classList.remove('hidden');
    heroBtn.textContent = 'Мой кабинет';
    dropdownMenu.classList.remove('hidden');
  } else {
    avatar.textContent = '→';
    label.textContent = 'Войти / Регистрация';
    badge.classList.add('hidden');
    heroBtn.textContent = 'Войти в кабинет';
    dropdownMenu.classList.add('hidden');
  }
}

function renderAccount() {
  renderHeader();

  const authBox = document.getElementById('authBox');
  const dashboardBox = document.getElementById('dashboardBox');

  if (!state.isLoggedIn) {
    authBox.classList.remove('hidden');
    dashboardBox.classList.add('hidden');
    return;
  }

  authBox.classList.add('hidden');
  dashboardBox.classList.remove('hidden');

  // Карточка профиля
  document.getElementById('profileAvatar').textContent = getInitials(state.user.name);
  document.getElementById('profileName').textContent = state.user.name;
  document.getElementById('profileEmail').textContent = state.user.email;
  document.getElementById('profileDistrict').textContent = state.user.district || 'Город не указан';
  document.getElementById('sideBookingsCount').textContent = state.bookings.length;
  document.getElementById('sideViewedCount').textContent = state.viewed.length;

  // Заполнение формы редактирования
  document.getElementById('editName').value = state.user.name;
  document.getElementById('editEmail').value = state.user.email;
  document.getElementById('editPhone').value = state.user.phone || '';
  document.getElementById('editDistrict').value = state.user.district || '';
  document.getElementById('alertWeekly').checked = Boolean(state.user.alerts.weekly);
  document.getElementById('alertReminder').checked = Boolean(state.user.alerts.reminder);
  document.getElementById('alertNearby').checked = Boolean(state.user.alerts.nearby);

  // Список записей
  const bookingsList = document.getElementById('bookingsList');
  if (!state.bookings.length) {
    bookingsList.innerHTML = '<p class="empty-tab-msg">Вы пока не записались ни на одно мероприятие. Откройте любую карточку в афише, чтобы записаться.</p>';
  } else {
    bookingsList.innerHTML = state.bookings.map(item => `
      <article class="ticket">
        <div class="ticket-thumb">${item.thumb || 'СОБЫТИЕ'}</div>
        <div>
          <h3>${item.title}</h3>
          <p>${item.date} · ${item.place}</p>
        </div>
        <div class="ticket-actions">
          <span class="status ${item.statusClass || 'paid'}">${item.status || 'Записан'}</span>
          <button type="button" class="mini-action-btn" data-cancel-booking="${item.id}">Отменить</button>
        </div>
      </article>
    `).join('');
  }

  // Список просмотренных
  const viewedList = document.getElementById('viewedList');
  if (!state.viewed.length) {
    viewedList.innerHTML = '<p class="empty-tab-msg">История просмотров пуста. Нажмите на любое событие на главной странице, чтобы изучить детали.</p>';
  } else {
    viewedList.innerHTML = state.viewed.map(item => {
      const alreadyBooked = state.bookings.some(b => b.id === item.id);
      return `
        <article class="ticket">
          <div class="ticket-thumb">${item.thumb || 'АФИША'}</div>
          <div>
            <h3>${item.title}</h3>
            <p>${item.date} · ${item.place} · ${item.price}</p>
          </div>
          <div class="ticket-actions">
            ${alreadyBooked
              ? '<span class="status paid">Вы записаны</span>'
              : `<button type="button" class="mini-action-btn" data-book-from-history="${item.id}">Записаться</button>`}
          </div>
        </article>
      `;
    }).join('');
  }

  // Список избранного
  const savedList = document.getElementById('savedList');
  if (!state.saved.length) {
    savedList.innerHTML = '<p class="empty-tab-msg">В избранном пока пусто.</p>';
  } else {
    savedList.innerHTML = state.saved.map(item => `
      <article class="ticket">
        <div class="ticket-thumb">${item.thumb || 'SAVE'}</div>
        <div>
          <h3>${item.title}</h3>
          <p>${item.date} · ${item.place} · ${item.price}</p>
        </div>
        <div class="ticket-actions">
          <button type="button" class="mini-action-btn" data-book-from-saved="${item.id}">Записаться</button>
          <button type="button" class="mini-action-btn" data-remove-saved="${item.id}">Убрать</button>
        </div>
      </article>
    `).join('');
  }
}

// Вкладки внутри кабинета
function switchAccountTab(tabId) {
  document.querySelectorAll('.account-tabs button').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.tab === tabId);
  });
  document.querySelectorAll('.tab-panel').forEach(panel => {
    panel.classList.toggle('hidden', panel.id !== tabId);
  });
}

document.querySelectorAll('.account-tabs button').forEach(btn => {
  btn.addEventListener('click', () => switchAccountTab(btn.dataset.tab));
});

document.querySelectorAll('[data-switch-tab]').forEach(btn => {
  btn.addEventListener('click', () => switchAccountTab(btn.dataset.switchTab));
});

// Действия в списках кабинета (делегирование)
document.getElementById('accountView').addEventListener('click', e => {
  const cancelId = e.target.dataset.cancelBooking;
  if (cancelId) {
    state.bookings = state.bookings.filter(b => b.id !== cancelId);
    saveState();
    renderAccount();
    return;
  }

  const bookHistId = e.target.dataset.bookFromHistory;
  if (bookHistId) {
    const found = state.viewed.find(v => v.id === bookHistId);
    if (found) addBooking(found);
    renderAccount();
    return;
  }

  const bookSavedId = e.target.dataset.bookFromSaved;
  if (bookSavedId) {
    const found = state.saved.find(s => s.id === bookSavedId);
    if (found) addBooking(found);
    renderAccount();
    return;
  }

  const removeSavedId = e.target.dataset.removeSaved;
  if (removeSavedId) {
    state.saved = state.saved.filter(s => s.id !== removeSavedId);
    saveState();
    renderAccount();
  }
});

document.getElementById('clearViewedBtn').addEventListener('click', () => {
  state.viewed = [];
  saveState();
  renderAccount();
});

// ==========================================
// АВТОРИЗАЦИЯ, РЕГИСТРАЦИЯ И РЕДАКТИРОВАНИЕ
// ==========================================
function switchAuthTab(mode) {
  document.querySelectorAll('[data-auth-tab]').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.authTab === mode);
  });
  document.getElementById('loginForm').classList.toggle('hidden', mode !== 'login');
  document.getElementById('registerForm').classList.toggle('hidden', mode !== 'register');
}

document.querySelectorAll('[data-auth-tab]').forEach(btn => {
  btn.addEventListener('click', () => switchAuthTab(btn.dataset.authTab));
});

document.getElementById('loginForm').addEventListener('submit', e => {
  e.preventDefault();
  const email = document.getElementById('loginEmail').value.trim();
  if (email) {
    state.user.email = email;
    if (!state.user.name) state.user.name = email.split('@')[0];
  }
  state.isLoggedIn = true;
  saveState();
  renderAccount();
});

document.getElementById('demoLoginBtn').addEventListener('click', () => {
  state = structuredClone(defaultState);
  state.isLoggedIn = true;
  saveState();
  renderAccount();
});

document.getElementById('registerForm').addEventListener('submit', e => {
  e.preventDefault();
  const name = document.getElementById('regName').value.trim();
  const email = document.getElementById('regEmail').value.trim();
  const district = document.getElementById('regDistrict').value.trim();

  state.user = {
    name: name || 'Новый участник',
    email: email || 'user@mail.ru',
    phone: '',
    district: district || 'Центральный район',
    alerts: { weekly: true, reminder: true, nearby: false }
  };
  state.isLoggedIn = true;
  saveState();
  renderAccount();
});

document.getElementById('logoutBtn').addEventListener('click', () => {
  state.isLoggedIn = false;
  saveState();
  renderAccount();
});

document.getElementById('profileEditForm').addEventListener('submit', e => {
  e.preventDefault();
  state.user.name = document.getElementById('editName').value.trim() || state.user.name;
  state.user.email = document.getElementById('editEmail').value.trim() || state.user.email;
  state.user.phone = document.getElementById('editPhone').value.trim();
  state.user.district = document.getElementById('editDistrict').value.trim();
  state.user.alerts = {
    weekly: document.getElementById('alertWeekly').checked,
    reminder: document.getElementById('alertReminder').checked,
    nearby: document.getElementById('alertNearby').checked
  };
  saveState();
  renderAccount();

  const status = document.getElementById('profileSaveStatus');
  status.textContent = '✓ Изменения сохранены';
  setTimeout(() => {
    status.textContent = '';
  }, 2500);
});

// ==========================================
// КАРТОЧКА СОБЫТИЯ, ПРОСМОТРЫ И ЗАПИСЬ
// ==========================================
const eventModal = document.getElementById('eventModal');

function trackViewedEvent(eventData) {
  state.viewed = [
    eventData,
    ...state.viewed.filter(item => item.id !== eventData.id)
  ].slice(0, 12);
  saveState();
  renderHeader();
}

function addBooking(eventData) {
  if (state.bookings.some(b => b.id === eventData.id)) return false;
  state.bookings.unshift({
    ...eventData,
    status: eventData.price === 'Бесплатно' ? 'Запись подтверждена' : 'Забронировано',
    statusClass: 'paid'
  });
  saveState();
  renderHeader();
  return true;
}

// ==========================================
// ДИНАМИЧЕСКИЙ РЕНДЕР ВСЕХ СЕКЦИЙ ИЗ БД
// ==========================================
function renderCatalogFromDB() {
  // 1. Рендер секции "Сегодня"
  const todayEvents = DATABASE.events.filter(ev => ev.section === 'today');
  const todayListEl = document.getElementById('todayList');
  const todayCountBadge = document.getElementById('todayCountBadge');

  if (todayCountBadge) {
    todayCountBadge.textContent = String(todayEvents.length).padStart(2, '0');
  }

  if (todayListEl) {
    todayListEl.innerHTML = todayEvents.map(ev => `
      <article class="today-event" data-event-id="${ev.id}">
        <time>${ev.time}</time>
        <div>
          <span class="tag ${ev.isFree ? 'free' : ''}">${ev.tag}</span>
          <h3>${ev.title}</h3>
          <p>${ev.place}</p>
        </div>
        <b>${ev.price}</b>
        <button type="button" class="event-open-btn" aria-label="Подробнее">↗</button>
      </article>
    `).join('');
  }

  // 2. Рендер секции "Выходные"
  const weekendEvents = DATABASE.events.filter(ev => ev.section === 'weekend');
  const eventGridEl = document.getElementById('eventGrid');

  if (eventGridEl) {
    eventGridEl.innerHTML = weekendEvents.map(ev => `
      <article class="event-card" data-event-id="${ev.id}" data-day="${ev.dayCode}" data-type="${ev.category}">
        <div class="event-visual ${ev.visualClass}">
          <span>${ev.visualDate}</span>
          <b>${(ev.visualTitle || ev.title).replace(/\n/g, '<br>')}</b>
        </div>
        <div class="event-info">
          <span class="tag ${ev.isFree ? 'free' : ''}">${ev.tag}</span>
          <h3>${ev.title}</h3>
          <p>${ev.place}</p>
          <b>${ev.price} <button type="button" class="event-open-btn" aria-label="Подробнее">↗</button></b>
        </div>
      </article>
    `).join('');
  }

  // 3. Рендер секции "Событие недели"
  const featureEv = DATABASE.events.find(ev => ev.section === 'feature');
  const featureEl = document.getElementById('feature');

  if (featureEv && featureEl) {
    const scheduleHtml = (featureEv.schedule || [])
      .map(item => `<li><time>${item.time}</time> ${item.text}</li>`)
      .join('');

    featureEl.innerHTML = `
      <div class="feature-image">
        <img src="${featureEv.image}" alt="${featureEv.title}">
        <span>${featureEv.badgeDate}</span>
      </div>
      <div class="feature-copy">
        <div class="eyebrow">${featureEv.eyebrow}</div>
        <h2>${featureEv.title}<span class="accent">.</span></h2>
        <p>${featureEv.desc}</p>
        <ul>${scheduleHtml}</ul>
        <button type="button" class="button button-dark" data-event-id="${featureEv.id}">
          Записаться и выбрать билет ↗
        </button>
        <small>${featureEv.note}</small>
      </div>
    `;
  }

  // 4. Рендер секции "Площадки"
  const venueGridEl = document.getElementById('venueGrid');
  if (venueGridEl) {
    venueGridEl.innerHTML = DATABASE.venues.map(v => `
      <article class="venue-card" data-venue-id="${v.id}">
        <img src="${v.image}" alt="${v.title}">
        <div>
          <span>${v.code}</span>
          <h3>${v.title}</h3>
          <p>${v.address}</p>
          <b>${v.countLabel}</b>
        </div>
      </article>
    `).join('');
  }
}

function openEventModalById(eventId) {
  const dbEvent = getEventById(eventId);
  if (!dbEvent) return;

  const eventData = {
    id: dbEvent.id,
    title: dbEvent.title,
    date: dbEvent.dateLabel || dbEvent.time,
    place: dbEvent.place,
    price: dbEvent.isFree ? 'Бесплатно' : dbEvent.price,
    tag: dbEvent.tag || 'СОБЫТИЕ',
    thumb: dbEvent.thumb || 'АФИША',
    desc: dbEvent.desc || ''
  };

  currentModalEvent = eventData;
  trackViewedEvent(eventData);

  document.getElementById('modalTag').textContent = eventData.tag;
  document.getElementById('modalTitle').textContent = eventData.title;
  document.getElementById('modalMeta').textContent = `${eventData.date} · ${eventData.place}`;
  document.getElementById('modalDesc').textContent = eventData.desc;
  document.getElementById('modalPrice').textContent = eventData.price;
  document.getElementById('modalFeedback').textContent = '';

  const isBooked = state.bookings.some(b => b.id === eventData.id);
  document.getElementById('modalBookBtn').textContent = isBooked
    ? 'Вы уже записаны ✓'
    : 'Записаться на мероприятие ↗';

  const isSaved = state.saved.some(s => s.id === eventData.id);
  document.getElementById('modalSaveBtn').textContent = isSaved
    ? 'В избранном ★'
    : 'В избранное';

  eventModal.classList.remove('hidden');
}

function closeEventModal() {
  eventModal.classList.add('hidden');
  currentModalEvent = null;
}

// Единый обработчик клика по любому объявлению (делегирование)
document.getElementById('mainView').addEventListener('click', e => {
  const eventTrigger = e.target.closest('[data-event-id]');
  if (eventTrigger) {
    openEventModalById(eventTrigger.dataset.eventId);
  }
});

document.getElementById('modalCloseBtn').addEventListener('click', closeEventModal);
eventModal.addEventListener('click', e => {
  if (e.target === eventModal) closeEventModal();
});

document.getElementById('modalBookBtn').addEventListener('click', () => {
  if (!currentModalEvent) return;
  if (!state.isLoggedIn) {
    const pendingEvent = currentModalEvent;
    closeEventModal();
    openAccountView('bookings', 'login');
    document.getElementById('loginEmail').focus();
    addBooking(pendingEvent);
    return;
  }

  const added = addBooking(currentModalEvent);
  document.getElementById('modalBookBtn').textContent = 'Вы уже записаны ✓';
  document.getElementById('modalFeedback').textContent = added
    ? 'Мероприятие добавлено в «Мои записи» в личном кабинете.'
    : 'Это событие уже есть в ваших записях.';
});

document.getElementById('modalSaveBtn').addEventListener('click', () => {
  if (!currentModalEvent) return;
  const exists = state.saved.some(s => s.id === currentModalEvent.id);
  if (exists) {
    state.saved = state.saved.filter(s => s.id !== currentModalEvent.id);
    document.getElementById('modalSaveBtn').textContent = 'В избранное';
    document.getElementById('modalFeedback').textContent = 'Убрано из избранного.';
  } else {
    state.saved.unshift(currentModalEvent);
    document.getElementById('modalSaveBtn').textContent = 'В избранном ★';
    document.getElementById('modalFeedback').textContent = 'Сохранено в избранное.';
  }
  saveState();
});

// ==========================================
// ФИЛЬТРЫ АФИШИ, МОБИЛЬНОЕ МЕНЮ И ИИ-АГЕНТЫ
// ==========================================
const dayButtons = [...document.querySelectorAll('[data-day]')].filter(x => x.classList.contains('chip'));
const typeButtons = [...document.querySelectorAll('[data-type]')].filter(x => x.classList.contains('chip'));
let selectedDay = 'all';
let selectedType = 'all';

function filterEvents() {
  let shown = 0;
  document.querySelectorAll('.event-card').forEach(card => {
    const dayMatch = selectedDay === 'all' || card.dataset.day === 'all' || card.dataset.day === selectedDay;
    const typeMatch = selectedType === 'all' || card.dataset.type === selectedType;
    card.style.display = dayMatch && typeMatch ? '' : 'none';
    if (dayMatch && typeMatch) shown++;
  });
  document.getElementById('resultCount').textContent = shown;
  document.getElementById('emptyState').style.display = shown ? 'none' : 'block';
}

dayButtons.forEach(btn => btn.addEventListener('click', () => {
  selectedDay = btn.dataset.day;
  dayButtons.forEach(b => b.classList.toggle('active', b === btn));
  filterEvents();
}));

typeButtons.forEach(btn => btn.addEventListener('click', () => {
  selectedType = btn.dataset.type;
  typeButtons.forEach(b => b.classList.toggle('active', b === btn));
  filterEvents();
}));

document.querySelector('.menu-toggle').addEventListener('click', () => {
  document.querySelector('.main-nav').classList.toggle('open');
});

document.querySelectorAll('.main-nav a').forEach(a => {
  a.addEventListener('click', () => document.querySelector('.main-nav').classList.remove('open'));
});

const agentReplies = {
  curator: 'Могу подобрать события под ваше настроение. Например, выставка «Город после дождя» в галерее «Свет» — спокойный вариант на субботу.',
  route: 'Предлагаю начать с выставки в галерее «Свет», затем прогуляться до набережной. Вечером можно закончить маршрут джазовым концертом.',
  ticket: 'На летний джаз есть варианты от 1 400 ₽. Нажмите на карточку события, чтобы записаться в один клик.'
};
const agentNames = { curator: 'Куратор', route: 'Маршрутовед', ticket: 'Билетный' };

document.querySelectorAll('.agent-choice').forEach(choice => choice.addEventListener('click', () => {
  document.querySelectorAll('.agent-choice').forEach(c => c.classList.toggle('active', c === choice));
  const key = choice.dataset.agent;
  document.getElementById('agentName').textContent = agentNames[key];
  const messages = document.getElementById('messages');
  messages.innerHTML = `<div class="message bot-message">${agentReplies[key]}<time>СЕЙЧАС</time></div>`;
}));

document.getElementById('chatForm').addEventListener('submit', e => {
  e.preventDefault();
  const input = document.getElementById('chatInput');
  const value = input.value.trim();
  if (!value) return;

  const messages = document.getElementById('messages');
  const user = document.createElement('div');
  user.className = 'message user-message';
  user.textContent = value;
  messages.append(user);
  input.value = '';

  const reply = document.createElement('div');
  reply.className = 'message bot-message';
  reply.textContent = 'Понял вас! Загляните в афишу выходных и нажмите на любую карточку — событие сразу сохранится в истории просмотров в вашем кабинете.';
  messages.append(reply);
  messages.scrollTop = messages.scrollHeight;
});

document.getElementById('subscribeForm').addEventListener('submit', e => {
  e.preventDefault();
  document.getElementById('subscribeMessage').textContent = 'Спасибо! Вы подписаны на пятничную подборку.';
});

// Инициализация при загрузке
renderHeader();
// Инициализация при загрузке
renderCatalogFromDB();
filterEvents();
renderHeader();