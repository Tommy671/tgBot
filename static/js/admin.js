// Глобальные переменные
let authToken = localStorage.getItem('authToken');

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
            // Токен истек или недействителен
            localStorage.removeItem('authToken');
            window.location.href = '/login';
            return;
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
        const stats = await apiRequest('/api/dashboard');
        updateDashboardUI(stats);
    } catch (error) {
        console.error('Failed to get dashboard stats:', error);
    }
}

// Обновление UI дашборда
function updateDashboardUI(stats) {
    document.getElementById('total-users').textContent = stats.total_users;
    document.getElementById('active-subscriptions').textContent = stats.active_subscriptions;
    document.getElementById('new-users-today').textContent = stats.new_users_today;
    document.getElementById('expiring-subscriptions').textContent = stats.expiring_subscriptions;
}

// Получение списка пользователей
async function getUsers(search = '', page = 0, limit = 20) {
    try {
        const params = new URLSearchParams({
            skip: page * limit,
            limit: limit,
        });
        
        if (search) {
            params.append('search', search);
        }
        
        const users = await apiRequest(`/api/users?${params}`);
        updateUsersTable(users);
    } catch (error) {
        console.error('Failed to get users:', error);
    }
}

// Обновление таблицы пользователей
function updateUsersTable(users) {
    const tbody = document.querySelector('#users-table tbody');
    if (!tbody) return;
    
    tbody.innerHTML = '';
    
    users.forEach(user => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${user.id}</td>
            <td>${user.full_name || 'Не указано'}</td>
            <td>@${user.username || 'Нет'}</td>
            <td>${user.activity_field || 'Не указано'}</td>
            <td>${user.company || 'Не указано'}</td>
            <td>${user.contact_number || 'Нет'}</td>
            <td>${user.registration_date ? new Date(user.registration_date).toLocaleDateString('ru-RU') : 'Не указано'}</td>
            <td>
                <span class="badge ${user.subscription && user.subscription.is_active && new Date(user.subscription.end_date) > new Date() ? 'bg-success' : 'bg-secondary'}">
                    ${user.subscription && user.subscription.is_active && new Date(user.subscription.end_date) > new Date() ? 'Активна' : 'Нет'}
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
function updateSubscriptionsTable(subscriptions) {
    const tbody = document.querySelector('#subscriptions-table tbody');
    if (!tbody) return;
    
    tbody.innerHTML = '';
    
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
    // Проверяем аутентификацию
    if (!authToken && window.location.pathname !== '/login') {
        window.location.href = '/login';
        return;
    }
    
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
    
    // Обработчик поиска
    const searchInput = document.getElementById('search-input');
    if (searchInput) {
        let searchTimeout;
        searchInput.addEventListener('input', function() {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                const search = this.value.trim();
                if (path === '/users') {
                    getUsers(search);
                }
            }, 500);
        });
    }
}); 