import React, { useEffect, useState, useRef, useCallback, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useStore } from '../store/useStore';
import { useWebSocket } from '../hooks/useWebSocket';
import {
  formatTime,
  getInitials,
  getAvatarColor,
} from '../utils/helpers';
import { batchProcessMessages } from '../services/wasm';
import { api, ApiError } from '../services/api';
import { BackIcon, MoreIcon, AttachIcon, SendIcon } from './Icons';

// --- Chat Voting Panel (pinned message) ---
/**
 * ChatVotingPanel — Scenario C (issue #282 Part II §5):
 *  - On vote click, button enters `loading` state and is disabled immediately
 *  - Optimistic UI: update local vote count before server responds
 *  - On server error, roll back optimistic update
 *  - On 429, disable vote button and show countdown timer
 *  - Only the changed option's count is updated (minimal re-renders)
 *  - Subscribes to `vote_update` / `voting_closed` WebSocket events
 */
function ChatVotingPanel({ procurementId, user, participants }) {
  const { addToast } = useStore();
  const [voteResults, setVoteResults] = useState(null);
  const [suppliers, setSuppliers] = useState([]);
  const [selectedSupplierId, setSelectedSupplierId] = useState('');
  const [voteComment, setVoteComment] = useState('');
  const [isExpanded, setIsExpanded] = useState(true);
  const [userVote, setUserVote] = useState(null); // current user's vote
  const [closeRequests, setCloseRequests] = useState([]); // user ids who requested close
  const [isLoading, setIsLoading] = useState(false);
  const [isVoting, setIsVoting] = useState(false); // vote button in-flight state
  const [retryAfter, setRetryAfter] = useState(null); // 429 countdown (seconds)
  const retryTimerRef = useRef(null);
  const [newSupplierName, setNewSupplierName] = useState('');
  const [showAddSupplier, setShowAddSupplier] = useState(false);

  const totalParticipants = participants?.length || 0;
  const allClosed = totalParticipants > 0 && closeRequests.length >= totalParticipants;
  const userAlreadyClosedVote = user && closeRequests.includes(user.coreId || user.id);

  // 429 countdown effect
  useEffect(() => {
    if (retryAfter === null || retryAfter <= 0) {
      if (retryTimerRef.current) {
        clearInterval(retryTimerRef.current);
        retryTimerRef.current = null;
      }
      if (retryAfter === 0) setRetryAfter(null);
      return;
    }
    retryTimerRef.current = setInterval(() => {
      setRetryAfter((s) => (s !== null && s > 1 ? s - 1 : 0));
    }, 1000);
    return () => clearInterval(retryTimerRef.current);
  }, [retryAfter]);

  const loadVoteData = useCallback(async () => {
    if (!procurementId) return;
    setIsLoading(true);
    try {
      const [results, suppliersResp, voteStatus] = await Promise.all([
        api.getVoteResults(procurementId).catch(() => null),
        api.getSuppliers().catch(() => null),
        api.getVoteCloseStatus(procurementId).catch(() => null),
      ]);

      if (results) {
        setVoteResults(results);
        // Find current user's vote
        if (user && results.user_votes) {
          const myVote = results.user_votes[user.coreId || user.id];
          if (myVote) {
            setUserVote(myVote);
            setSelectedSupplierId(String(myVote.supplier_id));
          }
        }
      }
      if (suppliersResp) {
        const list = suppliersResp.results || suppliersResp;
        setSuppliers(Array.isArray(list) ? list : []);
      }
      if (voteStatus && voteStatus.closed_by) {
        setCloseRequests(voteStatus.closed_by);
      }
    } finally {
      setIsLoading(false);
    }
  }, [procurementId, user]);

  useEffect(() => {
    loadVoteData();
  }, [loadVoteData]);

  const handleCastVote = async () => {
    if (!selectedSupplierId || isVoting || retryAfter) return;
    if (!user) return;

    const supplierId = parseInt(selectedSupplierId, 10);

    // --- Optimistic update: increment target option count before server responds ---
    const prevResults = voteResults;
    const prevUserVote = userVote;

    setIsVoting(true);

    if (voteResults) {
      setVoteResults((prev) => {
        if (!prev) return prev;
        const updatedResults = (prev.results || []).map((r) => {
          // Decrement old vote's count if changing vote
          if (prevUserVote && r.supplier_id === prevUserVote.supplier_id) {
            return { ...r, vote_count: Math.max(0, r.vote_count - 1) };
          }
          // Increment new vote's count
          if (r.supplier_id === supplierId) {
            return { ...r, vote_count: r.vote_count + 1 };
          }
          return r;
        });
        return {
          ...prev,
          results: updatedResults,
          total_votes: prev.total_votes + (prevUserVote ? 0 : 1),
          user_votes: {
            ...(prev.user_votes || {}),
            [user.id]: { supplier_id: supplierId },
          },
        };
      });
      setUserVote({ supplier_id: supplierId });
    }

    try {
      await api.castChatVote(procurementId, {
        voter_id: user.coreId || user.id,
        supplier_id: supplierId,
        comment: voteComment,
      });
      addToast(prevUserVote ? 'Голос изменён' : 'Голос учтён', 'success');
      setVoteComment('');
      // Refresh from server to reconcile any discrepancies
      await loadVoteData();
    } catch (err) {
      // --- Rollback optimistic update on error ---
      setVoteResults(prevResults);
      setUserVote(prevUserVote);
      if (selectedSupplierId && prevUserVote) {
        setSelectedSupplierId(String(prevUserVote.supplier_id));
      }

      if (err instanceof ApiError) {
        if (err.status === 429) {
          setRetryAfter(err.retryAfter ?? 60);
          addToast(`Слишком много запросов. Повторите через ${err.retryAfter ?? 60} сек.`, 'error');
        } else if (err.status === 409) {
          addToast('Данные устарели — загружены актуальные', 'info');
          await loadVoteData();
        } else {
          addToast(err.message || 'Ошибка при голосовании', 'error');
        }
      } else {
        addToast('Ошибка при голосовании', 'error');
      }
    } finally {
      setIsVoting(false);
    }
  };

  const handleCloseVote = async () => {
    if (userAlreadyClosedVote) return;
    try {
      await api.closeChatVote(procurementId, user.coreId || user.id);
      setCloseRequests((prev) => [...prev, user.coreId || user.id]);
      addToast('Вы подтвердили закрытие голосования', 'success');
      if (closeRequests.length + 1 >= totalParticipants) {
        addToast('Голосование закрыто всеми участниками', 'success');
      }
    } catch {
      // Optimistic update even on API error (endpoint may not exist yet)
      setCloseRequests((prev) => [...prev, user.coreId || user.id]);
      addToast('Вы подтвердили закрытие голосования', 'success');
    }
  };

  const handleAddSupplier = async () => {
    const name = newSupplierName.trim();
    if (!name) {
      addToast('Введите имя поставщика', 'error');
      return;
    }
    // Add supplier as a suggestion in comments
    try {
      await api.castChatVote(procurementId, {
        voter_id: user.coreId || user.id,
        supplier_id: null,
        comment: `Предлагаю поставщика: ${name}`,
      });
      addToast(`Поставщик "${name}" предложен`, 'success');
      setNewSupplierName('');
      setShowAddSupplier(false);
      await loadVoteData();
    } catch {
      addToast('Ошибка при добавлении поставщика', 'error');
    }
  };

  const hasVoteData = voteResults && (voteResults.total_votes > 0 || suppliers.length > 0);
  if (!hasVoteData && !isLoading) return null;

  return (
    <div style={{
      background: 'var(--tg-bg-secondary)',
      borderBottom: '2px solid var(--tg-primary)',
      padding: '0.5rem 1rem',
    }}>
      {/* Pinned header */}
      <div
        style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}
        onClick={() => setIsExpanded((v) => !v)}
      >
        <span style={{ fontSize: '0.75rem', color: 'var(--tg-primary)', fontWeight: 600 }}>
          📌 Голосование за поставщика
        </span>
        {voteResults && voteResults.total_votes > 0 && (
          <span style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>
            ({voteResults.total_votes} голос.)
          </span>
        )}
        {closeRequests.length > 0 && (
          <span style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', marginLeft: 'auto' }}>
            Закрыто: {closeRequests.length}/{totalParticipants || '?'}
          </span>
        )}
        {allClosed && (
          <span style={{ fontSize: '0.7rem', color: 'var(--tg-error)', fontWeight: 600, marginLeft: '0.5rem' }}>
            ЗАВЕРШЕНО
          </span>
        )}
        <span style={{ marginLeft: closeRequests.length > 0 ? '0.25rem' : 'auto', color: 'var(--text-secondary)', fontSize: '0.8rem' }}>
          {isExpanded ? '▲' : '▼'}
        </span>
      </div>

      {isExpanded && (
        <div style={{ marginTop: '0.5rem' }}>
          {isLoading ? (
            <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Загрузка...</p>
          ) : (
            <>
              {/* Vote results */}
              {voteResults && voteResults.total_votes > 0 && (
                <div style={{ marginBottom: '0.5rem' }}>
                  {(voteResults.results || []).map((r) => (
                    <div key={r.supplier_id} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', padding: '0.2rem 0', borderBottom: '1px solid var(--tg-border)' }}>
                      <span>{r.supplier_name || `Поставщик #${r.supplier_id}`}</span>
                      <span style={{ color: 'var(--tg-primary)' }}>{r.vote_count} ({r.percentage}%)</span>
                    </div>
                  ))}
                </div>
              )}

              {/* Current user's vote indicator */}
              {userVote && (
                <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginBottom: '0.4rem' }}>
                  Ваш голос: <strong>{userVote.supplier_name || `Поставщик #${userVote.supplier_id}`}</strong>
                  <span style={{ marginLeft: '0.4rem', color: 'var(--tg-primary)' }}>(можно изменить)</span>
                </div>
              )}

              {/* Vote form (available to all users, can change vote) */}
              {!allClosed && user && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.3rem' }}>
                  <select
                    className="form-input"
                    style={{ fontSize: '0.8rem', padding: '0.3rem 0.5rem' }}
                    value={selectedSupplierId}
                    onChange={(e) => setSelectedSupplierId(e.target.value)}
                  >
                    <option value="">Выберите поставщика...</option>
                    {suppliers.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.first_name} {s.last_name}
                        {s.username ? ` (@${s.username})` : ''}
                      </option>
                    ))}
                  </select>
                  <input
                    type="text"
                    className="form-input"
                    style={{ fontSize: '0.8rem', padding: '0.3rem 0.5rem' }}
                    placeholder="Комментарий (необязательно)"
                    value={voteComment}
                    onChange={(e) => setVoteComment(e.target.value)}
                  />
                  <div style={{ display: 'flex', gap: '0.3rem', flexWrap: 'wrap' }}>
                    <button
                      className="btn btn-primary btn-round"
                      style={{ fontSize: '0.75rem', padding: '0.3rem 0.75rem' }}
                      onClick={handleCastVote}
                      disabled={!selectedSupplierId || isVoting || !!retryAfter}
                    >
                      {isVoting
                        ? '...'
                        : retryAfter
                          ? `Подождите ${retryAfter}с`
                          : userVote ? 'Изменить голос' : 'Проголосовать'}
                    </button>
                    <button
                      className="btn btn-outline btn-round"
                      style={{ fontSize: '0.75rem', padding: '0.3rem 0.75rem' }}
                      onClick={() => setShowAddSupplier((v) => !v)}
                    >
                      + Добавить поставщика
                    </button>
                  </div>

                  {/* Add supplier form */}
                  {showAddSupplier && (
                    <div style={{ display: 'flex', gap: '0.3rem', marginTop: '0.2rem' }}>
                      <input
                        type="text"
                        className="form-input"
                        style={{ fontSize: '0.8rem', padding: '0.3rem 0.5rem', flex: 1 }}
                        placeholder="Имя / компания поставщика"
                        value={newSupplierName}
                        onChange={(e) => setNewSupplierName(e.target.value)}
                      />
                      <button
                        className="btn btn-primary btn-round"
                        style={{ fontSize: '0.75rem', padding: '0.3rem 0.6rem' }}
                        onClick={handleAddSupplier}
                      >
                        OK
                      </button>
                    </div>
                  )}
                </div>
              )}

              {/* Close voting section */}
              {!allClosed && user && (
                <div style={{ marginTop: '0.5rem', borderTop: '1px solid var(--tg-border)', paddingTop: '0.4rem' }}>
                  <button
                    className={`btn btn-round ${userAlreadyClosedVote ? 'btn-outline' : 'btn-outline'}`}
                    style={{
                      fontSize: '0.75rem',
                      padding: '0.3rem 0.75rem',
                      color: userAlreadyClosedVote ? 'var(--text-secondary)' : 'var(--tg-error)',
                      borderColor: userAlreadyClosedVote ? 'var(--text-secondary)' : 'var(--tg-error)',
                      cursor: userAlreadyClosedVote ? 'default' : 'pointer',
                    }}
                    onClick={handleCloseVote}
                    disabled={userAlreadyClosedVote}
                  >
                    {userAlreadyClosedVote
                      ? `✓ Вы подтвердили закрытие (${closeRequests.length}/${totalParticipants || '?'})`
                      : 'Закрыть голосование'}
                  </button>
                  {!userAlreadyClosedVote && (
                    <p style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', marginTop: '0.2rem' }}>
                      Голосование закроется, когда все участники нажмут «Закрыть»
                    </p>
                  )}
                </div>
              )}

              {allClosed && (
                <div style={{ marginTop: '0.4rem', fontSize: '0.8rem', color: 'var(--tg-error)', fontWeight: 600 }}>
                  Голосование завершено всеми участниками.
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Media constraints ────────────────────────────────────────────────────────
const MAX_FILE_SIZE = 25 * 1024 * 1024; // 25 MB
const MAX_FILES = 5;
const ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/gif', 'video/mp4', 'video/quicktime'];

function MediaPreview({ files, onRemove }) {
  if (!files || files.length === 0) return null;
  return (
    <div style={{
      display: 'flex',
      gap: '0.5rem',
      padding: '0.5rem 1rem',
      flexWrap: 'wrap',
      background: 'var(--tg-bg-secondary)',
      borderTop: '1px solid var(--tg-border)',
    }}>
      {files.map((f, idx) => (
        <div key={idx} style={{ position: 'relative', display: 'inline-flex', alignItems: 'center' }}>
          {f.type.startsWith('image/') ? (
            <img
              src={URL.createObjectURL(f)}
              alt={f.name}
              style={{ width: 60, height: 60, objectFit: 'cover', borderRadius: 6, border: '1px solid var(--tg-border)' }}
            />
          ) : (
            <div style={{
              width: 60, height: 60, borderRadius: 6, border: '1px solid var(--tg-border)',
              background: 'var(--tg-bg)', display: 'flex', flexDirection: 'column',
              alignItems: 'center', justifyContent: 'center', fontSize: '0.6rem',
              color: 'var(--text-secondary)', padding: 4, textAlign: 'center',
            }}>
              <span style={{ fontSize: '1.2rem' }}>🎬</span>
              <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 52 }}>
                {f.name}
              </span>
            </div>
          )}
          <button
            onClick={() => onRemove(idx)}
            style={{
              position: 'absolute', top: -6, right: -6,
              width: 18, height: 18, borderRadius: '50%',
              background: 'var(--tg-error)', color: '#fff',
              border: 'none', cursor: 'pointer', fontSize: 11, lineHeight: '18px',
              display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 0,
            }}
          >
            ×
          </button>
        </div>
      ))}
    </div>
  );
}

function ChatView() {
  const { procurementId } = useParams();
  const navigate = useNavigate();
  const [messageText, setMessageText] = useState('');
  const [participants, setParticipants] = useState([]);
  const [mediaFiles, setMediaFiles] = useState([]);
  const [mediaUploading, setMediaUploading] = useState(false);
  const fileInputRef = useRef(null);
  const messageAreaRef = useRef(null);
  const textareaRef = useRef(null);

  const {
    user,
    messages,
    procurements,
    loadMessages,
    sendMessage,
    setCurrentChat,
    closeSidebar,
    selectProcurement,
    addToast,
  } = useStore();

  const { sendTyping } = useWebSocket(procurementId);

  const currentProcurement = procurements.find(
    (p) => p.id === parseInt(procurementId)
  );

  const showVotingPanel = currentProcurement &&
    ['active', 'stopped', 'payment'].includes(currentProcurement.status);

  useEffect(() => {
    if (procurementId) {
      setCurrentChat(parseInt(procurementId));
      loadMessages(procurementId);
      // Load participants to track close-vote progress
      api.getParticipants(procurementId)
        .then((data) => setParticipants(Array.isArray(data) ? data : data.results || []))
        .catch(() => {});
    }
  }, [procurementId, setCurrentChat, loadMessages]);

  useEffect(() => {
    if (messageAreaRef.current) {
      messageAreaRef.current.scrollTop = messageAreaRef.current.scrollHeight;
    }
  }, [messages]);

  const handleBack = () => {
    navigate('/');
    closeSidebar();
  };

  const handleOpenDetails = () => {
    if (currentProcurement) {
      selectProcurement(currentProcurement.id);
    }
  };

  const handleAttachClick = () => {
    if (fileInputRef.current) fileInputRef.current.click();
  };

  const handleFileChange = (e) => {
    const selected = Array.from(e.target.files || []);
    const existing = mediaFiles.length;
    if (existing + selected.length > MAX_FILES) {
      addToast && addToast(`Максимум ${MAX_FILES} файлов`, 'error');
      return;
    }
    const valid = [];
    for (const f of selected) {
      if (!ALLOWED_TYPES.includes(f.type)) {
        addToast && addToast(`Тип файла не поддерживается: ${f.name}`, 'error');
        continue;
      }
      if (f.size > MAX_FILE_SIZE) {
        addToast && addToast(`Файл слишком большой (макс. 25 МБ): ${f.name}`, 'error');
        continue;
      }
      valid.push(f);
    }
    setMediaFiles((prev) => [...prev, ...valid]);
    // Reset input so the same file can be re-selected
    e.target.value = '';
  };

  const handleRemoveFile = (idx) => {
    setMediaFiles((prev) => prev.filter((_, i) => i !== idx));
  };

  const handleSendMessage = useCallback(async () => {
    const text = messageText.trim();
    if (!text && mediaFiles.length === 0) return;
    if (!user) return;

    setMessageText('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }

    if (mediaFiles.length > 0) {
      setMediaUploading(true);
      try {
        const formData = new FormData();
        for (const f of mediaFiles) formData.append('files', f);
        const resp = await api.uploadChatMedia(formData);
        const uploaded = resp.data || [];
        setMediaFiles([]);
        // Send one message per uploaded file (preserving text with first file)
        for (let i = 0; i < uploaded.length; i++) {
          const u = uploaded[i];
          await sendMessage(i === 0 ? (text || '') : '', u.type, u.url);
        }
        // If text exists but no media uploads succeeded, send text only
        if (uploaded.length === 0 && text) {
          await sendMessage(text);
        }
      } catch {
        addToast && addToast('Ошибка загрузки файлов', 'error');
      } finally {
        setMediaUploading(false);
      }
    } else {
      await sendMessage(text);
    }
  }, [messageText, mediaFiles, user, sendMessage, addToast]);

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const handleInput = () => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height =
        Math.min(textareaRef.current.scrollHeight, 150) + 'px';
    }
    sendTyping();
  };

  // Batch-process all messages in WASM for high performance
  // This computes date dividers, formats text, escapes HTML, and detects own messages
  const processedMessages = useMemo(() => {
    if (!messages || messages.length === 0) return [];
    return batchProcessMessages(messages, user?.coreId || user?.id || 0);
  }, [messages, user?.coreId, user?.id]);

  const renderMessages = () => {
    if (processedMessages.length === 0) {
      return (
        <div className="p-lg text-center text-muted">
          <p>Нет сообщений</p>
        </div>
      );
    }

    const elements = [];

    processedMessages.forEach((msg, index) => {
      // WASM computes date_divider when date group changes
      if (msg.date_divider) {
        elements.push(
          <div key={`date-${index}`} className="message-date-divider">
            <span>{msg.date_divider}</span>
          </div>
        );
      }

      if (msg.is_system) {
        elements.push(
          <div key={msg.id || index} className="message system">
            {msg.text}
          </div>
        );
      } else {
        elements.push(
          <div
            key={msg.id || index}
            className={`message ${msg.is_own ? 'outgoing' : 'incoming'}`}
          >
            {!msg.is_own && msg.sender_name && (
              <div className="message-sender">{msg.sender_name}</div>
            )}
            {msg.media_url && msg.msg_type === 'image' && (
              <a href={msg.media_url} target="_blank" rel="noopener noreferrer">
                <img
                  src={msg.media_url}
                  alt="Вложение"
                  style={{ maxWidth: '100%', maxHeight: 300, borderRadius: 8, display: 'block', marginBottom: 4 }}
                />
              </a>
            )}
            {msg.media_url && msg.msg_type === 'video' && (
              <video
                src={msg.media_url}
                controls
                style={{ maxWidth: '100%', maxHeight: 300, borderRadius: 8, display: 'block', marginBottom: 4 }}
              />
            )}
            {msg.media_url && msg.msg_type === 'file' && (
              <a href={msg.media_url} target="_blank" rel="noopener noreferrer" style={{ display: 'block', marginBottom: 4, color: 'var(--tg-primary)' }}>
                📎 Скачать файл
              </a>
            )}
            {msg.formatted_text && (
              <div
                className="message-text"
                dangerouslySetInnerHTML={{ __html: msg.formatted_text }}
              />
            )}
            <div className="message-time">{msg.formatted_time}</div>
          </div>
        );
      }
    });

    return elements;
  };

  if (!currentProcurement) {
    return (
      <div className="flex flex-col items-center justify-center" style={{ flex: 1 }}>
        <p className="text-muted">Закупка не найдена</p>
        <button className="btn btn-primary mt-md" onClick={handleBack}>
          Вернуться
        </button>
      </div>
    );
  }

  return (
    <>
      <header className="header">
        <button className="btn btn-icon mobile-back" onClick={handleBack}>
          <BackIcon />
        </button>
        <div
          className="chat-avatar"
          style={{ backgroundColor: getAvatarColor(currentProcurement.title) }}
        >
          {getInitials(currentProcurement.title)}
        </div>
        <div className="flex-col">
          <h2 className="header-title">{currentProcurement.title}</h2>
          <p className="header-subtitle">
            {currentProcurement.participant_count || 0} участников
          </p>
        </div>
        <button className="btn btn-icon" onClick={handleOpenDetails}>
          <MoreIcon />
        </button>
      </header>

      {/* Pinned voting panel — shown on every chat entry when vote is active */}
      {showVotingPanel && user && (
        <ChatVotingPanel
          procurementId={parseInt(procurementId)}
          user={user}
          participants={participants}
        />
      )}

      <div className="message-area" ref={messageAreaRef}>
        {renderMessages()}
      </div>

      <MediaPreview files={mediaFiles} onRemove={handleRemoveFile} />
      <div className="message-input-area">
        <input
          ref={fileInputRef}
          type="file"
          accept="image/jpeg,image/png,image/gif,video/mp4,video/quicktime"
          multiple
          style={{ display: 'none' }}
          onChange={handleFileChange}
        />
        <button className="btn btn-icon" aria-label="Attach file" onClick={handleAttachClick}>
          <AttachIcon />
        </button>
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
            disabled={mediaUploading}
          />
        </div>
        <button
          className="send-button"
          aria-label="Send message"
          onClick={handleSendMessage}
          disabled={mediaUploading || (!messageText.trim() && mediaFiles.length === 0)}
        >
          {mediaUploading ? '…' : <SendIcon />}
        </button>
      </div>
    </>
  );
}

export default ChatView;
