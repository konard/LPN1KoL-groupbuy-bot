/**
 * GroupBuy — Personal Cabinet (LK) JavaScript
 * Light Telegram-style interface
 */

// ================================================================
// Screen routing
// ================================================================
const Router = {
    history: [],

    /** Show a screen by its id, push to history */
    goTo(screenId) {
        const prev = document.querySelector('.screen.active');
        if (prev && prev.id !== screenId) {
            prev.classList.remove('active');
            this.history.push(prev.id);
        }
        const next = document.getElementById(screenId);
        if (next) next.classList.add('active');
    },

    /** Go back to previous screen */
    back() {
        const prevId = this.history.pop();
        const current = document.querySelector('.screen.active');
        if (current) current.classList.remove('active');
        const prev = document.getElementById(prevId || 'screen-lk');
        if (prev) prev.classList.add('active');
    }
};

// ================================================================
// Section data — content for the 7 slider cards
// ================================================================
const SECTIONS = {
    subscriptions: {
        title: 'Подписки',
        sliderLabel: 'Ваши подписки',
        sliderCards: [
            { title: 'Канал «Мёд и пасека»', desc: '245 подписчиков', meta: 'Последний пост: вчера' },
            { title: 'Органик-маркет', desc: '1 230 подписчиков', meta: 'Последний пост: сегодня' },
            { title: 'Фермерский кооп', desc: '890 подписчиков', meta: 'Последний пост: 3 дня назад' },
        ],
        content() {
            return `
                <div class="pinned-message">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                        <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/>
                    </svg>
                    Последний пост из «Канал «Мёд и пасека»»
                </div>
                <div style="background:var(--bg-screen);border-radius:var(--radius-lg);padding:16px;box-shadow:var(--shadow-sm)">
                    <div style="font-size:15px;font-weight:600;margin-bottom:8px;">🍯 Весенний сбор — предзаказ открыт!</div>
                    <div style="font-size:14px;color:var(--text-secondary);line-height:1.55;">
                        Дорогие друзья! Открываем предзаказ на майский мёд урожая 2026 года. Липа, акация, гречиха — всё на выбор.
                        Цена фиксируется при предзаказе. Минимальная партия — 1 кг.
                    </div>
                    <div style="font-size:12px;color:var(--text-muted);margin-top:10px;">14 марта 2026 • 14:20</div>
                </div>
                <div style="background:var(--bg-screen);border-radius:var(--radius-lg);padding:16px;box-shadow:var(--shadow-sm)">
                    <div style="font-size:15px;font-weight:600;margin-bottom:8px;">📦 Доставка новой партии</div>
                    <div style="font-size:14px;color:var(--text-secondary);line-height:1.55;">
                        Партия прошлого месяца уже в пути. Ожидаемая дата получения — 20 апреля.
                        Следите за обновлениями.
                    </div>
                    <div style="font-size:12px;color:var(--text-muted);margin-top:10px;">10 марта 2026 • 10:05</div>
                </div>
            `;
        }
    },

    exchange: {
        title: 'Биржа',
        sliderLabel: 'Хотят продать',
        sliderCards: [
            { title: 'Мёд 5 кг', desc: 'Иван П. • Цена: 2 500 ₽', meta: 'Опубликовано: сегодня' },
            { title: 'Греча 10 кг', desc: 'Мария С. • Цена: 1 200 ₽', meta: 'Опубликовано: вчера' },
            { title: 'Оливковое масло 3 л', desc: 'Алексей К. • Цена: 900 ₽', meta: 'Опубликовано: 2 дня назад' },
        ],
        content() {
            return `
                <div class="pinned-message">
                    Список желающих купить (заявки покупателей)
                </div>
                ${this._buyerCards()}
                <button class="btn-submit" onclick="LK.openExchangeForm('sell')" style="margin-top:8px;">+ Выставить на продажу</button>
                <button class="btn-submit" onclick="LK.openExchangeForm('buy')" style="background:var(--bg-section);color:var(--accent);border:1.5px solid var(--accent);margin-top:4px;">+ Добавить запрос на покупку</button>
            `;
        },
        _buyerCards() {
            const items = [
                { name: 'Анна В.', item: 'Ищет мёд 3 кг', price: 'до 1 500 ₽', date: '7 апр' },
                { name: 'Сергей М.', item: 'Ищет орехи 5 кг', price: 'до 2 000 ₽', date: '6 апр' },
                { name: 'Ольга Н.', item: 'Ищет кофе 1 кг', price: 'до 800 ₽', date: '5 апр' },
            ];
            return items.map(i => `
                <div class="purchase-item" style="cursor:default">
                    <div class="message-avatar" style="background:var(--accent);font-size:13px">${i.name.split(' ').map(w=>w[0]).join('')}</div>
                    <div class="purchase-info">
                        <div class="purchase-name">${i.name}</div>
                        <div class="purchase-meta">${i.item} • ${i.price}</div>
                        <div class="purchase-stats">${i.date}</div>
                    </div>
                    <button class="btn-invite-accept" style="font-size:12px;padding:5px 10px">Связаться</button>
                </div>
            `).join('');
        }
    },

    leisure: {
        title: 'Отдых',
        sliderLabel: 'Предложения от организаторов',
        sliderCards: [
            { title: 'Тур в горы', desc: 'Организатор: Турагентство «Вершина»', meta: 'Май 2026 • от 25 000 ₽' },
            { title: 'Отдых на море', desc: 'Организатор: «Морской бриз»', meta: 'Июнь 2026 • от 35 000 ₽' },
            { title: 'Санаторий Подмосковье', desc: 'Организатор: «Здоровье»', meta: 'Апрель 2026 • от 15 000 ₽' },
        ],
        content() {
            return `
                <div class="pinned-message">Запросы-пожелания пользователей</div>
                ${[
                    { name: 'Татьяна К.', when: 'Июнь 2026', where: 'Море (Черноморское побережье)', pref: 'Тихое место, питание включено, для семьи с детьми' },
                    { name: 'Игорь В.', when: 'Май 2026', where: 'Горы', pref: 'Активный туризм, треккинг, небольшая группа' },
                ].map(r => `
                    <div class="purchase-item" style="flex-direction:column;align-items:flex-start;gap:6px;cursor:default">
                        <div style="display:flex;align-items:center;gap:8px;width:100%">
                            <div class="message-avatar" style="background:var(--accent)">${r.name.split(' ').map(w=>w[0]).join('')}</div>
                            <span style="font-size:15px;font-weight:500">${r.name}</span>
                        </div>
                        <div style="font-size:13px;color:var(--text-secondary)">Когда: <b>${r.when}</b> · Где: <b>${r.where}</b></div>
                        <div style="font-size:13px;color:var(--text-muted)">${r.pref}</div>
                    </div>
                `).join('')}
                <button class="btn-submit" onclick="LK.openLeisureRequestForm()">+ Добавить запрос-пожелание</button>
            `;
        }
    },

    competitions: {
        title: 'Соревнования',
        sliderLabel: 'Приглашения от организаторов',
        sliderCards: [
            { title: 'Кулинарный чемпионат', desc: 'Организатор: «ВкусFest»', meta: 'Регистрация до 20 апр' },
            { title: 'Фото-конкурс', desc: 'Организатор: «Lens Club»', meta: 'Регистрация до 30 апр' },
            { title: 'Спортивные игры', desc: 'Организатор: «АктивСпорт»', meta: 'Регистрация до 10 мая' },
        ],
        content() {
            return `
                <div class="pinned-message" style="background:rgba(52,168,240,0.08);border-color:var(--accent);font-size:14px;padding:12px 16px">
                    📋 <b>Правила участия:</b> Для регистрации заполните заявку. Участие бесплатно.
                    Победители получают призы от партнёров. Результаты публикуются в течение 7 дней после окончания.
                </div>
                ${[
                    { name: 'Михаил Р.', req: 'Ищу команду для кулинарного чемпионата', cat: 'Кулинария', date: '7 апр' },
                    { name: 'Светлана Д.', req: 'Участвую в фото-конкурсе, ищу ментора', cat: 'Фото', date: '6 апр' },
                ].map(r => `
                    <div class="purchase-item" style="cursor:default">
                        <div class="message-avatar" style="background:var(--accent)">${r.name.split(' ').map(w=>w[0]).join('')}</div>
                        <div class="purchase-info">
                            <div class="purchase-name">${r.name}</div>
                            <div class="purchase-meta">${r.req}</div>
                            <div class="purchase-stats">${r.cat} · ${r.date}</div>
                        </div>
                        <button class="btn-invite-accept" style="font-size:12px;padding:5px 10px">Ответить</button>
                    </div>
                `).join('')}
            `;
        }
    },

    housing: {
        title: 'Жильё',
        sliderLabel: 'Приглашения в группы',
        sliderCards: [
            { title: 'Новостройка ЖК «Радуга»', desc: '45 участников · Московская обл.', meta: 'Взнос: 10 000 ₽' },
            { title: 'Коттеджный посёлок', desc: '23 участника · Подмосковье', meta: 'Взнос: 15 000 ₽' },
            { title: 'Апартаменты у моря', desc: '67 участников · Сочи', meta: 'Взнос: 20 000 ₽' },
        ],
        content() {
            return `
                <div style="background:var(--bg-screen);border-radius:var(--radius-lg);padding:16px;box-shadow:var(--shadow-sm);margin-bottom:8px">
                    <div style="font-size:16px;font-weight:600;margin-bottom:8px;color:var(--accent)">🏠 Честное жильё</div>
                    <div style="font-size:14px;color:var(--text-secondary);line-height:1.55;">
                        Проект объединяет людей, желающих приобрести недвижимость на выгодных условиях.
                        Совместная покупка снижает стоимость и упрощает оформление.
                        Каждый участник имеет равные права и прозрачный доступ к документам.
                    </div>
                </div>
                <div class="pinned-message">Запросы от участников</div>
                ${[
                    { name: 'Дмитрий К.', req: '2-комнатная квартира, Москва, до 8 млн', date: '7 апр' },
                    { name: 'Наталья П.', req: 'Студия у моря, Сочи или Крым, до 4 млн', date: '5 апр' },
                ].map(r => `
                    <div class="purchase-item" style="cursor:default">
                        <div class="message-avatar" style="background:#7bc862">${r.name.split(' ').map(w=>w[0]).join('')}</div>
                        <div class="purchase-info">
                            <div class="purchase-name">${r.name}</div>
                            <div class="purchase-meta">${r.req}</div>
                            <div class="purchase-stats">${r.date}</div>
                        </div>
                        <button class="btn-invite-accept" style="font-size:12px;padding:5px 10px">Контакт</button>
                    </div>
                `).join('')}
            `;
        }
    },

    news: {
        title: 'Новости',
        sliderLabel: 'Все поставщики и организаторы',
        sliderCards: [
            { title: 'Пасека Алтай', desc: 'Скидка 10% на оптовый заказ мёда', meta: 'Сегодня' },
            { title: 'ФермерМаркет', desc: 'Новинка: сезонные овощи с доставкой', meta: 'Вчера' },
            { title: 'КофеИмпорт', desc: 'Новая партия эфиопской арабики', meta: '5 апр' },
        ],
        content() {
            return `
                <div class="pinned-message">Посты по вашим интересам (продукты, органика, кофе)</div>
                ${[
                    { org: 'Пасека Алтай', text: '🍯 Весенний мёд 2026 — предзаказ. Акация, липа, разнотравье. Доставка по всей России. Минимум 2 кг.', date: 'Сегодня 10:00', reactions: '❤️ 42 · 🔥 18' },
                    { org: 'ФермерМаркет', text: '🥦 Первые сезонные овощи уже в продаже! Редис, салат, шпинат. Только из Подмосковья. Заказы принимаем до 12:00.', date: 'Вчера 15:30', reactions: '❤️ 31 · 👍 12' },
                    { org: 'КофеИмпорт', text: '☕ Новая партия эфиопской арабики Yirgacheffe. 1 кг — 1 200 ₽. Свежеобжаренный, под заказ. Ограниченное количество.', date: '5 апр 9:15', reactions: '❤️ 55 · 🔥 27' },
                ].map(n => `
                    <div style="background:var(--bg-screen);border-radius:var(--radius-lg);padding:16px;box-shadow:var(--shadow-sm)">
                        <div style="font-size:13px;font-weight:600;color:var(--accent);margin-bottom:6px">${n.org}</div>
                        <div style="font-size:14px;color:var(--text-primary);line-height:1.55;margin-bottom:8px">${n.text}</div>
                        <div style="display:flex;justify-content:space-between;font-size:12px;color:var(--text-muted)">
                            <span>${n.reactions}</span><span>${n.date}</span>
                        </div>
                    </div>
                `).join('')}
            `;
        }
    },

    blogs: {
        title: 'Блоги / каналы',
        sliderLabel: 'Популярные посты (по реакциям)',
        sliderCards: [
            { title: 'ТОП: Мёд 2026', desc: '❤️ 234 · Пасека Алтай', meta: 'Подписан' },
            { title: 'ТОП: Кофейный гид', desc: '❤️ 189 · КофеМир', meta: 'Подписан' },
            { title: 'ТОП: Рецепты закупок', desc: '❤️ 156 · ФермерБлог', meta: 'Все каналы' },
        ],
        content() {
            const allPosts = [
                { ch: 'Пасека Алтай', subscribed: true, text: '🍯 Как отличить настоящий мёд от подделки — полный гид.', date: '7 апр', reactions: '❤️ 234' },
                { ch: 'КофеМир', subscribed: true, text: '☕ Топ-10 регионов для арабики: наш выбор этого сезона.', date: '6 апр', reactions: '❤️ 189' },
                { ch: 'ФермерБлог', subscribed: false, text: '🌿 Зачем покупать сезонные овощи вместе: экономия до 40%.', date: '5 апр', reactions: '❤️ 142' },
                { ch: 'ЗдоровьеПлюс', subscribed: false, text: '🥗 Суперфуды: миф или реальная польза? Разбираем по косточкам.', date: '4 апр', reactions: '❤️ 98' },
            ];
            const subscribed = allPosts.filter(p => p.subscribed);
            const rest = allPosts.filter(p => !p.subscribed).sort((a,b) => a.ch.localeCompare(b.ch));
            const render = posts => posts.map(p => `
                <div style="background:var(--bg-screen);border-radius:var(--radius-lg);padding:16px;box-shadow:var(--shadow-sm)">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
                        <span style="font-size:13px;font-weight:600;color:var(--accent)">${p.ch}</span>
                        ${p.subscribed ? '<span style="font-size:11px;background:var(--accent);color:#fff;border-radius:8px;padding:2px 7px">Подписан</span>' : ''}
                    </div>
                    <div style="font-size:14px;color:var(--text-primary);line-height:1.55;margin-bottom:8px">${p.text}</div>
                    <div style="display:flex;justify-content:space-between;font-size:12px;color:var(--text-muted)">
                        <span>${p.reactions}</span><span>${p.date}</span>
                    </div>
                </div>
            `).join('');
            return `
                <div class="pinned-message">Сначала — подписки, затем все каналы (по алфавиту)</div>
                ${render(subscribed)}
                ${rest.length ? `<div class="section-title" style="margin-top:8px">Другие каналы</div>${render(rest)}` : ''}
            `;
        }
    }
};

// ================================================================
// Main LK controller
// ================================================================
const LK = {
    currentFontSize: 14,

    openSection(key) {
        const sec = SECTIONS[key];
        if (!sec) return;

        document.getElementById('section-title').textContent = sec.title;
        document.getElementById('section-slider-label').textContent = sec.sliderLabel;

        // Render slider cards
        const track = document.getElementById('section-slider-track');
        track.innerHTML = sec.sliderCards.map(card => `
            <div class="section-card">
                <div class="section-card-title">${card.title}</div>
                <div class="section-card-desc">${card.desc}</div>
                <div class="section-card-meta">${card.meta}</div>
            </div>
        `).join('');

        // Render body
        const body = document.getElementById('section-body');
        body.innerHTML = sec.content.call(sec);

        Router.goTo('screen-section');
    },

    openCurrentPurchases() {
        Router.goTo('screen-current-purchases');
    },

    openCreateRequest() {
        Router.goTo('screen-create-request');
    },

    openHistory() {
        Router.goTo('screen-history');
    },

    openSettings() {
        Router.goTo('screen-settings');
    },

    openChat(id) {
        Router.goTo('screen-chat');
    },

    goBack() {
        Router.back();
    },

    openProfile() {
        Utils.toast('Профиль — скоро будет доступно');
    },

    downloadApp() {
        Utils.toast('Приложение скоро появится в App Store и Google Play');
    },

    switchRole() {
        Utils.toast('Смена роли — скоро будет доступно');
    },

    openBalance() {
        Utils.toast('Баланс: интеграция с банком');
    },

    acceptInvite(id) {
        Utils.toast('Приглашение принято!');
    },

    submitRequest(e) {
        e.preventDefault();
        Utils.toast('Запрос опубликован!');
    },

    sendMessage() {
        const input = document.querySelector('.chat-input');
        const text = input && input.value.trim();
        if (!text) return;
        const messages = document.getElementById('chat-messages');
        const msg = document.createElement('div');
        msg.className = 'msg msg-out';
        msg.innerHTML = `
            <div class="msg-bubble">
                <div class="msg-text">${Utils.escapeHtml(text)}</div>
                <div class="msg-time">${Utils.time()} ✓</div>
            </div>
        `;
        messages.appendChild(msg);
        input.value = '';
        msg.scrollIntoView({ behavior: 'smooth' });
    },

    openExchangeForm(type) {
        Utils.toast(type === 'sell' ? 'Форма для продажи — скоро' : 'Форма для покупки — скоро');
    },

    openLeisureRequestForm() {
        Utils.toast('Форма запроса на отдых — скоро');
    },

    openChatInfo() {
        Utils.toast('Информация о закупке');
    },

    setTheme(theme) {
        document.body.classList.toggle('dark', theme === 'dark');
        document.querySelectorAll('.theme-btn').forEach(b => {
            b.classList.toggle('active', b.textContent.toLowerCase().includes(theme === 'dark' ? 'тёмн' : 'светл'));
        });
        Utils.toast(theme === 'dark' ? 'Тёмная тема включена' : 'Светлая тема включена');
    },

    changeFontSize(delta) {
        this.currentFontSize = Math.max(12, Math.min(20, this.currentFontSize + delta));
        document.documentElement.style.fontSize = this.currentFontSize + 'px';
        const disp = document.getElementById('font-size-display');
        if (disp) disp.textContent = this.currentFontSize + 'px';
    },

    toggleNotifications(type, enabled) {
        Utils.toast(`Уведомления «${type}»: ${enabled ? 'включены' : 'выключены'}`);
    },

    changeLanguage(lang) {
        Utils.toast(lang === 'en' ? 'Language changed to English (coming soon)' : 'Язык: Русский');
    },

    logout() {
        if (confirm('Вы уверены, что хотите выйти?')) {
            window.location.href = '/';
        }
    },

    search(query) {
        // Placeholder for search logic
        if (!query) return;
        console.log('Search:', query);
    }
};

// ================================================================
// Utilities
// ================================================================
const Utils = {
    toast(message, duration = 3000) {
        let container = document.getElementById('toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'toast-container';
            container.style.cssText = 'position:fixed;bottom:24px;left:50%;transform:translateX(-50%);z-index:9999;display:flex;flex-direction:column;gap:8px;align-items:center;pointer-events:none;';
            document.body.appendChild(container);
        }
        const toast = document.createElement('div');
        toast.style.cssText = 'background:rgba(0,0,0,0.75);color:#fff;padding:10px 18px;border-radius:20px;font-size:14px;max-width:320px;text-align:center;animation:fadeIn 0.2s ease;backdrop-filter:blur(4px);pointer-events:none;';
        toast.textContent = message;
        container.appendChild(toast);
        setTimeout(() => toast.remove(), duration);
    },

    escapeHtml(str) {
        const d = document.createElement('div');
        d.textContent = str;
        return d.innerHTML;
    },

    time() {
        const d = new Date();
        return d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
    }
};

// ================================================================
// LK Slider scroll → dot sync
// ================================================================
(function initSliderDots() {
    document.addEventListener('DOMContentLoaded', () => {
        const track = document.getElementById('lk-slider-track');
        const dots  = document.querySelectorAll('.lk-dot');
        if (!track || !dots.length) return;

        let debounceTimer;
        track.addEventListener('scroll', () => {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(() => {
                const cardWidth = track.querySelector('.lk-card')
                    ? track.querySelector('.lk-card').offsetWidth + 16 /* gap */ : 1;
                const idx = Math.round(track.scrollLeft / cardWidth);
                dots.forEach((d, i) => d.classList.toggle('active', i === idx));
            }, 50);
        }, { passive: true });

        // Click dot → scroll to card
        dots.forEach((dot, i) => {
            dot.addEventListener('click', () => {
                const cards = track.querySelectorAll('.lk-card');
                if (cards[i]) {
                    cards[i].scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'start' });
                }
            });
        });
    });
})();

// ================================================================
// Auto-resize chat textarea
// ================================================================
document.addEventListener('DOMContentLoaded', () => {
    const chatInput = document.querySelector('.chat-input');
    if (chatInput) {
        chatInput.addEventListener('input', () => {
            chatInput.style.height = 'auto';
            chatInput.style.height = Math.min(chatInput.scrollHeight, 120) + 'px';
        });
        chatInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                LK.sendMessage();
            }
        });
    }
});
