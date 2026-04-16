import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";


const apiUrl = import.meta.env.VITE_API_URL || "/api";
const configuredWsUrl = import.meta.env.VITE_WS_URL || "/ws/items";


function toWebSocketUrl(value) {
  if (value.startsWith("ws://") || value.startsWith("wss://")) {
    return value;
  }
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const path = value.startsWith("/") ? value : `/${value}`;
  return `${protocol}//${window.location.host}${path}`;
}


function App() {
  const [items, setItems] = useState([]);
  const [events, setEvents] = useState([]);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [status, setStatus] = useState("connecting");
  const [serverId, setServerId] = useState("-");
  const retryRef = useRef(0);
  const socketRef = useRef(null);

  const wsUrl = useMemo(() => toWebSocketUrl(configuredWsUrl), []);

  const loadItems = useCallback(async () => {
    const response = await fetch(`${apiUrl}/items`);
    if (!response.ok) {
      throw new Error(`GET /api/items failed with ${response.status}`);
    }
    setItems(await response.json());
  }, []);

  useEffect(() => {
    loadItems().catch((error) => {
      setEvents((current) => [
        { type: "error", text: error.message, at: new Date().toISOString() },
        ...current.slice(0, 8),
      ]);
    });
  }, [loadItems]);

  useEffect(() => {
    let stopped = false;
    let retryTimer = null;

    const connect = () => {
      if (stopped) return;
      const socket = new WebSocket(wsUrl);
      socketRef.current = socket;
      setStatus("connecting");

      socket.onopen = () => {
        retryRef.current = 0;
        setStatus("connected");
      };

      socket.onmessage = (event) => {
        const payload = JSON.parse(event.data);
        if (payload.server_id) {
          setServerId(payload.server_id);
        }
        if (payload.type === "item.created" && payload.item) {
          setItems((current) => [payload.item, ...current.filter((item) => item.id !== payload.item.id)]);
        }
        setEvents((current) => [
          { ...payload, at: new Date().toISOString() },
          ...current.slice(0, 8),
        ]);
      };

      socket.onclose = () => {
        if (stopped) return;
        setStatus("reconnecting");
        const delay = Math.min(1000 * 2 ** retryRef.current, 10000);
        retryRef.current += 1;
        retryTimer = window.setTimeout(connect, delay);
      };

      socket.onerror = () => {
        socket.close();
      };
    };

    connect();

    return () => {
      stopped = true;
      window.clearTimeout(retryTimer);
      if (socketRef.current) {
        socketRef.current.close();
      }
    };
  }, [wsUrl]);

  const createItem = async (event) => {
    event.preventDefault();
    const trimmedName = name.trim();
    if (!trimmedName) return;

    const response = await fetch(`${apiUrl}/items`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: trimmedName,
        description: description.trim() || null,
      }),
    });

    if (!response.ok) {
      const body = await response.text();
      setEvents((current) => [
        { type: "error", text: body, at: new Date().toISOString() },
        ...current.slice(0, 8),
      ]);
      return;
    }

    setName("");
    setDescription("");
  };

  return (
    <main className="shell">
      <section className="panel">
        <div>
          <p className="eyebrow">GroupBuy Highload</p>
          <h1>Items stream</h1>
        </div>
        <div className="status-row">
          <span className={`status ${status}`}>{status}</span>
          <span className="server">server {serverId}</span>
        </div>

        <form className="create-form" onSubmit={createItem}>
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Item name"
            maxLength={200}
          />
          <input
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            placeholder="Description"
            maxLength={2000}
          />
          <button type="submit">Create</button>
        </form>

        <div className="grid">
          <section>
            <h2>Latest items</h2>
            <ul className="list">
              {items.map((item) => (
                <li key={item.id}>
                  <strong>{item.name}</strong>
                  {item.description && <span>{item.description}</span>}
                </li>
              ))}
              {items.length === 0 && <li className="empty">No items yet</li>}
            </ul>
          </section>

          <section>
            <h2>Redis Pub/Sub events</h2>
            <ul className="list events">
              {events.map((event, index) => (
                <li key={`${event.at}-${index}`}>
                  <strong>{event.type || "event"}</strong>
                  <span>{event.item?.name || event.text || event.server_id || "received"}</span>
                </li>
              ))}
              {events.length === 0 && <li className="empty">Waiting for events</li>}
            </ul>
          </section>
        </div>
      </section>
    </main>
  );
}


createRoot(document.getElementById("root")).render(<App />);
