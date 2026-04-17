import { useState, useEffect, useRef } from 'react'
import { SOCKET_URL } from '../api.js'

const s = {
  wrap: { display: 'flex', flexDirection: 'column', height: '100vh' },
  header: { background: '#1a1a2e', color: '#fff', padding: '1rem 1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' },
  main: { flex: 1, display: 'flex', gap: '1rem', padding: '1rem', overflow: 'hidden' },
  sidebar: { width: 200, background: '#fff', borderRadius: 8, padding: '1rem', boxShadow: '0 2px 4px rgba(0,0,0,.08)' },
  roomBtn: (active) => ({ display: 'block', width: '100%', padding: '.5rem', marginBottom: '.4rem', background: active ? '#007bff' : '#f0f2f5', color: active ? '#fff' : '#333', border: 'none', borderRadius: 4, cursor: 'pointer', textAlign: 'left' }),
  chat: { flex: 1, display: 'flex', flexDirection: 'column', background: '#fff', borderRadius: 8, boxShadow: '0 2px 4px rgba(0,0,0,.08)' },
  messages: { flex: 1, padding: '1rem', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '.5rem' },
  msg: (isMe) => ({ alignSelf: isMe ? 'flex-end' : 'flex-start', maxWidth: '70%', padding: '.5rem .8rem', borderRadius: 12, background: isMe ? '#007bff' : '#f0f2f5', color: isMe ? '#fff' : '#333' }),
  sysmsg: { alignSelf: 'center', fontSize: '.8rem', color: '#999', fontStyle: 'italic' },
  inputRow: { padding: '.75rem', borderTop: '1px solid #eee', display: 'flex', gap: '.5rem' },
  input: { flex: 1, padding: '.6rem', border: '1px solid #ccc', borderRadius: 4, fontSize: '1rem' },
  sendBtn: { padding: '.6rem 1.2rem', background: '#007bff', color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer' },
  logoutBtn: { background: 'none', border: '1px solid #a8d8ea', color: '#a8d8ea', padding: '.3rem .8rem', borderRadius: 4, cursor: 'pointer' },
}

const ROOMS = ['general', 'sales', 'support']

export default function ChatPage({ user, onLogout }) {
  const [room, setRoom] = useState('general')
  const [messages, setMessages] = useState([])
  const [text, setText] = useState('')
  const [connected, setConnected] = useState(false)
  const wsRef = useRef(null)
  const bottomRef = useRef(null)

  useEffect(() => {
    const token = localStorage.getItem('token')
    if (!token) return

    const url = `${SOCKET_URL}/ws/${room}?token=${token}`
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => setConnected(true)
    ws.onclose = () => setConnected(false)
    ws.onerror = () => setConnected(false)
    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data)
        setMessages(prev => [...prev, msg])
      } catch {}
    }

    setMessages([])
    return () => ws.close()
  }, [room])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  function sendMessage(e) {
    e.preventDefault()
    if (!text.trim() || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return
    wsRef.current.send(JSON.stringify({ text }))
    setText('')
  }

  return (
    <div style={s.wrap}>
      <div style={s.header}>
        <span>GroupBuy Chat &mdash; <strong>{user.username}</strong></span>
        <span style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <span style={{ fontSize: '.85rem', color: connected ? '#7bed9f' : '#ff6b6b' }}>
            {connected ? '● Connected' : '○ Disconnected'}
          </span>
          <button style={s.logoutBtn} onClick={onLogout}>Logout</button>
        </span>
      </div>
      <div style={s.main}>
        <div style={s.sidebar}>
          <p style={{ fontWeight: 600, marginBottom: '.8rem', fontSize: '.9rem' }}>Rooms</p>
          {ROOMS.map(r => (
            <button key={r} style={s.roomBtn(r === room)} onClick={() => setRoom(r)}>
              # {r}
            </button>
          ))}
        </div>
        <div style={s.chat}>
          <div style={s.messages}>
            {messages.map((m, i) =>
              m.type === 'system'
                ? <div key={i} style={s.sysmsg}>{m.text}</div>
                : <div key={i} style={s.msg(m.user_id === String(user.id))}>
                    {m.user_id !== String(user.id) && <div style={{ fontSize: '.75rem', opacity: .7, marginBottom: '.15rem' }}>{m.user_id}</div>}
                    <div>{m.text}</div>
                    <div style={{ fontSize: '.7rem', opacity: .6, marginTop: '.15rem', textAlign: 'right' }}>
                      {new Date(m.timestamp).toLocaleTimeString()}
                    </div>
                  </div>
            )}
            <div ref={bottomRef} />
          </div>
          <form style={s.inputRow} onSubmit={sendMessage}>
            <input
              style={s.input}
              value={text}
              onChange={e => setText(e.target.value)}
              placeholder={connected ? 'Type a message…' : 'Connecting…'}
              disabled={!connected}
            />
            <button style={s.sendBtn} type="submit" disabled={!connected}>Send</button>
          </form>
        </div>
      </div>
    </div>
  )
}
