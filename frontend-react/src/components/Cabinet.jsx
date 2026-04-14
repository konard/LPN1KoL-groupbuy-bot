import React, { useEffect, useState, useRef, useCallback, useMemo } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useStore } from '../store/useStore';
import { useWebSocket } from '../hooks/useWebSocket';
import { api } from '../services/api';
import { batchProcessMessages } from '../services/wasm';
import {
  formatCurrency,
  formatTime,
  getInitials,
  getAvatarColor,
  getRoleText,
  getStatusText,
} from '../utils/helpers';
import { SendIcon, AttachIcon } from './Icons';
import {
  RequestsIcon,
  ShoppingBagIcon,
  MailIcon,
  HistoryIcon,
  PlusIcon,
  HomeIcon,
  FileIcon,
  SearchIcon,
} from './Icons';
import CompanyCardModal from './CompanyCardModal';
import PriceListModal from './PriceListModal';
import NewsModal from './NewsModal';
import CreateRequestModal from './CreateRequestModal';
import ClosingDocumentsModal from './ClosingDocumentsModal';

// ─── Inline SVG Icons ────────────────────────────────────────────────────────

function InvitationIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" />
      <polyline points="22,6 12,13 2,6" />
    </svg>
  );
}

function ChevronRight() {
  return (
    <svg className="lk-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
      <polyline points="9 18 15 12 9 6" />
    </svg>
  );
}

// ─── LC Slider categories ────────────────────────────────────────────────────

const LC_SLIDER_CATEGORIES = [
  { id: 'subscriptions', label: 'Подписки', description: 'Каналы и блоги, на которые вы подписаны' },
  { id: 'exchange', label: 'Биржа', description: 'Купля и продажа товаров между участниками' },
  { id: 'rest', label: 'Отдых', description: 'Запросы и предложения для отдыха' },
  { id: 'competitions', label: 'Соревнования', description: 'Участвуйте в соревнованиях и выигрывайте' },
  { id: 'housing', label: 'Жильё', description: 'Проект «Честное жильё» — группы покупателей' },
  { id: 'news', label: 'Новости', description: 'Актуальные посты от поставщиков и организаторов' },
  { id: 'blogs', label: 'Блоги / каналы', description: 'Лента постов и популярные материалы' },
];

// ─── Sub-components ──────────────────────────────────────────────────────────

/** LK action row — M3-style list button with tonal icon container, label, badge, chevron */
function ActionRow({ icon, label, badge, onClick, danger }) {
  return (
    <button
      className={`lk-list-action-btn${danger ? ' lk-list-action-btn--danger' : ''}`}
      onClick={onClick}
    >
      <span className={`lk-list-icon-container${danger ? ' lk-list-icon-container--danger' : ''}`}>{icon}</span>
      <span style={{ flex: 1, textAlign: 'left' }}>{label}</span>
      {badge != null && badge > 0 && (
        <span className="lk-message-badge">{badge}</span>
      )}
      <ChevronRight />
    </button>
  );
}

/** Section group header */
function SectionHeader({ title }) {
  return <div className="lk-group-header">{title}</div>;
}

/** Expandable content panel */
function ContentPanel({ children }) {
  return <div className="lk-content-panel">{children}</div>;
}

// ─── Category page content ───────────────────────────────────────────────────

function CategoryPageContent({ category, procurements, user, newsFeed, newsFeedLoading, onLoadNewsFeed, navigate }) {
  if (!category) return null;

  if (category.id === 'subscriptions') {
    return (
      <p className="lk-purchase-meta" style={{ padding: '4px 0' }}>
        Последние посты из ваших подписок появятся здесь.
      </p>
    );
  }

  if (category.id === 'exchange') {
    const allProcs = [
      ...(procurements?.organized || []),
      ...(procurements?.participating || []),
    ].filter((p) => p.status === 'active');
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <p className="lk-purchase-meta">Биржа — список желающих купить и продать.</p>
        {allProcs.length === 0 ? (
          <p className="lk-purchase-stats">Нет активных позиций</p>
        ) : (
          allProcs.slice(0, 5).map((p) => (
            <div
              key={p.id}
              className="lk-purchase-item"
              onClick={() => navigate && navigate(`/chat/${p.id}`)}
            >
              <div className="lk-purchase-info">
                <div className="lk-purchase-name">{p.title}</div>
                <div className="lk-purchase-meta">
                  {p.city} · {formatCurrency(p.current_amount || 0)} · {p.participant_count || 0} участн.
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    );
  }

  if (category.id === 'news') {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <p className="lk-purchase-meta" style={{ margin: 0 }}>Посты от организаторов и поставщиков.</p>
          <button
            className="lk-btn-invite-accept"
            style={{ fontSize: '0.75rem', padding: '4px 10px' }}
            onClick={onLoadNewsFeed}
            disabled={newsFeedLoading}
          >
            {newsFeedLoading ? 'Загрузка...' : 'Обновить'}
          </button>
        </div>
        {newsFeed.length === 0 && !newsFeedLoading && (
          <p className="lk-purchase-stats">Нажмите «Обновить» чтобы загрузить новости</p>
        )}
        {newsFeed.map((item) => (
          <div
            key={item.id}
            className="lk-purchase-item"
            onClick={() => item.procurement_id && navigate && navigate(`/chat/${item.procurement_id}`)}
            style={{ cursor: item.procurement_id ? 'pointer' : 'default' }}
          >
            <div className="lk-purchase-info">
              <div className="lk-purchase-name">{item.title}</div>
              <div className="lk-purchase-meta" style={{ marginBottom: 2 }}>{item.text}</div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span className="lk-purchase-stats">{item.author}</span>
                <span className="lk-purchase-stats">{formatTime(item.date)}</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div>
      <p className="lk-purchase-meta" style={{ padding: '4px 0' }}>{category.description}</p>
      <p className="lk-purchase-stats">Раздел разрабатывается...</p>
    </div>
  );
}

// ─── Telegram-style two-panel chat section ──────────────────────────────────

function CabinetChatSection() {
  const {
    user,
    procurements,
    messages,
    currentChat,
    unreadCounts,
    setCurrentChat,
    loadMessages,
    sendMessage,
  } = useStore();

  const [messageText, setMessageText] = useState('');
  const messageAreaRef = useRef(null);
  const textareaRef = useRef(null);

  // Connect WebSocket for the active chat
  const { sendTyping } = useWebSocket(currentChat);

  const activeProcurement = procurements.find((p) => p.id === currentChat) || null;

  // Load messages when active chat changes
  useEffect(() => {
    if (currentChat) {
      loadMessages(currentChat);
    }
  }, [currentChat, loadMessages]);

  // Auto-scroll to bottom when messages update
  useEffect(() => {
    if (messageAreaRef.current) {
      messageAreaRef.current.scrollTop = messageAreaRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSelectChat = useCallback((procurement) => {
    setCurrentChat(procurement.id);
  }, [setCurrentChat]);

  const handleSend = useCallback(async () => {
    const text = messageText.trim();
    if (!text || !user) return;
    setMessageText('');
    if (textareaRef.current) textareaRef.current.style.height = 'auto';
    await sendMessage(text);
  }, [messageText, user, sendMessage]);

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleInput = () => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 120) + 'px';
    }
    sendTyping();
  };

  const processedMessages = useMemo(() => {
    if (!messages || messages.length === 0) return [];
    return batchProcessMessages(messages, user?.coreId || user?.id || 0);
  }, [messages, user?.coreId, user?.id]);

  return (
    <div className="lk-chat-panel">
      {/* Left: conversation list */}
      <div className="lk-chat-list-col">
        <div className="lk-chat-list-header">Чаты</div>
        {procurements.length === 0 ? (
          <p className="lk-purchase-stats" style={{ padding: '12px 16px' }}>Нет активных закупок</p>
        ) : (
          procurements.map((p) => (
            <div
              key={p.id}
              className={`lk-chat-list-item${currentChat === p.id ? ' active' : ''}`}
              onClick={() => handleSelectChat(p)}
            >
              <div className="chat-avatar" style={{ backgroundColor: getAvatarColor(p.title), flexShrink: 0 }}>
                {getInitials(p.title)}
              </div>
              <div className="chat-info">
                <div className="chat-header">
                  <span className="chat-title">{p.title}</span>
                  <span className="chat-time">{formatTime(p.updated_at)}</span>
                </div>
                <div className="chat-message">
                  {p.description
                    ? (p.description.length > 40 ? p.description.slice(0, 40) + '…' : p.description)
                    : `${p.participant_count || 0} участников`}
                </div>
              </div>
              {unreadCounts[p.id] > 0 && (
                <div className="chat-badge">{unreadCounts[p.id]}</div>
              )}
            </div>
          ))
        )}
      </div>

      {/* Right: active chat pane */}
      <div className="lk-chat-view-col">
        {currentChat && activeProcurement && (
          <>
            {/* Chat header */}
            <div className="lk-chat-view-header">
              <div className="chat-avatar" style={{ backgroundColor: getAvatarColor(activeProcurement.title), flexShrink: 0 }}>
                {getInitials(activeProcurement.title)}
              </div>
              <div className="flex-col">
                <span style={{ fontWeight: 600, fontSize: '0.95rem' }}>{activeProcurement.title}</span>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                  {activeProcurement.participant_count || 0} участников
                </span>
              </div>
            </div>

            {/* Messages */}
            <div className="message-area" ref={messageAreaRef}>
              {processedMessages.length === 0 ? (
                <div className="p-lg text-center text-muted"><p>Нет сообщений</p></div>
              ) : (
                processedMessages.map((msg, index) => {
                  const items = [];
                  if (msg.date_divider) {
                    items.push(
                      <div key={`date-${index}`} className="message-date-divider">
                        <span>{msg.date_divider}</span>
                      </div>
                    );
                  }
                  if (msg.is_system) {
                    items.push(
                      <div key={msg.id || index} className="message system">{msg.text}</div>
                    );
                  } else {
                    items.push(
                      <div key={msg.id || index} className={`message ${msg.is_own ? 'outgoing' : 'incoming'}`}>
                        {!msg.is_own && msg.sender_name && (
                          <div className="message-sender">{msg.sender_name}</div>
                        )}
                        <div className="message-text" dangerouslySetInnerHTML={{ __html: msg.formatted_text }} />
                        <div className="message-time">{msg.formatted_time}</div>
                      </div>
                    );
                  }
                  return items;
                })
              )}
            </div>

            {/* Input area */}
            <div className="message-input-area">
              <button className="btn btn-icon" aria-label="Attach file"><AttachIcon /></button>
              <div className="message-input-container">
                <textarea
                  ref={textareaRef}
                  className="message-input"
                  placeholder="Сообщение..."
                  rows="1"
                  value={messageText}
                  onChange={(e) => setMessageText(e.target.value)}
                  onKeyDown={handleKeyDown}
                  onInput={handleInput}
                />
              </div>
              <button className="send-button" aria-label="Send message" onClick={handleSend}>
                <SendIcon />
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// ─── Main Cabinet component ──────────────────────────────────────────────────

function Cabinet() {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, openCreateProcurementModal, addToast, openLoginModal, createProcurementModalOpen } = useStore();
  const [userStats, setUserStats] = useState(null);
  const [companyCardOpen, setCompanyCardOpen] = useState(false);
  const [priceListOpen, setPriceListOpen] = useState(false);
  const [newsOpen, setNewsOpen] = useState(false);
  const [createRequestOpen, setCreateRequestOpen] = useState(false);
  const [closingDocsOpen, setClosingDocsOpen] = useState(false);
  const [selectedOrderTableId, setSelectedOrderTableId] = useState(null);

  const [myProcurements, setMyProcurements] = useState(null);
  const [procurementsLoading, setProcurementsLoading] = useState(true);
  const [myRequests, setMyRequests] = useState([]);
  const [procurementHistory, setProcurementHistory] = useState([]);
  const [paymentProcurements, setPaymentProcurements] = useState([]);
  const [orderTables, setOrderTables] = useState([]);
  const [shipmentHistory, setShipmentHistory] = useState([]);

  // User search state
  const [userSearchQuery, setUserSearchQuery] = useState('');
  const [userSearchResults, setUserSearchResults] = useState([]);
  const [userSearchLoading, setUserSearchLoading] = useState(false);
  const userSearchTimeout = useRef(null);

  // Editors (shared access) state
  const [editorsModalOpen, setEditorsModalOpen] = useState(false);
  const [editorsProcurement, setEditorsProcurement] = useState(null);
  const [editorsList, setEditorsList] = useState([]);
  const [editorsLoading, setEditorsLoading] = useState(false);
  const [editorSearchQuery, setEditorSearchQuery] = useState('');
  const [editorSearchResults, setEditorSearchResults] = useState([]);
  const [editorSearchLoading, setEditorSearchLoading] = useState(false);
  const editorSearchTimeout = useRef(null);

  // Add participant modal state
  const [addParticipantOpen, setAddParticipantOpen] = useState(false);
  const [addParticipantProcurement, setAddParticipantProcurement] = useState(null);
  const [addParticipantUserQuery, setAddParticipantUserQuery] = useState('');
  const [addParticipantResults, setAddParticipantResults] = useState([]);
  const [addParticipantLoading, setAddParticipantLoading] = useState(false);
  const [addParticipantSelected, setAddParticipantSelected] = useState(null);
  const [addParticipantAmount, setAddParticipantAmount] = useState('');
  const [addParticipantQuantity, setAddParticipantQuantity] = useState('1');
  const addParticipantSearchTimeout = useRef(null);

  // Invite user modal state
  const [inviteOpen, setInviteOpen] = useState(false);
  const [inviteProcurement, setInviteProcurement] = useState(null);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteLoading, setInviteLoading] = useState(false);

  // Subscriptions
  const [subscriptions, setSubscriptions] = useState([
    { id: 1, type: 'category', name: 'Биржа', active: true },
    { id: 2, type: 'category', name: 'Быт', active: true },
    { id: 3, type: 'organizer', name: 'Организатор Иванов', active: false },
  ]);
  const [newSubscription, setNewSubscription] = useState('');

  // Messages/Invitations
  const [messages, setMessages] = useState([]);
  const [replyTarget, setReplyTarget] = useState(null);
  const [replyText, setReplyText] = useState('');

  // Invitations
  const [invitations, setInvitations] = useState([]);

  // Pending procurements
  const [pendingItems, setPendingItems] = useState([]);
  const [pendingLoaded, setPendingLoaded] = useState(false);

  // Approve supplier modal
  const [approveSupplierOpen, setApproveSupplierOpen] = useState(false);
  const [approveSupplierProcurement, setApproveSupplierProcurement] = useState(null);
  const [supplierSearchQuery, setSupplierSearchQuery] = useState('');
  const [supplierSearchResults, setSupplierSearchResults] = useState([]);
  const [supplierSearchLoading, setSupplierSearchLoading] = useState(false);
  const supplierSearchTimeout = useRef(null);

  // News feed state
  const [newsFeed, setNewsFeed] = useState([]);
  const [newsFeedLoading, setNewsFeedLoading] = useState(false);

  // LC state
  const [activeSection, setActiveSection] = useState(null);
  const [selectedCarouselCategory, setSelectedCarouselCategory] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');

  // Slider ref
  const sliderTrackRef = useRef(null);

  // Set initial active section based on user role to show active purchases immediately
  useEffect(() => {
    if (!user) return;
    setActiveSection((prev) => {
      if (prev !== null) return prev;
      if (user.role === 'organizer') return 'myProcurements';
      if (user.role === 'buyer') return 'currentPurchases';
      return prev;
    });
  }, [user]);

  // loadStats is extracted as a useCallback so it can be called from multiple effects
  // (initial load, visibility change, and post-procurement-creation refresh).
  const loadStats = useCallback(async () => {
    if (!user) return;
    setProcurementsLoading(true);
    try {
      const coreId = user.coreId || user.id;
      const [balance, procurements, notifications] = await Promise.all([
        api.getUserBalance(coreId).catch(() => null),
        api.getUserProcurements(coreId).catch(() => null),
        api.getNotifications(coreId).catch(() => null),
      ]);

      if (notifications) {
        const notifList = notifications.results || notifications;
        const invites = notifList.filter((n) => n.notification_type === 'invite' || n.notification_type === 'invitation');
        const msgs = notifList.filter((n) => n.notification_type !== 'invite' && n.notification_type !== 'invitation');
        setInvitations(invites.map((n) => ({
          id: n.id,
          from: n.sender_name || 'Организатор',
          text: n.title ? `${n.title}: ${n.message}` : n.message,
          date: n.created_at,
          read: n.is_read,
          procurement_id: n.procurement_id || n.related_object_id,
        })));
        setMessages(msgs.map((n) => ({
          id: n.id,
          from: n.notification_type === 'system' ? 'Система' : (n.sender_name || 'Администратор'),
          text: n.title ? `${n.title}: ${n.message}` : n.message,
          date: n.created_at,
          read: n.is_read,
          procurement_id: n.procurement_id || n.related_object_id,
          sender_id: n.sender_id,
        })));
      }

      let organized = [];
      let participating = [];
      if (procurements) {
        if (Array.isArray(procurements)) {
          organized = procurements.filter((p) => p.organizer === (user.coreId || user.id));
          participating = procurements.filter((p) => p.organizer !== (user.coreId || user.id));
        } else {
          organized = procurements.organized || [];
          participating = procurements.participating || [];
        }
      }
      const procs = [...organized, ...participating];
      setMyProcurements({ organized, participating });
      setPaymentProcurements(organized.filter((p) => p.status === 'payment' || p.status === 'stopped'));
      const history = procs.filter((p) => p.status === 'completed' || p.status === 'cancelled');
      setProcurementHistory(history);

      setUserStats({
        balance: balance || {},
        procurementsCount: procs.length,
        activeProcurements: procs.filter((p) => p.status === 'active').length,
        completedProcurements: procs.filter((p) => p.status === 'completed').length,
      });
    } catch {
      // ignore stats loading errors
    } finally {
      setProcurementsLoading(false);
    }
  }, [user]);

  useEffect(() => {
    if (!user) return;
    loadStats();

    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        loadStats();
      }
    };
    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [user, location.key, loadStats]);

  // Reload procurements immediately when the create-procurement modal closes.
  // This ensures the new purchase appears in Cabinet without a manual page refresh.
  const prevCreateModalOpen = useRef(createProcurementModalOpen);
  useEffect(() => {
    if (prevCreateModalOpen.current && !createProcurementModalOpen) {
      loadStats();
    }
    prevCreateModalOpen.current = createProcurementModalOpen;
  }, [createProcurementModalOpen, loadStats]);

  // ─── Handlers ──────────────────────────────────────────────────────────────

  const handleSaveCompanyCard = async (data) => {
    try {
      await api.updateUser(user.coreId || user.id, {
        first_name: data.company_name,
        phone: data.phone,
        email: data.email,
      });
      addToast('Карточка компании сохранена', 'success');
    } catch {
      addToast('Ошибка сохранения карточки компании', 'error');
      throw new Error('Save failed');
    }
  };

  const handleSavePriceList = async () => {
    addToast('Прайс-лист загружен', 'success');
  };

  const handleSaveNews = async () => {
    addToast('Новость опубликована', 'success');
  };

  const handleSaveRequest = async (data) => {
    const newRequest = { id: Date.now(), ...data, created_at: new Date().toISOString() };
    setMyRequests((prev) => [newRequest, ...prev]);
    addToast('Запрос успешно создан', 'success');
  };

  const handleDeleteRequest = (id) => {
    setMyRequests((prev) => prev.filter((r) => r.id !== id));
    addToast('Запрос удалён', 'info');
  };

  const handleProcurementStatusChange = async (procurementId, newStatus) => {
    try {
      await api.updateProcurementStatus(procurementId, newStatus, user.coreId || user.id);
      setMyProcurements((prev) => {
        if (!prev) return prev;
        const updateList = (list) =>
          list.map((p) => p.id === procurementId ? { ...p, status: newStatus } : p);
        return { organized: updateList(prev.organized), participating: updateList(prev.participating) };
      });
      setPaymentProcurements((prev) =>
        prev.map((p) => p.id === procurementId ? { ...p, status: newStatus } : p)
      );
      setProcurementHistory((prev) =>
        prev.map((p) => p.id === procurementId ? { ...p, status: newStatus } : p)
      );
      addToast('Статус закупки обновлён', 'success');
    } catch (error) {
      addToast(error.message || 'Ошибка при изменении статуса', 'error');
    }
  };

  const handleSendClosingDocuments = async () => {
    addToast('Закрывающие документы отправлены покупателям', 'success');
  };

  const handleAddSubscription = () => {
    const name = newSubscription.trim();
    if (!name) return;
    setSubscriptions((prev) => [...prev, { id: Date.now(), type: 'category', name, active: true }]);
    setNewSubscription('');
    addToast('Подписка добавлена', 'success');
  };

  const handleToggleSubscription = (id) => {
    setSubscriptions((prev) => prev.map((s) => s.id === id ? { ...s, active: !s.active } : s));
  };

  const handleDeleteSubscription = (id) => {
    setSubscriptions((prev) => prev.filter((s) => s.id !== id));
    addToast('Подписка удалена', 'info');
  };

  const handleMarkMessageRead = async (message) => {
    try {
      await api.markNotificationRead(message.id);
    } catch {
      // ignore
    }
    setMessages((prev) => prev.map((m) => m.id === message.id ? { ...m, read: true } : m));
    if (message.procurement_id) {
      navigate(`/chat/${message.procurement_id}`);
    }
  };

  const handleMarkInvitationRead = async (id) => {
    try {
      await api.markNotificationRead(id);
    } catch {
      // ignore
    }
    setInvitations((prev) => prev.map((inv) => inv.id === id ? { ...inv, read: true } : inv));
  };

  const handleReplyMessage = async () => {
    if (!replyText.trim() || !replyTarget) return;
    try {
      await api.sendMessage({ text: replyText, recipient_id: replyTarget.sender_id });
      addToast('Ответ отправлен', 'success');
    } catch {
      addToast('Ошибка отправки ответа', 'error');
    }
    setReplyTarget(null);
    setReplyText('');
  };

  const handleStopProcurement = async (procurement) => {
    if (!window.confirm(`Остановить закупку "${procurement.title}"? Участники получат уведомление с запросом подтверждения.`)) return;
    try {
      await api.stopProcurement(procurement.id);
      setMyProcurements((prev) => {
        if (!prev) return prev;
        const updateList = (list) => list.map((p) => p.id === procurement.id ? { ...p, status: 'stopped' } : p);
        return { organized: updateList(prev.organized), participating: updateList(prev.participating) };
      });
      setPaymentProcurements((prev) => prev.map((p) => p.id === procurement.id ? { ...p, status: 'stopped' } : p));
      addToast('Закупка остановлена. Создан закрытый чат для участников.', 'success');
    } catch (err) {
      addToast(err.message || 'Ошибка остановки закупки', 'error');
    }
  };

  const handleOpenApproveSupplier = (procurement) => {
    setApproveSupplierProcurement(procurement);
    setSupplierSearchQuery('');
    setSupplierSearchResults([]);
    setApproveSupplierOpen(true);
  };

  const handleSupplierSearch = (query) => {
    setSupplierSearchQuery(query);
    if (supplierSearchTimeout.current) clearTimeout(supplierSearchTimeout.current);
    if (!query.trim()) { setSupplierSearchResults([]); return; }
    supplierSearchTimeout.current = setTimeout(async () => {
      setSupplierSearchLoading(true);
      try {
        const results = await api.searchUsers(query);
        const all = Array.isArray(results) ? results : (results.results || []);
        setSupplierSearchResults(all.filter((u) => u.role === 'supplier'));
      } catch {
        setSupplierSearchResults([]);
      } finally {
        setSupplierSearchLoading(false);
      }
    }, 400);
  };

  const handleApproveSupplierSubmit = async (supplier) => {
    if (!approveSupplierProcurement) return;
    try {
      await api.approveSupplier(approveSupplierProcurement.id, supplier.id);
      setMyProcurements((prev) => {
        if (!prev) return prev;
        const updateList = (list) => list.map((p) => p.id === approveSupplierProcurement.id ? { ...p, supplier: supplier.id, supplier_name: `${supplier.first_name || ''} ${supplier.last_name || ''}`.trim() } : p);
        return { organized: updateList(prev.organized), participating: updateList(prev.participating) };
      });
      addToast(`Поставщик ${supplier.first_name || ''} ${supplier.last_name || ''} одобрен`, 'success');
      setApproveSupplierOpen(false);
    } catch (err) {
      addToast(err.message || 'Ошибка одобрения поставщика', 'error');
    }
  };

  const handleCreateReceiptTable = async (procurement) => {
    try {
      const table = await api.getReceiptTable(procurement.id);
      if (table) {
        addToast('Таблица квитанций создана и отправлена поставщику', 'success');
      }
    } catch (err) {
      addToast(err.message || 'Ошибка создания таблицы квитанций', 'error');
    }
  };

  const handleCloseProcurement = async (procurement) => {
    if (!window.confirm(`Закрыть закупку "${procurement.title}"? Она будет перенесена в историю.`)) return;
    try {
      await api.closeProcurement(procurement.id);
      setMyProcurements((prev) => {
        if (!prev) return prev;
        const updateList = (list) => list.map((p) => p.id === procurement.id ? { ...p, status: 'completed' } : p);
        return { organized: updateList(prev.organized), participating: updateList(prev.participating) };
      });
      setPaymentProcurements((prev) => prev.filter((p) => p.id !== procurement.id));
      const completed = { ...procurement, status: 'completed' };
      setProcurementHistory((prev) => [completed, ...prev.filter((p) => p.id !== procurement.id)]);
      addToast('Закупка завершена и перенесена в историю', 'success');
    } catch (err) {
      addToast(err.message || 'Ошибка закрытия закупки', 'error');
    }
  };

  const handleLoadNewsFeed = async () => {
    setNewsFeedLoading(true);
    try {
      const result = await api.getProcurements({ status: 'active' }).catch(() => null);
      const list = result ? (result.results || result) : [];
      setNewsFeed(list.slice(0, 20).map((p) => ({
        id: p.id,
        title: p.title,
        author: p.organizer_name || `Организатор #${p.organizer}`,
        text: p.description || `Закупка в ${p.city || '...'}`,
        date: p.created_at,
        type: 'procurement',
        procurement_id: p.id,
      })));
    } catch {
      setNewsFeed([]);
    } finally {
      setNewsFeedLoading(false);
    }
  };

  const handleOpenPending = async () => {
    setActiveSection(activeSection === 'pending' ? null : 'pending');
    if (activeSection !== 'pending' && !pendingLoaded) {
      setPendingLoaded(true);
      try {
        const waiting = myProcurements?.organized?.filter((p) => p.status === 'stopped') || [];
        setPendingItems(waiting);
      } catch {
        // ignore
      }
    }
  };

  const handleOpenOrderTables = async () => {
    setActiveSection(activeSection === 'orderTables' ? null : 'orderTables');
    if (activeSection !== 'orderTables' && orderTables.length === 0) {
      try {
        const completed = myProcurements?.organized?.filter((p) => ['payment', 'completed', 'stopped'].includes(p.status)) || [];
        const tables = await Promise.all(
          completed.map((p) =>
            api.getReceiptTable(p.id)
              .then((t) => ({ ...t, procurement_title: p.title, procurement_id: p.id }))
              .catch(() => null)
          )
        );
        setOrderTables(tables.filter(Boolean));
      } catch {
        // ignore
      }
    }
  };

  const handleCarouselSelect = (cat) => {
    setSelectedCarouselCategory(selectedCarouselCategory?.id === cat.id ? null : cat);
  };

  const handleOpenEditors = async (procurement) => {
    setEditorsProcurement(procurement);
    setEditorsModalOpen(true);
    setEditorSearchQuery('');
    setEditorSearchResults([]);
    setEditorsLoading(true);
    try {
      const resp = await api.getPurchaseEditors(procurement.id);
      setEditorsList(resp.data || []);
    } catch {
      setEditorsList([]);
    } finally {
      setEditorsLoading(false);
    }
  };

  const handleEditorSearch = (query) => {
    setEditorSearchQuery(query);
    if (editorSearchTimeout.current) clearTimeout(editorSearchTimeout.current);
    if (!query.trim()) { setEditorSearchResults([]); return; }
    editorSearchTimeout.current = setTimeout(async () => {
      setEditorSearchLoading(true);
      try {
        const results = await api.searchUsers(query);
        setEditorSearchResults(Array.isArray(results) ? results : (results.results || []));
      } catch {
        setEditorSearchResults([]);
      } finally {
        setEditorSearchLoading(false);
      }
    }, 400);
  };

  const handleAddEditor = async (targetUser) => {
    if (!editorsProcurement) return;
    try {
      const resp = await api.addPurchaseEditor(editorsProcurement.id, targetUser.id);
      setEditorsList((prev) => [...prev.filter((e) => e.userId !== targetUser.id), resp.data]);
      addToast(`${targetUser.first_name || 'Пользователь'} добавлен как редактор`, 'success');
      setEditorSearchQuery('');
      setEditorSearchResults([]);
    } catch (err) {
      addToast(err.message || 'Ошибка добавления редактора', 'error');
    }
  };

  const handleRemoveEditor = async (editorUserId) => {
    if (!editorsProcurement) return;
    try {
      await api.removePurchaseEditor(editorsProcurement.id, editorUserId);
      setEditorsList((prev) => prev.filter((e) => e.userId !== editorUserId));
      addToast('Редактор удалён', 'success');
    } catch (err) {
      addToast(err.message || 'Ошибка удаления редактора', 'error');
    }
  };

  const handleOpenAddParticipant = (procurement) => {
    setAddParticipantProcurement(procurement);
    setAddParticipantOpen(true);
    setAddParticipantUserQuery('');
    setAddParticipantResults([]);
    setAddParticipantSelected(null);
    setAddParticipantAmount('');
    setAddParticipantQuantity('1');
  };

  const handleAddParticipantSearch = (query) => {
    setAddParticipantUserQuery(query);
    setAddParticipantSelected(null);
    if (addParticipantSearchTimeout.current) clearTimeout(addParticipantSearchTimeout.current);
    if (!query.trim()) { setAddParticipantResults([]); return; }
    addParticipantSearchTimeout.current = setTimeout(async () => {
      setAddParticipantLoading(true);
      try {
        const results = await api.searchUsers(query);
        setAddParticipantResults(Array.isArray(results) ? results : (results.results || []));
      } catch {
        setAddParticipantResults([]);
      } finally {
        setAddParticipantLoading(false);
      }
    }, 400);
  };

  const handleAddParticipantSubmit = async () => {
    if (!addParticipantSelected || !addParticipantAmount || !addParticipantProcurement) return;
    try {
      await api.addParticipant(addParticipantProcurement.id, {
        organizer_id: user.coreId || user.id,
        user_id: addParticipantSelected.id,
        quantity: parseFloat(addParticipantQuantity) || 1,
        amount: parseFloat(addParticipantAmount),
      });
      addToast(`Пользователь ${addParticipantSelected.first_name || ''} добавлен в закупку`, 'success');
      setAddParticipantOpen(false);
    } catch (err) {
      addToast(err.message || 'Ошибка добавления участника', 'error');
    }
  };

  const handleOpenInvite = (procurement) => {
    setInviteProcurement(procurement);
    setInviteEmail('');
    setInviteOpen(true);
  };

  const handleInviteSubmit = async () => {
    if (!inviteEmail.trim() || !inviteProcurement) return;
    setInviteLoading(true);
    try {
      await api.inviteUser(inviteProcurement.id, inviteEmail.trim(), user.coreId || user.id);
      addToast(`Приглашение отправлено на ${inviteEmail.trim()}`, 'success');
      setInviteOpen(false);
    } catch (err) {
      addToast(err.message || 'Ошибка отправки приглашения', 'error');
    } finally {
      setInviteLoading(false);
    }
  };

  const handleUserSearch = (query) => {
    setUserSearchQuery(query);
    if (userSearchTimeout.current) clearTimeout(userSearchTimeout.current);
    if (!query.trim()) { setUserSearchResults([]); return; }
    userSearchTimeout.current = setTimeout(async () => {
      setUserSearchLoading(true);
      try {
        const results = await api.searchUsers(query);
        setUserSearchResults(Array.isArray(results) ? results : (results.results || []));
      } catch {
        setUserSearchResults([]);
      } finally {
        setUserSearchLoading(false);
      }
    }, 400);
  };

  const toggleSection = (id) => setActiveSection((prev) => (prev === id ? null : id));

  // ─── Section renderers ─────────────────────────────────────────────────────

  const renderMessages = () => (
    <ContentPanel>
      {messages.length === 0 ? (
        <p className="lk-purchase-stats" style={{ padding: '4px 0' }}>Нет сообщений</p>
      ) : (
        <div className="lk-messages-list">
          {messages.map((m) => (
            <div key={m.id}>
              <div
                className="lk-message-item"
                onClick={() => { handleMarkMessageRead(m); setReplyTarget(m); }}
                style={!m.read ? { background: 'rgba(36,129,204,0.06)', borderLeft: '3px solid var(--tg-primary)' } : undefined}
              >
                <div className="lk-message-avatar" style={{ background: getAvatarColor(m.from) }}>
                  {getInitials(m.from, '')}
                </div>
                <div className="lk-message-info">
                  <div className="lk-message-row">
                    <span className="lk-message-name">{m.from}</span>
                    <span className="lk-message-time">{formatTime(m.date)}</span>
                  </div>
                  <div className="lk-message-text">{m.text}</div>
                </div>
                {!m.read && <span className="lk-message-badge">!</span>}
              </div>
              {replyTarget?.id === m.id && (
                <div style={{ marginTop: 4, display: 'flex', gap: 6, padding: '0 4px' }}>
                  <input
                    type="text"
                    className="lk-search-input"
                    style={{ flex: 1, borderRadius: 8, paddingLeft: 12 }}
                    placeholder="Написать ответ..."
                    value={replyText}
                    onChange={(e) => setReplyText(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleReplyMessage()}
                    autoFocus
                  />
                  <button className="lk-btn-invite-accept" style={{ fontSize: '0.8rem', padding: '6px 12px' }} onClick={handleReplyMessage}>
                    Отправить
                  </button>
                  <button className="lk-category-panel-close" onClick={() => { setReplyTarget(null); setReplyText(''); }}>
                    ×
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </ContentPanel>
  );

  const renderInvitations = () => (
    <ContentPanel>
      {invitations.length === 0 ? (
        <p className="lk-purchase-stats" style={{ padding: '4px 0' }}>Нет новых приглашений</p>
      ) : (
        <div className="lk-messages-list">
          {invitations.map((inv) => (
            <div
              key={inv.id}
              className="lk-message-item"
              onClick={() => {
                handleMarkInvitationRead(inv.id);
                if (inv.procurement_id) navigate(`/chat/${inv.procurement_id}`);
              }}
              style={!inv.read ? { background: 'rgba(36,129,204,0.06)', borderLeft: '3px solid var(--tg-primary)' } : undefined}
            >
              <div className="lk-message-avatar" style={{ background: getAvatarColor(inv.from) }}>
                {getInitials(inv.from, '')}
              </div>
              <div className="lk-message-info">
                <div className="lk-message-row">
                  <span className="lk-message-name">{inv.from}</span>
                  <span className="lk-message-time">{formatTime(inv.date)}</span>
                </div>
                <div className="lk-message-text">{inv.text}</div>
              </div>
              {inv.procurement_id ? (
                <button className="lk-btn-invite-accept" onClick={(e) => { e.stopPropagation(); navigate(`/chat/${inv.procurement_id}`); }}>
                  Принять
                </button>
              ) : (
                !inv.read && <span className="lk-message-badge">!</span>
              )}
            </div>
          ))}
        </div>
      )}
    </ContentPanel>
  );

  const renderCurrentPurchases = () => {
    const activeProcs = [
      ...(myProcurements?.organized || []),
      ...(myProcurements?.participating || []),
    ].filter((p) => ['active', 'stopped', 'payment'].includes(p.status));

    return (
      <ContentPanel>
        {procurementsLoading ? (
          <p className="lk-purchase-stats" style={{ padding: '4px 0' }}>Загрузка...</p>
        ) : activeProcs.length === 0 ? (
          <p className="lk-purchase-stats" style={{ padding: '4px 0' }}>Нет активных закупок</p>
        ) : (
          activeProcs.map((p) => {
            const progress = p.target_amount ? Math.round((p.current_amount / p.target_amount) * 100) : 0;
            return (
              <div key={p.id} className="lk-purchase-item" onClick={() => navigate(`/chat/${p.id}`)}>
                <div className="lk-purchase-icon" style={{ background: getAvatarColor(p.title || '') }}>
                  {getInitials(p.title || '', '')}
                </div>
                <div className="lk-purchase-info">
                  <div className="lk-purchase-name">{p.title}</div>
                  <div className="lk-purchase-meta">
                    {p.participant_count || 0} участников{p.participation_deadline ? ` · Дедлайн: ${formatTime(p.participation_deadline)}` : ''}
                  </div>
                  <div className="lk-purchase-progress-bar">
                    <div className="lk-purchase-progress-fill" style={{ width: `${Math.min(progress, 100)}%` }} />
                  </div>
                  <div className="lk-purchase-stats">
                    {progress}% собрано · {formatCurrency(p.current_amount || 0)} из {formatCurrency(p.target_amount || 0)}
                  </div>
                </div>
              </div>
            );
          })
        )}
      </ContentPanel>
    );
  };

  const renderPurchaseHistory = () => (
    <ContentPanel>
      {procurementHistory.length === 0 ? (
        <p className="lk-purchase-stats" style={{ padding: '4px 0' }}>История закупок пуста</p>
      ) : (
        procurementHistory.map((p) => (
          <div key={p.id} className="lk-purchase-item" style={{ cursor: 'default' }}>
            <div className="lk-purchase-icon" style={{ background: p.status === 'completed' ? '#4fae4e' : '#e17076' }}>
              {p.status === 'completed' ? '✓' : '✗'}
            </div>
            <div className="lk-purchase-info">
              <div className="lk-purchase-name">{p.title}</div>
              <div className="lk-purchase-meta">
                Завершено: {formatTime(p.updated_at)}
              </div>
              <div className="lk-purchase-stats" style={p.status === 'completed' ? { color: '#4fae4e' } : undefined}>
                {p.status === 'completed' ? '✓ Успешно' : '✗ Отменена'} · {formatCurrency(p.current_amount || 0)}
              </div>
            </div>
            {user.role === 'organizer' && p.organizer === (user.coreId || user.id) && (
              <select
                value={p.status}
                onChange={(e) => handleProcurementStatusChange(p.id, e.target.value)}
                className="lk-search-input"
                style={{ width: 'auto', padding: '2px 6px', borderRadius: 6, border: '1px solid var(--tg-border-light)' }}
              >
                {[
                  { value: 'draft', label: 'Черновик' },
                  { value: 'active', label: 'Активная' },
                  { value: 'stopped', label: 'Остановлена' },
                  { value: 'payment', label: 'Оплата' },
                  { value: 'completed', label: 'Завершена' },
                  { value: 'cancelled', label: 'Отменена' },
                ].map((opt) => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
              </select>
            )}
          </div>
        ))
      )}
    </ContentPanel>
  );

  const renderSubscriptions = () => (
    <ContentPanel>
      <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
        <input
          type="text"
          className="lk-search-input"
          style={{ flex: 1, paddingLeft: 12, borderRadius: 8 }}
          placeholder="Категория или организатор..."
          value={newSubscription}
          onChange={(e) => setNewSubscription(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleAddSubscription()}
        />
        <button className="lk-btn-invite-accept" onClick={handleAddSubscription}>+ Добавить</button>
      </div>
      {subscriptions.map((s) => (
        <div key={s.id} className="lk-message-item" style={{ cursor: 'default' }}>
          <span className="lk-message-name" style={{ flex: 1 }}>
            {s.type === 'organizer' ? '👤' : '🏷️'} {s.name}
          </span>
          <button
            className={`lk-btn-invite-accept`}
            style={s.active ? {} : { background: 'var(--tg-bg-secondary)', color: 'var(--tg-text-secondary)', border: '1px solid var(--tg-border-light)' }}
            onClick={() => handleToggleSubscription(s.id)}
          >
            {s.active ? 'Вкл' : 'Выкл'}
          </button>
          <button className="lk-category-panel-close" onClick={() => handleDeleteSubscription(s.id)}>×</button>
        </div>
      ))}
    </ContentPanel>
  );

  const renderUserSearch = () => (
    <ContentPanel>
      <input
        type="text"
        className="lk-search-input"
        style={{ marginBottom: 8, paddingLeft: 12, borderRadius: 8 }}
        placeholder="Имя, email, телефон..."
        value={userSearchQuery}
        onChange={(e) => handleUserSearch(e.target.value)}
      />
      {userSearchLoading && <p className="lk-purchase-stats">Поиск...</p>}
      {!userSearchLoading && userSearchQuery.trim() && userSearchResults.length === 0 && (
        <p className="lk-purchase-stats">Пользователи не найдены</p>
      )}
      <div className="lk-messages-list">
        {userSearchResults.map((u) => (
          <div key={u.id} className="lk-message-item" style={{ cursor: 'default' }}>
            <div className="lk-message-avatar" style={{ background: getAvatarColor(u.first_name || ''), width: 36, height: 36, fontSize: 13 }}>
              {getInitials(u.first_name, u.last_name)}
            </div>
            <div className="lk-message-info">
              <div className="lk-message-name">{u.first_name || ''} {u.last_name || ''}</div>
              <div className="lk-message-text">
                {u.username ? `@${u.username}` : u.email || u.phone || getRoleText(u.role)}
              </div>
            </div>
            <span className="lk-message-badge" style={{ background: 'rgba(36,129,204,0.12)', color: 'var(--tg-primary)', fontSize: 11 }}>
              {getRoleText(u.role)}
            </span>
          </div>
        ))}
      </div>
    </ContentPanel>
  );

  const renderMyProcurements = () => {
    const procs = myProcurements?.organized || [];
    return (
      <ContentPanel>
        {procurementsLoading ? (
          <p className="lk-purchase-stats" style={{ padding: '4px 0' }}>Загрузка...</p>
        ) : procs.length === 0 ? (
          <p className="lk-purchase-stats" style={{ padding: '4px 0' }}>Нет закупок</p>
        ) : (
          procs.map((p) => (
            <div key={p.id} className="lk-purchase-item" style={{ flexDirection: 'column', alignItems: 'stretch' }}>
              <div className="lk-purchase-name" style={{ cursor: 'pointer' }} onClick={() => navigate(`/chat/${p.id}`)}>
                {p.title}
              </div>
              <div className="lk-purchase-meta">
                {p.city} · {p.participant_count || 0} участн. · {formatCurrency(p.current_amount || 0)}
              </div>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
                <select
                  value={p.status}
                  onChange={(e) => handleProcurementStatusChange(p.id, e.target.value)}
                  className="lk-search-input"
                  style={{ width: 'auto', padding: '2px 6px', borderRadius: 6, border: '1px solid var(--tg-border-light)' }}
                >
                  {[
                    { value: 'draft', label: 'Черновик' },
                    { value: 'active', label: 'Активная' },
                    { value: 'stopped', label: 'Остановлена' },
                    { value: 'payment', label: 'Оплата' },
                    { value: 'completed', label: 'Завершена' },
                    { value: 'cancelled', label: 'Отменена' },
                  ].map((opt) => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
                </select>
                {p.organizer === (user?.coreId || user?.id) && p.status === 'active' && (
                  <button className="lk-btn-invite-accept" style={{ fontSize: '0.7rem', padding: '2px 8px' }} onClick={() => handleOpenAddParticipant(p)}>
                    + Добавить участника
                  </button>
                )}
                {p.organizer === (user?.coreId || user?.id) && p.status === 'active' && (
                  <button className="lk-btn-invite-accept" style={{ fontSize: '0.7rem', padding: '2px 8px' }} onClick={() => handleOpenInvite(p)}>
                    Пригласить
                  </button>
                )}
                {p.organizer === (user?.coreId || user?.id) && (
                  <button className="lk-btn-invite-accept" style={{ fontSize: '0.7rem', padding: '2px 8px', background: 'var(--tg-bg-secondary)', color: 'var(--tg-primary)', border: '1px solid var(--tg-primary)' }} onClick={() => handleOpenEditors(p)}>
                    👥 Редакторы
                  </button>
                )}
              </div>
            </div>
          ))
        )}
      </ContentPanel>
    );
  };

  const renderPaymentProcurements = () => (
    <ContentPanel>
      {paymentProcurements.length === 0 ? (
        <p className="lk-purchase-stats" style={{ padding: '4px 0' }}>Нет закупок в стадии оплаты</p>
      ) : (
        paymentProcurements.map((p) => (
          <div key={p.id} className="lk-purchase-item" style={{ flexDirection: 'column', alignItems: 'stretch' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 4 }}>
              <span className="lk-purchase-name" style={{ cursor: 'pointer', flex: 1 }} onClick={() => navigate(`/chat/${p.id}`)}>
                {p.title}
              </span>
              <span className={`status-badge status-${p.status}`} style={{ fontSize: '0.65rem', flexShrink: 0, marginLeft: 6 }}>
                {getStatusText(p.status)}
              </span>
            </div>
            <div className="lk-purchase-meta">
              {p.city} · {p.participant_count || 0} участн. · {formatCurrency(p.current_amount || 0)}
              {p.participation_deadline && ` · до ${formatTime(p.participation_deadline)}`}
            </div>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {p.status === 'active' && (
                <button className="lk-btn-invite-accept" style={{ fontSize: '0.7rem', padding: '3px 8px', background: 'var(--tg-bg-secondary)', color: 'var(--tg-primary)', border: '1px solid var(--tg-primary)' }} onClick={() => handleStopProcurement(p)}>
                  Стоп-сумма
                </button>
              )}
              {(p.status === 'active' || p.status === 'stopped') && (
                <button className="lk-btn-invite-accept" style={{ fontSize: '0.7rem', padding: '3px 8px', background: 'var(--tg-bg-secondary)', color: 'var(--tg-primary)', border: '1px solid var(--tg-primary)' }} onClick={() => handleOpenApproveSupplier(p)}>
                  Одобрить поставщика
                </button>
              )}
              {(p.status === 'stopped' || p.status === 'payment') && (
                <button className="lk-btn-invite-accept" style={{ fontSize: '0.7rem', padding: '3px 8px', background: 'var(--tg-bg-secondary)', color: 'var(--tg-primary)', border: '1px solid var(--tg-primary)' }} onClick={() => handleCreateReceiptTable(p)}>
                  Создать таблицу
                </button>
              )}
              {(p.status === 'stopped' || p.status === 'payment') && (
                <button className="lk-btn-invite-accept" style={{ fontSize: '0.7rem', padding: '3px 8px', background: 'var(--tg-bg-secondary)', color: 'var(--tg-error)', border: '1px solid var(--tg-error)' }} onClick={() => handleCloseProcurement(p)}>
                  Закрыть закупку
                </button>
              )}
            </div>
          </div>
        ))
      )}
    </ContentPanel>
  );

  const renderShipmentHistory = () => {
    const completedShipments = myProcurements?.organized?.filter((p) => p.status === 'completed') || [];
    return (
      <ContentPanel>
        {completedShipments.length === 0 ? (
          <p className="lk-purchase-stats" style={{ padding: '4px 0' }}>История отгрузок пуста</p>
        ) : (
          completedShipments.map((p) => (
            <div key={p.id} className="lk-purchase-item" style={{ cursor: 'default' }}>
              <div className="lk-purchase-icon" style={{ background: '#4fae4e' }}>✓</div>
              <div className="lk-purchase-info">
                <div className="lk-purchase-name">{p.title}</div>
                <div className="lk-purchase-meta">
                  {p.city} · {formatCurrency(p.current_amount || 0)} · {formatTime(p.updated_at)}
                </div>
                <span className="status-badge status-completed" style={{ fontSize: '0.65rem' }}>Завершена</span>
              </div>
            </div>
          ))
        )}
      </ContentPanel>
    );
  };

  // ─── Role-specific sections ────────────────────────────────────────────────

  const renderRoleRows = () => {
    const role = user.role;
    const unreadCount = messages.filter((m) => !m.read).length;
    const activeProcCount = [
      ...(myProcurements?.organized || []),
      ...(myProcurements?.participating || []),
    ].filter((p) => ['active', 'stopped', 'payment'].includes(p.status)).length;

    if (role === 'organizer') {
      return (
        <>
          <SectionHeader title="Закупки" />
          <div className="lk-section-group">
            <ActionRow icon={<PlusIcon />} label="Создать закупку" onClick={openCreateProcurementModal} />
            <ActionRow icon={<ShoppingBagIcon />} label="Открытые закупки" badge={myProcurements?.organized?.filter((p) => p.status === 'active' || p.status === 'draft').length || 0} onClick={() => toggleSection('myProcurements')} />
            {activeSection === 'myProcurements' && renderMyProcurements()}
            <ActionRow icon={<ShoppingBagIcon />} label="Закупки в стадии оплаты" badge={paymentProcurements.length} onClick={() => toggleSection('paymentProcurements')} />
            {activeSection === 'paymentProcurements' && renderPaymentProcurements()}
            <ActionRow icon={<HistoryIcon />} label="История закупок" badge={procurementHistory.length} onClick={() => toggleSection('history')} />
            {activeSection === 'history' && renderPurchaseHistory()}
            <ActionRow icon={<PlusIcon />} label="Создать новость" onClick={() => setNewsOpen(true)} />
          </div>
          <SectionHeader title="Коммуникация" />
          <div className="lk-section-group">
            <ActionRow icon={<MailIcon />} label="Сообщения" badge={unreadCount} onClick={() => toggleSection('messages')} />
            {activeSection === 'messages' && renderMessages()}
            <ActionRow icon={<SearchIcon />} label="Поиск пользователей" onClick={() => toggleSection('userSearch')} />
            {activeSection === 'userSearch' && renderUserSearch()}
          </div>
        </>
      );
    }

    if (role === 'supplier') {
      return (
        <>
          <SectionHeader title="Отгрузки" />
          <div className="lk-section-group">
            <ActionRow icon={<HomeIcon />} label="Карточка компании" onClick={() => setCompanyCardOpen(true)} />
            <ActionRow icon={<FileIcon />} label="Загрузить прайс-лист" onClick={() => setPriceListOpen(true)} />
            <ActionRow icon={<ShoppingBagIcon />} label="Текущие отгрузки" badge={orderTables.length} onClick={handleOpenOrderTables} />
            {activeSection === 'orderTables' && (
              <ContentPanel>
                {orderTables.length === 0 ? (
                  <p className="lk-purchase-stats">Нет текущих отгрузок</p>
                ) : (
                  orderTables.map((table, idx) => (
                    <div key={idx} className="lk-purchase-item" style={{ flexDirection: 'column', alignItems: 'stretch' }}>
                      <div className="lk-purchase-name">{table.procurement_title}</div>
                      {table.total_amount && <div className="lk-purchase-meta">Сумма: {formatCurrency(table.total_amount)}</div>}
                      <button className="lk-btn-invite-accept" style={{ fontSize: '0.75rem', padding: '4px 10px', alignSelf: 'flex-start', marginTop: 6 }} onClick={() => { setSelectedOrderTableId(table.procurement_id); setClosingDocsOpen(true); }}>
                        Отправить закрывающие документы
                      </button>
                    </div>
                  ))
                )}
              </ContentPanel>
            )}
            <ActionRow icon={<HistoryIcon />} label="В ожидании" badge={pendingItems.length} onClick={handleOpenPending} />
            {activeSection === 'pending' && (
              <ContentPanel>
                {pendingItems.length === 0 ? (
                  <p className="lk-purchase-stats">Нет закупок в ожидании</p>
                ) : (
                  pendingItems.map((p) => (
                    <div key={p.id} className="lk-purchase-item" onClick={() => navigate(`/chat/${p.id}`)}>
                      <div className="lk-purchase-icon" style={{ background: getAvatarColor(p.title || '') }}>
                        {getInitials(p.title || '', '')}
                      </div>
                      <div className="lk-purchase-info">
                        <div className="lk-purchase-name">{p.title}</div>
                        <div className="lk-purchase-meta">{p.city} · {p.participant_count || 0} участн.</div>
                      </div>
                    </div>
                  ))
                )}
              </ContentPanel>
            )}
            <ActionRow icon={<HistoryIcon />} label="История отгрузок" badge={myProcurements?.organized?.filter((p) => p.status === 'completed').length || 0} onClick={() => toggleSection('shipmentHistory')} />
            {activeSection === 'shipmentHistory' && renderShipmentHistory()}
          </div>
          <SectionHeader title="Коммуникация" />
          <div className="lk-section-group">
            <ActionRow icon={<MailIcon />} label="Приглашения и сообщения" badge={unreadCount} onClick={() => toggleSection('messages')} />
            {activeSection === 'messages' && renderMessages()}
            <ActionRow icon={<SearchIcon />} label="Поиск пользователей" onClick={() => toggleSection('userSearch')} />
            {activeSection === 'userSearch' && renderUserSearch()}
            <ActionRow icon={<PlusIcon />} label="Написать в ленту новостей" onClick={() => setNewsOpen(true)} />
          </div>
        </>
      );
    }

    // Buyer
    const unreadInvitations = invitations.filter((inv) => !inv.read).length;
    return (
      <>
        <SectionHeader title="Закупки" />
        <div className="lk-section-group">
          <ActionRow icon={<ShoppingBagIcon />} label="Текущие закупки" badge={activeProcCount} onClick={() => toggleSection('currentPurchases')} />
          {activeSection === 'currentPurchases' && renderCurrentPurchases()}
          <ActionRow icon={<HistoryIcon />} label="История закупок" badge={procurementHistory.length} onClick={() => toggleSection('history')} />
          {activeSection === 'history' && renderPurchaseHistory()}
          <ActionRow icon={<PlusIcon />} label="Создать запрос" onClick={() => setCreateRequestOpen(true)} />
          <ActionRow icon={<RequestsIcon />} label="Мои запросы" badge={myRequests.length} onClick={() => toggleSection('myRequests')} />
          {activeSection === 'myRequests' && (
            <ContentPanel>
              <button className="lk-btn-invite-accept" style={{ marginBottom: 8 }} onClick={() => setCreateRequestOpen(true)}>
                + Создать запрос
              </button>
              {myRequests.length === 0 ? (
                <p className="lk-purchase-stats">Нет активных запросов</p>
              ) : (
                myRequests.map((req) => (
                  <div key={req.id} className="lk-purchase-item" style={{ flexDirection: 'column', alignItems: 'stretch' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                      <div className="lk-purchase-name">{req.product_name}</div>
                      <button className="lk-category-panel-close" onClick={() => handleDeleteRequest(req.id)}>×</button>
                    </div>
                    <div className="lk-purchase-meta">Кол-во: {req.quantity} · {req.city}</div>
                    <div className="lk-purchase-stats">{formatTime(req.created_at)}</div>
                  </div>
                ))
              )}
            </ContentPanel>
          )}
        </div>
        <SectionHeader title="Мои приглашения и сообщения" />
        <div className="lk-section-group">
          <ActionRow icon={<InvitationIcon />} label="Приглашения в закупки" badge={unreadInvitations} onClick={() => toggleSection('invitations')} />
          {activeSection === 'invitations' && renderInvitations()}
          <ActionRow icon={<MailIcon />} label="Сообщения" badge={unreadCount} onClick={() => toggleSection('messages')} />
          {activeSection === 'messages' && renderMessages()}
        </div>
      </>
    );
  };

  // ─── Not logged in ─────────────────────────────────────────────────────────

  if (!user) {
    return (
      <div className="lk-root" style={{ alignItems: 'center', justifyContent: 'center', gap: '1rem' }}>
        <p style={{ color: 'var(--tg-text-muted)' }}>Войдите для доступа к личному кабинету</p>
        <button className="lk-btn-action" style={{ width: 'auto', flex: 'none', padding: '0 24px' }} onClick={openLoginModal}>
          Войти / Зарегистрироваться
        </button>
      </div>
    );
  }

  // ─── Main render ───────────────────────────────────────────────────────────

  return (
    <div className="lk-root">
      {/* ═══ CATEGORY SLIDER ═══ */}
      <div className="lk-topbar">
        {/* Horizontal slider carousel (7 cards) */}
        <div className="lk-slider-wrapper">
          <div
            className="lk-slider-track"
            ref={sliderTrackRef}
          >
            {LC_SLIDER_CATEGORIES.map((cat) => (
              <div
                key={cat.id}
                className={`lk-card${selectedCarouselCategory?.id === cat.id ? ' active' : ''}`}
                onClick={() => handleCarouselSelect(cat)}
              >
                <div className="lk-card-title">{cat.label}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ═══ SCROLLABLE BODY ═══ */}
      <div className="lk-body">
        {/* Category panel (shown below topbar when a card is selected) */}
        {selectedCarouselCategory && (
          <div className="lk-category-panel">
            <div className="lk-category-panel-header">
              <span className="lk-category-panel-title">
                {selectedCarouselCategory.label}
              </span>
              <button className="lk-category-panel-close" onClick={() => setSelectedCarouselCategory(null)}>×</button>
            </div>
            <CategoryPageContent
              category={selectedCarouselCategory}
              procurements={myProcurements}
              user={user}
              newsFeed={newsFeed}
              newsFeedLoading={newsFeedLoading}
              onLoadNewsFeed={handleLoadNewsFeed}
              navigate={navigate}
            />
          </div>
        )}

        {/* Search bar */}
        <div className="lk-section-block lk-search-section">
          <div className="lk-search-bar" style={{ margin: 0 }}>
            <div className="lk-search-bar-icon"><SearchIcon /></div>
            <input
              type="text"
              className="lk-search-input"
              placeholder="Поиск..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
        </div>

        {/* Two-panel chat section (Telegram-style) */}
        <div className="lk-section-block" style={{ padding: 0 }}>
          <CabinetChatSection />
        </div>

        {/* Messages section */}
        {messages.length > 0 && (
          <div className="lk-section-block">
            <div className="lk-section-title">Сообщения</div>
            <div className="lk-messages-list">
              {messages.slice(0, 3).map((m) => (
                <div
                  key={m.id}
                  className="lk-message-item"
                  onClick={() => { handleMarkMessageRead(m); setReplyTarget(m); }}
                >
                  <div className="lk-message-avatar" style={{ background: getAvatarColor(m.from) }}>
                    {getInitials(m.from, '')}
                  </div>
                  <div className="lk-message-info">
                    <div className="lk-message-row">
                      <span className="lk-message-name">{m.from}</span>
                      <span className="lk-message-time">{formatTime(m.date)}</span>
                    </div>
                    <div className="lk-message-text">{m.text}</div>
                  </div>
                  {!m.read && <span className="lk-message-badge">!</span>}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Bottom spacing */}
        <div style={{ height: 24 }} />
      </div>

      {/* ═══ MODALS ═══ */}

      <CompanyCardModal isOpen={companyCardOpen} onClose={() => setCompanyCardOpen(false)} onSave={handleSaveCompanyCard} />
      <PriceListModal isOpen={priceListOpen} onClose={() => setPriceListOpen(false)} onSave={handleSavePriceList} />
      <NewsModal isOpen={newsOpen} onClose={() => setNewsOpen(false)} onSave={handleSaveNews} />
<CreateRequestModal isOpen={createRequestOpen} onClose={() => setCreateRequestOpen(false)} onSave={handleSaveRequest} />
      <ClosingDocumentsModal isOpen={closingDocsOpen} onClose={() => setClosingDocsOpen(false)} onSave={handleSendClosingDocuments} orderTableId={selectedOrderTableId} />

      {/* Approve Supplier modal */}
      {approveSupplierOpen && (
        <div className="modal-overlay active" onClick={(e) => e.target === e.currentTarget && setApproveSupplierOpen(false)}>
          <div className="modal" style={{ maxWidth: 380 }}>
            <div className="modal-header">
              <h3 className="modal-title">Одобрить поставщика</h3>
              <button className="modal-close" onClick={() => setApproveSupplierOpen(false)}>×</button>
            </div>
            <div className="modal-body" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {approveSupplierProcurement && (
                <p className="lk-purchase-meta" style={{ margin: 0 }}>
                  Закупка: <strong>{approveSupplierProcurement.title}</strong>
                </p>
              )}
              <div>
                <label className="lk-purchase-stats" style={{ display: 'block', marginBottom: 4 }}>Поиск поставщика</label>
                <input
                  type="text"
                  className="lk-search-input"
                  style={{ paddingLeft: 12, borderRadius: 8 }}
                  placeholder="Имя, компания, email..."
                  value={supplierSearchQuery}
                  onChange={(e) => handleSupplierSearch(e.target.value)}
                  autoFocus
                />
                {supplierSearchLoading && <p className="lk-purchase-stats" style={{ marginTop: 4 }}>Поиск...</p>}
                {supplierSearchResults.length > 0 && (
                  <div className="lk-messages-list" style={{ border: '1px solid var(--tg-border-light)', borderRadius: 8, marginTop: 4, overflow: 'hidden' }}>
                    {supplierSearchResults.map((s) => (
                      <div
                        key={s.id}
                        className="lk-message-item"
                        onClick={() => handleApproveSupplierSubmit(s)}
                        style={{ padding: '8px 12px' }}
                      >
                        <div className="lk-message-info">
                          <div className="lk-message-name">{s.first_name || ''} {s.last_name || ''}</div>
                          <div className="lk-message-text">{s.email || s.phone || 'Поставщик'}</div>
                        </div>
                        <span className="lk-message-badge" style={{ background: 'rgba(36,129,204,0.12)', color: 'var(--tg-primary)', fontSize: 11 }}>
                          Одобрить
                        </span>
                      </div>
                    ))}
                  </div>
                )}
                {!supplierSearchLoading && supplierSearchQuery.trim() && supplierSearchResults.length === 0 && (
                  <p className="lk-purchase-stats" style={{ marginTop: 4 }}>Поставщики не найдены</p>
                )}
              </div>
              <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                <button className="lk-btn-action lk-btn-action--outline" style={{ height: 36, flex: 'none', padding: '0 16px' }} onClick={() => setApproveSupplierOpen(false)}>Отмена</button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Add participant modal */}
      {addParticipantOpen && (
        <div className="modal-overlay active" onClick={(e) => e.target === e.currentTarget && setAddParticipantOpen(false)}>
          <div className="modal" style={{ maxWidth: 380 }}>
            <div className="modal-header">
              <h3 className="modal-title">Добавить участника в закупку</h3>
              <button className="modal-close" onClick={() => setAddParticipantOpen(false)}>×</button>
            </div>
            <div className="modal-body" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {addParticipantProcurement && (
                <p className="lk-purchase-meta" style={{ margin: 0 }}>
                  Закупка: <strong>{addParticipantProcurement.title}</strong>
                </p>
              )}
              <div>
                <label className="lk-purchase-stats" style={{ display: 'block', marginBottom: 4 }}>Поиск пользователя</label>
                <input
                  type="text"
                  className="lk-search-input"
                  style={{ paddingLeft: 12, borderRadius: 8 }}
                  placeholder="Имя, email, телефон..."
                  value={addParticipantUserQuery}
                  onChange={(e) => handleAddParticipantSearch(e.target.value)}
                  autoFocus
                />
                {addParticipantLoading && <p className="lk-purchase-stats" style={{ marginTop: 4 }}>Поиск...</p>}
                {addParticipantResults.length > 0 && !addParticipantSelected && (
                  <div className="lk-messages-list" style={{ border: '1px solid var(--tg-border-light)', borderRadius: 8, marginTop: 4, overflow: 'hidden' }}>
                    {addParticipantResults.map((u) => (
                      <div key={u.id} className="lk-message-item" style={{ padding: '8px 12px' }}
                        onClick={() => { setAddParticipantSelected(u); setAddParticipantUserQuery(`${u.first_name || ''} ${u.last_name || ''}`.trim()); setAddParticipantResults([]); }}>
                        <div className="lk-message-info">
                          <div className="lk-message-name">{u.first_name || ''} {u.last_name || ''}</div>
                          <div className="lk-message-text">{u.email || u.phone || getRoleText(u.role)}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
                {addParticipantSelected && (
                  <div style={{ marginTop: 4, fontSize: '0.75rem', color: 'var(--tg-success)' }}>
                    ✓ Выбран: {addParticipantSelected.first_name} {addParticipantSelected.last_name || ''}
                  </div>
                )}
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                <div style={{ flex: 1 }}>
                  <label className="lk-purchase-stats" style={{ display: 'block', marginBottom: 4 }}>Количество</label>
                  <input type="number" className="lk-search-input" style={{ paddingLeft: 12, borderRadius: 8 }} min="0.01" step="0.01" value={addParticipantQuantity} onChange={(e) => setAddParticipantQuantity(e.target.value)} />
                </div>
                <div style={{ flex: 1 }}>
                  <label className="lk-purchase-stats" style={{ display: 'block', marginBottom: 4 }}>Сумма (₽)</label>
                  <input type="number" className="lk-search-input" style={{ paddingLeft: 12, borderRadius: 8 }} min="0" step="0.01" placeholder="0.00" value={addParticipantAmount} onChange={(e) => setAddParticipantAmount(e.target.value)} />
                </div>
              </div>
              <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                <button className="lk-btn-action lk-btn-action--outline" style={{ height: 36, flex: 'none', padding: '0 16px' }} onClick={() => setAddParticipantOpen(false)}>Отмена</button>
                <button className="lk-btn-action" style={{ height: 36, flex: 'none', padding: '0 16px' }} disabled={!addParticipantSelected || !addParticipantAmount} onClick={handleAddParticipantSubmit}>Добавить</button>
              </div>
            </div>
          </div>
        </div>
      )}

      {inviteOpen && (
        <div className="modal-overlay active" onClick={(e) => e.target === e.currentTarget && setInviteOpen(false)}>
          <div className="modal" style={{ maxWidth: 360 }}>
            <div className="modal-header">
              <h3 className="modal-title">Пригласить пользователя</h3>
              <button className="modal-close" onClick={() => setInviteOpen(false)}>×</button>
            </div>
            <div className="modal-body" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {inviteProcurement && (
                <p className="lk-purchase-meta" style={{ margin: 0 }}>
                  Закупка: <strong>{inviteProcurement.title}</strong>
                </p>
              )}
              <div>
                <label className="lk-purchase-stats" style={{ display: 'block', marginBottom: 4 }}>Email пользователя</label>
                <input
                  type="email"
                  className="lk-search-input"
                  style={{ paddingLeft: 12, borderRadius: 8 }}
                  placeholder="example@email.com"
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleInviteSubmit()}
                  autoFocus
                />
              </div>
              <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                <button className="lk-btn-action lk-btn-action--outline" style={{ height: 36, flex: 'none', padding: '0 16px' }} onClick={() => setInviteOpen(false)}>Отмена</button>
                <button className="lk-btn-action" style={{ height: 36, flex: 'none', padding: '0 16px' }} disabled={!inviteEmail.trim() || inviteLoading} onClick={handleInviteSubmit}>
                  {inviteLoading ? 'Отправка...' : 'Пригласить'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Editors (shared access) modal */}
      {editorsModalOpen && (
        <div className="modal-overlay active" onClick={(e) => e.target === e.currentTarget && setEditorsModalOpen(false)}>
          <div className="modal" style={{ maxWidth: 420 }}>
            <div className="modal-header">
              <h3 className="modal-title">👥 Редакторы закупки</h3>
              <button className="modal-close" onClick={() => setEditorsModalOpen(false)}>×</button>
            </div>
            <div className="modal-body" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {editorsProcurement && (
                <p className="lk-purchase-meta" style={{ margin: 0 }}>
                  Закупка: <strong>{editorsProcurement.title}</strong>
                </p>
              )}
              <p className="lk-purchase-stats" style={{ margin: 0, fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                Редакторы могут просматривать, редактировать товары и цены, а также участвовать в чате. Отменить закупку или управлять другими редакторами может только владелец.
              </p>

              {/* Current editors list */}
              <div>
                <div className="lk-purchase-stats" style={{ fontWeight: 600, marginBottom: 6 }}>Текущие редакторы</div>
                {editorsLoading ? (
                  <p className="lk-purchase-stats">Загрузка...</p>
                ) : editorsList.length === 0 ? (
                  <p className="lk-purchase-stats">Редакторов нет</p>
                ) : (
                  <div className="lk-messages-list" style={{ border: '1px solid var(--tg-border-light)', borderRadius: 8, overflow: 'hidden', marginBottom: 4 }}>
                    {editorsList.map((e) => (
                      <div key={e.id} className="lk-message-item" style={{ padding: '8px 12px' }}>
                        <div className="lk-message-info">
                          <div className="lk-message-name">ID: {e.userId}</div>
                          <div className="lk-message-text" style={{ fontSize: '0.7rem' }}>
                            Роль: {e.role} · Добавлен: {new Date(e.createdAt).toLocaleDateString()}
                          </div>
                        </div>
                        <button
                          className="lk-category-panel-close"
                          style={{ color: 'var(--tg-error)', fontWeight: 700 }}
                          title="Удалить редактора"
                          onClick={() => handleRemoveEditor(e.userId)}
                        >
                          ×
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Add editor */}
              <div>
                <div className="lk-purchase-stats" style={{ fontWeight: 600, marginBottom: 6 }}>Добавить редактора</div>
                <input
                  type="text"
                  className="lk-search-input"
                  style={{ paddingLeft: 12, borderRadius: 8, marginBottom: 4 }}
                  placeholder="Поиск по имени, email, телефону..."
                  value={editorSearchQuery}
                  onChange={(e) => handleEditorSearch(e.target.value)}
                />
                {editorSearchLoading && <p className="lk-purchase-stats" style={{ marginTop: 4 }}>Поиск...</p>}
                {editorSearchResults.length > 0 && (
                  <div className="lk-messages-list" style={{ border: '1px solid var(--tg-border-light)', borderRadius: 8, overflow: 'hidden' }}>
                    {editorSearchResults.map((u) => (
                      <div key={u.id} className="lk-message-item" style={{ padding: '8px 12px', cursor: 'pointer' }}
                        onClick={() => handleAddEditor(u)}>
                        <div className="lk-message-avatar" style={{ background: getAvatarColor(u.first_name || ''), width: 32, height: 32, fontSize: 12, flexShrink: 0 }}>
                          {getInitials(u.first_name, u.last_name)}
                        </div>
                        <div className="lk-message-info">
                          <div className="lk-message-name">{u.first_name || ''} {u.last_name || ''}</div>
                          <div className="lk-message-text">{u.email || u.username || u.phone || getRoleText(u.role)}</div>
                        </div>
                        <span className="lk-message-badge" style={{ background: 'rgba(36,129,204,0.12)', color: 'var(--tg-primary)', fontSize: 11 }}>
                          + Добавить
                        </span>
                      </div>
                    ))}
                  </div>
                )}
                {!editorSearchLoading && editorSearchQuery.trim() && editorSearchResults.length === 0 && (
                  <p className="lk-purchase-stats" style={{ marginTop: 4 }}>Пользователи не найдены</p>
                )}
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                <button className="lk-btn-action lk-btn-action--outline" style={{ height: 36, flex: 'none', padding: '0 16px' }} onClick={() => setEditorsModalOpen(false)}>Закрыть</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default Cabinet;
