use actix_web::{web, HttpRequest, HttpResponse};
use actix_ws::Message;
use futures_util::StreamExt;
use sqlx::PgPool;
use std::sync::Arc;
use tokio::sync::broadcast;

/// Shared state for WebSocket connections
pub struct WsState {
    pub tx: broadcast::Sender<String>,
}

impl WsState {
    pub fn new() -> Self {
        let (tx, _) = broadcast::channel(1000);
        WsState { tx }
    }
}

/// WebSocket handler for real-time chat
pub async fn ws_handler(
    req: HttpRequest,
    body: web::Payload,
    ws_state: web::Data<Arc<WsState>>,
    _pool: web::Data<PgPool>,
) -> Result<HttpResponse, actix_web::Error> {
    let (response, mut session, mut msg_stream) = actix_ws::handle(&req, body)?;

    let tx = ws_state.tx.clone();
    let mut rx = tx.subscribe();

    // Spawn task to forward broadcast messages to this WebSocket client
    let mut session_clone = session.clone();
    actix_web::rt::spawn(async move {
        while let Ok(msg) = rx.recv().await {
            if session_clone.text(msg).await.is_err() {
                break;
            }
        }
    });

    // Spawn task to handle incoming WebSocket messages
    actix_web::rt::spawn(async move {
        while let Some(Ok(msg)) = msg_stream.next().await {
            match msg {
                Message::Text(text) => {
                    // Parse incoming message and broadcast to all clients
                    let text_str = text.to_string();
                    tracing::debug!("WebSocket received: {}", text_str);

                    // Broadcast to all connected clients
                    let _ = tx.send(text_str);
                }
                Message::Ping(bytes) => {
                    if session.pong(&bytes).await.is_err() {
                        break;
                    }
                }
                Message::Close(_) => {
                    break;
                }
                _ => {}
            }
        }
    });

    Ok(response)
}
