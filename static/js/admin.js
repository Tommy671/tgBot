// Telegram CRM Admin Panel JavaScript
// Version: 6.4 - Fixed Dashboard Users Table Update

// Глобальные переменные
let authToken = localStorage.getItem('authToken');
window.allUsers = []; // Храним всех пользователей для фильтрации
window.filteredUsers = []; // Отфильтрованные пользователи

// Функции для работы с API
async function apiRequest(endpoint, options = {}) {
    const baseUrl = window.location.origin;
    const url = `${baseUrl}${endpoint}`;
    
    const defaultOptions = {
        headers: {
            'Content-Type': 'application/json',
        },
    };
    
    if (authToken) {
        defaultOptions.headers['Authorization'] = `Bearer ${authToken}`;
    }
    
    const finalOptions = {
        ...defaultOptions,
        ...options,
        headers: {
            ...defaultOptions.headers,
            ...options.headers,
        },
    };
    
    try {
        const response = await fetch(url, finalOptions);
        
        if (response.status === 401) {
            // Токен истек или недействителен - временно убираем перенаправление
            // localStorage.removeItem('authToken');
            // window.location.href = '/login';
            // return;
            console.warn('Unauthorized access, but continuing for debugging');
        }
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        return await response.json();
    } catch (error) {
        console.error('API request failed:', error);
        throw error;
    }
}

// Аутентификация
async function login(username, password) {
    try {
        const response = await apiRequest('/api/login', {
            method: 'POST',
            body: JSON.stringify({ username, password }),
        });
        
        authToken = response.access_token;
        localStorage.setItem('authToken', authToken);
        return true;
    } catch (error) {
        console.error('Login failed:', error);
        return false;
    }
}

// Получение статистики дашборда
async function getDashboardStats() {
    try {
        console.log('Fetching dashboard stats...');
        const stats = await apiRequest('/api/dashboard');
        console.log('Dashboard stats received:', stats);
        console.log('Stats type:', typeof stats);
        console.log('Stats keys:', Object.keys(stats));
        
        // Обновляем UI дашборда через функцию updateDashboardUI
        updateDashboardUI(stats);
        
    } catch (error) {
        console.error('Failed to get dashboard stats:', error);
        // Показываем сообщение об ошибке на странице
        const totalUsersEl = document.getElementById('total-users');
        const activeSubscriptionsEl = document.getElementById('active-subscriptions');
        const newUsersTodayEl = document.getElementById('new-users-today');
        const expiringSubscriptionsEl = document.getElementById('expiring-subscriptions');
        
        if (totalUsersEl) totalUsersEl.textContent = 'Ошибка';
        if (activeSubscriptionsEl) activeSubscriptionsEl.textContent = 'Ошибка';
        if (newUsersTodayEl) newUsersTodayEl.textContent = 'Ошибка';
        if (expiringSubscriptionsEl) expiringSubscriptionsEl.textContent = 'Ошибка';
        
        // Показываем уведомление об ошибке
        showAlert('Ошибка загрузки статистики. Возможно, требуется авторизация.', 'warning');
    }
}

// Функция для обновления дашборда (вызывается кнопкой "Обновить статистику")
async function loadDashboardData() {
    try {
        // Обновляем статистику дашборда
        await getDashboardStats();
        
        // Если мы на дашборде, обновляем таблицу пользователей
        if (window.location.pathname === '/' && typeof loadUsers === 'function') {
            await loadUsers();
        }
        // Если мы на странице пользователей, обновляем полный список
        else if (window.location.pathname === '/users' && typeof getUsers === 'function') {
            await getUsers();
        }
        
        showAlert('Список пользователей обновлен', 'success');
    } catch (error) {
        console.error('Failed to refresh dashboard data:', error);
        showAlert('Ошибка обновления данных', 'error');
    }
}

// Обновление UI дашборда
function updateDashboardUI(stats) {
    console.log('🔄 updateDashboardUI called with stats:', stats);
    
    // Элементы для статистики бесплатного канала
    const totalFreeChannelEl = document.getElementById('total-free-channel-count');
    const activeUsersEl = document.getElementById('active-users-count');
    const newUsersWeekEl = document.getElementById('new-users-week');
    const newUsersTodayEl = document.getElementById('new-users-today');
    
    // Элементы для статистики платного чата
    const usersWithSubscriptionEl = document.getElementById('users-with-subscription-count');
    const newPaidWeekEl = document.getElementById('new-paid-week');
    const newPaidTodayEl = document.getElementById('new-paid-today');
    
    console.log('🔍 Dashboard elements found:');
    console.log('   - total-free-channel-count:', totalFreeChannelEl ? '✅' : '❌');
    console.log('   - active-users-count:', activeUsersEl ? '✅' : '❌');
    console.log('   - new-users-week:', newUsersWeekEl ? '✅' : '❌');
    console.log('   - new-users-today:', newUsersTodayEl ? '✅' : '❌');
    console.log('   - users-with-subscription-count:', usersWithSubscriptionEl ? '✅' : '❌');
    console.log('   - new-paid-week:', newPaidWeekEl ? '✅' : '❌');
    console.log('   - new-paid-today:', newPaidTodayEl ? '✅' : '❌');
    
    // Обновляем статистику бесплатного канала
    if (totalFreeChannelEl) {
        totalFreeChannelEl.textContent = stats.total_free_channel_users || 0;
        console.log('✅ Updated total-free-channel-count to:', stats.total_free_channel_users || 0);
    } else {
        console.warn('⚠️ Element total-free-channel-count not found!');
    }
    
    if (activeUsersEl) {
        activeUsersEl.textContent = stats.active_users || 0;
        console.log('✅ Updated active-users-count to:', stats.active_users || 0);
    } else {
        console.warn('⚠️ Element active-users-count not found!');
    }
    
    if (newUsersWeekEl) {
        newUsersWeekEl.textContent = stats.new_users_week || 0;
        console.log('✅ Updated new-users-week to:', stats.new_users_week || 0);
    } else {
        console.warn('⚠️ Element new-users-week not found!');
    }
    
    if (newUsersTodayEl) {
        newUsersTodayEl.textContent = stats.new_users_today || 0;
        console.log('✅ Updated new-users-today to:', stats.new_users_today || 0);
    } else {
        console.warn('⚠️ Element new-users-today not found!');
    }
    
    // Обновляем статистику платного чата
    if (usersWithSubscriptionEl) {
        usersWithSubscriptionEl.textContent = stats.users_with_subscription || 0;
        console.log('✅ Updated users-with-subscription-count to:', stats.users_with_subscription || 0);
    } else {
        console.warn('⚠️ Element users-with-subscription-count not found!');
    }
    
    if (newPaidWeekEl) {
        newPaidWeekEl.textContent = stats.new_paid_week || 0;
        console.log('✅ Updated new-paid-week to:', stats.new_paid_week || 0);
    } else {
        console.warn('⚠️ Element new-paid-week not found!');
    }
    
    if (newPaidTodayEl) {
        newPaidTodayEl.textContent = stats.new_paid_today || 0;
        console.log('✅ Updated new-paid-today to:', stats.new_paid_today || 0);
    } else {
        console.warn('⚠️ Element new-paid-today not found!');
    }
    
    console.log('🎉 Dashboard UI update completed!');
    
    // Загружаем последних пользователей для отображения на дашборде
    loadRecentUsers();
}

// Обновление статистики в разделе пользователей
function updateUsersStats(usersData) {
    const totalFreeChannelEl = document.getElementById('total-free-channel-count');
    const activeUsersCountEl = document.getElementById('active-users-count');
    const usersWithSubscriptionEl = document.getElementById('users-with-subscription-count');
    const newUsersCountEl = document.getElementById('new-users-count');
    
    if (totalFreeChannelEl) totalFreeChannelEl.textContent = usersData.total_free_channel || 0;
    
    // Подсчитываем активных пользователей по полю is_active
    const users = usersData.users || [];
    const activeCount = users.filter(user => user.is_active === true).length;
    if (activeUsersCountEl) activeUsersCountEl.textContent = activeCount;
    
    // Подсчитываем пользователей с подпиской
    const subscribedCount = users.filter(user => 
        user.subscription_status && user.subscription_status !== 'Нет подписки'
    ).length;
    
    if (usersWithSubscriptionEl) usersWithSubscriptionEl.textContent = subscribedCount;
    
    // Подсчитываем новых пользователей за сегодня
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const newUsersCount = users.filter(user => {
        if (!user.registration_date) return false;
        const registrationDate = new Date(user.registration_date);
        registrationDate.setHours(0, 0, 0, 0);
        return registrationDate.getTime() === today.getTime();
    }).length;
    
    if (newUsersCountEl) newUsersCountEl.textContent = newUsersCount;
    
    console.log('Users stats updated:', {
        total_free_channel: usersData.total_free_channel,
        active: activeCount,
        subscribed: subscribedCount,
        newToday: newUsersCount
    });
}

// Загрузка последних пользователей для дашборда
async function loadRecentUsers() {
    try {
        const users = await apiRequest('/api/users?skip=0&limit=5');
        updateRecentUsersTable(users);
    } catch (error) {
        console.error('Failed to load recent users:', error);
        // Показываем сообщение об ошибке в таблице
        const tbody = document.querySelector('#recent-users-table tbody');
        if (tbody) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="6" class="text-center text-danger">
                        <i class="fas fa-exclamation-triangle me-2"></i>
                        Ошибка загрузки данных
                    </td>
                </tr>
            `;
        }
    }
}

// Обновление таблицы последних пользователей на дашборде
function updateRecentUsersTable(usersData) {
    const tbody = document.querySelector('#recent-users-table tbody');
    if (!tbody) return;
    
    tbody.innerHTML = '';
    
    const users = usersData.users || [];
    
    if (users.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="6" class="text-center text-muted">
                    Нет пользователей
                </td>
            </tr>
        `;
        return;
    }
    
    users.forEach(user => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${user.id}</td>
            <td>${user.full_name || 'Не указано'}</td>
            <td>@${user.username || 'Нет'}</td>
            <td>${user.registration_date ? new Date(user.registration_date).toLocaleDateString('ru-RU') : 'Не указано'}</td>
            <td>
                <span class="badge ${user.subscription_status && user.subscription_status !== 'Нет подписки' ? 'bg-success' : 'bg-secondary'}">
                    ${user.subscription_status || 'Нет'}
                </span>
            </td>
        `;
        tbody.appendChild(row);
    });
}

// Получение списка пользователей
async function getUsers(search = '', page = 0, limit = 20) {
    try {
        console.log('Fetching users...');
        const params = new URLSearchParams({
            skip: 0, // Всегда загружаем всех пользователей для фильтрации
            limit: 1000, // Большой лимит для получения всех пользователей
        });
        
        const users = await apiRequest(`/api/users?${params}`);
        console.log('Users received:', users);
        
        // Сохраняем всех пользователей в глобальную переменную
        window.allUsers = users.users || [];
        console.log('All users saved:', window.allUsers);
        
        // Применяем фильтры и поиск
        applyFiltersAndSearch();
    } catch (error) {
        console.error('Failed to get users:', error);
    }
}

// Применение фильтров и поиска
function applyFiltersAndSearch() {
    let filtered = [...allUsers];
    
    // Получаем значения фильтров
    const searchTerm = document.getElementById('search-input')?.value?.toLowerCase() || '';
    const statusFilter = document.getElementById('status-filter')?.value || '';
    const sortFilter = document.getElementById('sort-filter')?.value || '';
    
    // Применяем поиск
    if (searchTerm) {
        filtered = filtered.filter(user => {
            const name = (user.full_name || '').toLowerCase();
            const username = (user.username || '').toLowerCase();
            const phone = (user.contact_number || '').toLowerCase();
            const company = (user.company || '').toLowerCase();
            
            return name.includes(searchTerm) || 
                   username.includes(searchTerm) || 
                   phone.includes(searchTerm) || 
                   company.includes(searchTerm);
        });
    }
    
    // Применяем фильтр по статусу
    if (statusFilter) {
        switch (statusFilter) {
            case 'active':
                filtered = filtered.filter(user => user.is_active === true);
                break;
            case 'inactive':
                filtered = filtered.filter(user => user.is_active === false);
                break;
            case 'with_subscription':
                filtered = filtered.filter(user => user.subscription_status && user.subscription_status !== 'Нет подписки');
                break;
            case 'without_subscription':
                filtered = filtered.filter(user => !user.subscription_status || user.subscription_status === 'Нет подписки');
                break;
        }
    }
    
    // Применяем сортировку
    switch (sortFilter) {
        case 'registration_date_desc':
            filtered.sort((a, b) => new Date(b.registration_date || 0) - new Date(a.registration_date || 0));
            break;
        case 'registration_date_asc':
            filtered.sort((a, b) => new Date(a.registration_date || 0) - new Date(b.registration_date || 0));
            break;
        case 'last_activity_desc':
            filtered.sort((a, b) => new Date(b.last_activity || 0) - new Date(a.last_activity || 0));
            break;
        case 'name_asc':
            filtered.sort((a, b) => (a.full_name || '').localeCompare(b.full_name || '', 'ru'));
            break;
        case 'name_desc':
            filtered.sort((a, b) => (b.full_name || '').localeCompare(a.full_name || '', 'ru'));
            break;
    }
    
    // Сохраняем отфильтрованные данные в глобальную переменную
    window.filteredUsers = filtered;
    
    // Обновляем таблицу
    updateUsersTable({ users: filtered, total: filtered.length });
}

// Обновление списка пользователей
function refreshUsers() {
    getUsers();
    showAlert('Список пользователей обновлен', 'success');
}

// Выполнение экспорта (только Excel)
function performExport() {
    const fields = [];
    
    // Собираем выбранные поля
    if (document.getElementById('exportId').checked) fields.push('id');
    if (document.getElementById('exportName').checked) fields.push('full_name');
    if (document.getElementById('exportUsername').checked) fields.push('username');
    if (document.getElementById('exportPhone').checked) fields.push('contact_number');
    if (document.getElementById('exportCompany').checked) fields.push('company');
    if (document.getElementById('exportRegistration').checked) fields.push('registration_date');
    if (document.getElementById('exportSubscription').checked) fields.push('subscription_status');
    
    // Создаем данные для экспорта - используем allUsers если filteredUsers не определен
    const exportData = (window.filteredUsers && window.filteredUsers.length > 0) ? window.filteredUsers : window.allUsers;
    
    console.log('Export data:', exportData);
    console.log('All users:', window.allUsers);
    console.log('Filtered users:', window.filteredUsers);
    
    if (!exportData || exportData.length === 0) {
        showAlert('Нет данных для экспорта', 'warning');
        return;
    }
    
    // Экспортируем данные только в Excel
    exportToExcel(exportData, fields);
    
    // Закрываем модальное окно
    const exportModal = bootstrap.Modal.getInstance(document.getElementById('exportModal'));
    exportModal.hide();
    
    showAlert(`Экспортировано ${exportData.length} пользователей (Excel)`, 'success');
}

// Удален экспорт в CSV

// Экспорт в Excel (простой формат)
function exportToExcel(data, fields) {
    const headers = fields.map(field => {
        const fieldNames = {
            'id': 'ID',
            'full_name': 'ФИО',
            'username': 'Username',
            'contact_number': 'Телефон',
            'company': 'Компания',
            'registration_date': 'Дата регистрации',
            'subscription_status': 'Статус подписки'
        };
        return fieldNames[field] || field;
    });
    
    // Создаем HTML таблицу для Excel
    let html = '<table border="1">';
    html += '<tr>' + headers.map(h => `<th>${h}</th>`).join('') + '</tr>';
    
    data.forEach(user => {
        html += '<tr>';
        fields.forEach(field => {
            let value = user[field] || '';
            if (field === 'registration_date' && value) {
                value = new Date(value).toLocaleDateString('ru-RU');
            }
            html += `<td>${value}</td>`;
        });
        html += '</tr>';
    });
    
    html += '</table>';
    
    downloadFile(html, 'users.xls', 'application/vnd.ms-excel');
}

// Функция для скачивания файла
function downloadFile(content, filename, contentType) {
    const blob = new Blob([content], { type: contentType });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
}

// Обновление таблицы пользователей
function updateUsersTable(usersData) {
    console.log('updateUsersTable called with:', usersData);
    const tbody = document.querySelector('#users-table tbody');
    if (!tbody) {
        console.error('Table body not found');
        return;
    }
    
    tbody.innerHTML = '';
    
    // API возвращает объект с полем users, а не массив напрямую
    const users = usersData.users || usersData;
    console.log('Extracted users:', users);
    console.log('Users type:', typeof users);
    console.log('Is array:', Array.isArray(users));
    
    if (!Array.isArray(users)) {
        console.error('Users is not an array:', users);
        return;
    }
    
    // Обновляем статистику в разделе пользователей
    updateUsersStats(usersData);
    
    if (users.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="9" class="text-center text-muted">
                    <i class="fas fa-search me-2"></i>
                    Пользователи не найдены
                </td>
            </tr>
        `;
        return;
    }
    
    users.forEach(user => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${user.id}</td>
            <td>${user.full_name || 'Не указано'}</td>
            <td>@${user.username || 'Нет'}</td>
            
            <td>${user.company || 'Не указано'}</td>
            <td>${user.contact_number || 'Нет'}</td>
            <td>${user.registration_date ? new Date(user.registration_date).toLocaleDateString('ru-RU') : 'Не указано'}</td>
            <td>
                <span class="badge ${user.subscription_status && user.subscription_status !== 'Нет подписки' ? 'bg-success' : 'bg-secondary'}">
                    ${user.subscription_status || 'Нет'}
                </span>
            </td>
            <td>
                <a href="/users/${user.id}" class="btn btn-sm btn-primary">Детали</a>
            </td>
        `;
        tbody.appendChild(row);
    });
}

// Получение информации о пользователе
async function getUser(userId) {
    try {
        const user = await apiRequest(`/api/users/${userId}`);
        updateUserDetailUI(user);
    } catch (error) {
        console.error('Failed to get user:', error);
    }
}

// Обновление UI детальной информации о пользователе
function updateUserDetailUI(user) {
    // Заполняем поля формы
    document.getElementById('user-id').textContent = user.id || 'Не указано';
    document.getElementById('user-telegram-id').textContent = user.telegram_id || 'Не указано';
    document.getElementById('user-name').textContent = user.full_name || 'Не указано';
    document.getElementById('user-username').textContent = user.username ? `@${user.username}` : 'Нет';
    document.getElementById('user-activity-field').textContent = user.activity_field || 'Не указано';
    document.getElementById('user-company').textContent = user.company || 'Не указано';
    document.getElementById('user-role').textContent = user.role_in_company || 'Не указано';
    document.getElementById('user-phone').textContent = user.contact_number || 'Нет';
    document.getElementById('user-purpose').textContent = user.participation_purpose || 'Не указано';
    document.getElementById('user-registration-date').textContent = user.registration_date ? new Date(user.registration_date).toLocaleDateString('ru-RU') : 'Не указано';
    document.getElementById('user-last-activity').textContent = user.last_activity ? new Date(user.last_activity).toLocaleDateString('ru-RU') : 'Не указано';
    document.getElementById('user-consent').textContent = user.consent_given ? 'Да' : 'Нет';
    
    // Обновляем статус подписки
    const subscriptionStatus = document.getElementById('subscription-status');
    if (subscriptionStatus) {
        if (user.subscription && user.subscription.is_active && new Date(user.subscription.end_date) > new Date()) {
            const daysLeft = Math.ceil((new Date(user.subscription.end_date) - new Date()) / (1000 * 60 * 60 * 24));
            subscriptionStatus.textContent = `Активна (${daysLeft} дн.)`;
        } else {
            subscriptionStatus.textContent = 'Нет подписки';
        }
    }
}

// Получение списка подписок
async function getSubscriptions(page = 0, limit = 20) {
    try {
        const params = new URLSearchParams({
            skip: page * limit,
            limit: limit,
        });
        
        const subscriptions = await apiRequest(`/api/subscriptions?${params}`);
        updateSubscriptionsTable(subscriptions);
    } catch (error) {
        console.error('Failed to get subscriptions:', error);
    }
}

// Обновление таблицы подписок
function updateSubscriptionsTable(subscriptionsData) {
    const tbody = document.querySelector('#subscriptions-table tbody');
    if (!tbody) return;
    
    tbody.innerHTML = '';
    
    // API возвращает объект с полем subscriptions, а не массив напрямую
    const subscriptions = subscriptionsData.subscriptions || subscriptionsData;
    
    if (!Array.isArray(subscriptions)) {
        console.error('Subscriptions is not an array:', subscriptions);
        return;
    }
    
    subscriptions.forEach(subscription => {
        const row = document.createElement('tr');
        const daysLeft = subscription.is_active && new Date(subscription.end_date) > new Date() ? 
            Math.ceil((new Date(subscription.end_date) - new Date()) / (1000 * 60 * 60 * 24)) : 0;
        const isExpiring = daysLeft <= 7 && daysLeft > 0;
        
        row.innerHTML = `
            <td>${subscription.id}</td>
            <td>${subscription.user_id}</td>
            <td>${new Date(subscription.start_date).toLocaleDateString('ru-RU')}</td>
            <td>${new Date(subscription.end_date).toLocaleDateString('ru-RU')}</td>
            <td>
                <span class="badge ${subscription.is_active && new Date(subscription.end_date) > new Date() ? 'bg-success' : 'bg-secondary'}">
                    ${subscription.is_active && new Date(subscription.end_date) > new Date() ? 'Активна' : 'Неактивна'}
                </span>
            </td>
            <td>
                <span class="badge ${subscription.auto_renewal ? 'bg-info' : 'bg-warning'}">
                    ${subscription.auto_renewal ? 'Включено' : 'Выключено'}
                </span>
            </td>
            <td>${subscription.payment_amount} ₽</td>
            <td>
                <span class="badge ${isExpiring ? 'bg-warning' : 'bg-success'}">
                    ${daysLeft} дн.
                </span>
            </td>
            <td>
                <button class="btn btn-sm btn-success" onclick="extendSubscription(${subscription.id})">
                    Продлить
                </button>
                <button class="btn btn-sm btn-info" onclick="toggleAutoRenewal(${subscription.id})">
                    ${subscription.auto_renewal ? 'Отключить' : 'Включить'} автопродление
                </button>
                <button class="btn btn-sm btn-danger" onclick="cancelSubscription(${subscription.id})">
                    Отменить
                </button>
            </td>
        `;
        tbody.appendChild(row);
    });
}

// Продление подписки
async function extendSubscription(subscriptionId, days = 30) {
    try {
        await apiRequest(`/api/subscriptions/${subscriptionId}/extend?days=${days}`, {
            method: 'PUT',
        });
        
        // Обновляем таблицу
        await getSubscriptions();
        showAlert('Подписка успешно продлена', 'success');
    } catch (error) {
        console.error('Failed to extend subscription:', error);
        showAlert('Ошибка при продлении подписки', 'danger');
    }
}

// Переключение автопродления
async function toggleAutoRenewal(subscriptionId) {
    try {
        const result = await apiRequest(`/api/subscriptions/${subscriptionId}/toggle-auto-renewal`, {
            method: 'PUT',
        });
        
        // Обновляем таблицу
        await getSubscriptions();
        showAlert('Автопродление переключено', 'success');
    } catch (error) {
        console.error('Failed to toggle auto renewal:', error);
        showAlert('Ошибка при переключении автопродления', 'danger');
    }
}

// Отмена подписки
async function cancelSubscription(subscriptionId) {
    if (!confirm('Вы уверены, что хотите отменить подписку?')) {
        return;
    }
    
    try {
        await apiRequest(`/api/subscriptions/${subscriptionId}`, {
            method: 'DELETE',
        });
        
        // Обновляем таблицу
        await getSubscriptions();
        showAlert('Подписка отменена', 'success');
    } catch (error) {
        console.error('Failed to cancel subscription:', error);
        showAlert('Ошибка при отмене подписки', 'danger');
    }
}

// Показ уведомлений
function showAlert(message, type = 'info') {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    const container = document.querySelector('.container');
    if (container) {
        container.insertBefore(alertDiv, container.firstChild);
        
        // Автоматически скрываем через 5 секунд
        setTimeout(() => {
            alertDiv.remove();
        }, 5000);
    }
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    // Временно убираем проверку аутентификации для отладки
    // if (!authToken && window.location.pathname !== '/login' && window.location.pathname !== '/') {
    //     window.location.href = '/login';
    //     return;
    // }
    
    // Инициализируем страницы
    const path = window.location.pathname;
    
    if (path === '/') {
        getDashboardStats();
    } else if (path.startsWith('/users') && path !== '/users') {
        const userId = path.split('/').pop();
        if (userId && !isNaN(userId)) {
            getUser(parseInt(userId));
        }
    } else if (path === '/users') {
        getUsers();
    } else if (path === '/subscriptions') {
        getSubscriptions();
    }
    
    // Обработчики форм
    const loginForm = document.getElementById('login-form');
    if (loginForm) {
        loginForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const username = document.getElementById('username').value;
            const password = document.getElementById('password').value;
            
            const success = await login(username, password);
            if (success) {
                window.location.href = '/';
            } else {
                showAlert('Неверное имя пользователя или пароль', 'danger');
            }
        });
    }
    
    // Обработчики фильтров и поиска
    const searchInput = document.getElementById('search-input');
    const statusFilter = document.getElementById('status-filter');
    const sortFilter = document.getElementById('sort-filter');
    
    if (searchInput) {
        let searchTimeout;
        searchInput.addEventListener('input', function() {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                if (path === '/users') {
                    applyFiltersAndSearch();
                }
            }, 300);
        });
    }
    
    if (statusFilter) {
        statusFilter.addEventListener('change', function() {
            if (path === '/users') {
                applyFiltersAndSearch();
            }
        });
    }
    
    if (sortFilter) {
        sortFilter.addEventListener('change', function() {
                if (path === '/users') {
                applyFiltersAndSearch();
                }
        });
    }
}); 