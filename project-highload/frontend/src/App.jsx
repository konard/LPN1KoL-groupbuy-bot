import { useState, useEffect, useRef, useCallback } from "react";

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "http://localhost/api";
const WS_URL = import.meta.env.VITE_WS_URL || "ws://localhost/ws";

function App() {
  const [items, setItems] = useState([]);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [wsStatus, setWsStatus] = useState("disconnected");
  const [events, setEvents] = useState([]);
  const wsRef = useRef(null);
  const reconnectTimer = useRef(null);

  const fetchItems = useCallback(async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/items`);
      const data = await res.json();
      setItems(data);
    } catch (err) {
      console.error("Failed to fetch items:", err);
    }
  }, []);

  const connectWs = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      setWsStatus("connected");
      setEvents((prev) => [`[${new Date().toLocaleTimeString()}] Connected to WebSocket`, ...prev.slice(0, 49)]);
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.event === "items:new") {
          setEvents((prev) => [
            `[${new Date().toLocaleTimeString()}] New item via ${msg.server}: ${msg.data.name}`,
            ...prev.slice(0, 49),
          ]);
          setItems((prev) => [msg.data, ...prev]);
        }
      } catch {
        // ignore malformed messages
      }
    };

    ws.onclose = () => {
      setWsStatus("reconnecting");
      reconnectTimer.current = setTimeout(connectWs, 3000);
    };

    ws.onerror = () => {
      ws.close();
    };
  }, []);

  useEffect(() => {
    fetchItems();
    connectWs();
    return () => {
      clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [fetchItems, connectWs]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!name.trim()) return;
    try {
      await fetch(`${BACKEND_URL}/items`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, description }),
      });
      setName("");
      setDescription("");
    } catch (err) {
      console.error("Failed to create item:", err);
    }
  };

  return (
    <div style={{ fontFamily: "sans-serif", maxWidth: 800, margin: "0 auto", padding: 20 }}>
      <h1>GroupBuy High-Load Demo</h1>

      <p>
        WebSocket:{" "}
        <span style={{ color: wsStatus === "connected" ? "green" : "orange", fontWeight: "bold" }}>
          {wsStatus}
        </span>
      </p>

      <section>
        <h2>Add Item</h2>
        <form onSubmit={handleSubmit} style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Item name"
            required
            style={{ flex: 1, padding: "6px 10px" }}
          />
          <input
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Description (optional)"
            style={{ flex: 2, padding: "6px 10px" }}
          />
          <button type="submit" style={{ padding: "6px 16px" }}>
            Add
          </button>
        </form>
      </section>

      <section style={{ marginTop: 24 }}>
        <h2>Live Events</h2>
        <div
          style={{
            background: "#111",
            color: "#0f0",
            fontFamily: "monospace",
            padding: 12,
            height: 150,
            overflowY: "auto",
            borderRadius: 4,
          }}
        >
          {events.length === 0 ? <span style={{ color: "#555" }}>Waiting for events…</span> : null}
          {events.map((e, i) => (
            <div key={i}>{e}</div>
          ))}
        </div>
      </section>

      <section style={{ marginTop: 24 }}>
        <h2>Items ({items.length})</h2>
        <ul style={{ listStyle: "none", padding: 0 }}>
          {items.map((item) => (
            <li
              key={item.id}
              style={{ borderBottom: "1px solid #eee", padding: "8px 0" }}
            >
              <strong>#{item.id}</strong> {item.name}
              {item.description ? ` — ${item.description}` : ""}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

export default App;
