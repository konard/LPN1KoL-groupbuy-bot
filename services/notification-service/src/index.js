'use strict';

const { Kafka, logLevel } = require('kafkajs');
const nodemailer = require('nodemailer');
const axios = require('axios');
const webpush = require('web-push');
const http = require('http');

// ─── Configuration ────────────────────────────────────────────────────────────

const config = {
  kafka: {
    brokers: (process.env.KAFKA_BROKERS || 'localhost:9092').split(','),
    groupId: process.env.KAFKA_GROUP_ID || 'notification-group',
    clientId: 'notification-service',
  },
  centrifugo: {
    url: process.env.CENTRIFUGO_URL || 'http://localhost:8000',
    apiKey: process.env.CENTRIFUGO_API_KEY || 'centrifugo_api_key',
  },
  smtp: {
    host: process.env.SMTP_HOST || 'smtp.example.com',
    port: parseInt(process.env.SMTP_PORT || '587', 10),
    user: process.env.SMTP_USER || 'notifications@example.com',
    pass: process.env.SMTP_PASS || '',
    from: process.env.SMTP_FROM || 'Groupbuy <notifications@example.com>',
  },
  webPush: {
    vapidPublicKey: process.env.VAPID_PUBLIC_KEY || '',
    vapidPrivateKey: process.env.VAPID_PRIVATE_KEY || '',
    subject: process.env.VAPID_SUBJECT || 'mailto:admin@example.com',
  },
  telegram: {
    botToken: process.env.TELEGRAM_BOT_TOKEN || '',
    apiUrl: process.env.TELEGRAM_API_URL || 'https://api.telegram.org',
  },
  whatsapp: {
    apiUrl: process.env.WHATSAPP_API_URL || '',
    accessToken: process.env.WHATSAPP_ACCESS_TOKEN || '',
    phoneNumberId: process.env.WHATSAPP_PHONE_NUMBER_ID || '',
  },
  port: parseInt(process.env.PORT || '4005', 10),
};

// ─── Email Transport ──────────────────────────────────────────────────────────

const mailer = nodemailer.createTransport({
  host: config.smtp.host,
  port: config.smtp.port,
  // port 465 → implicit TLS/SSL; port 587 → STARTTLS (requireTLS ensures the
  // upgrade is mandatory — Yandex and many other providers reject plain-text
  // connections even on 587, so we must not allow a downgrade).
  secure: config.smtp.port === 465,
  requireTLS: config.smtp.port !== 465,
  auth: {
    user: config.smtp.user,
    pass: config.smtp.pass,
  },
});

async function sendEmail(to, subject, html, text) {
  try {
    await mailer.sendMail({
      from: config.smtp.from,
      to,
      subject,
      html,
      text,
    });
    console.log(`[EMAIL] Sent to ${to}: ${subject}`);
  } catch (err) {
    console.error(`[EMAIL] Failed to send to ${to}: ${err.message}`);
  }
}

// ─── WebSocket via Centrifugo ─────────────────────────────────────────────────

async function publishCentrifugo(channel, data) {
  try {
    await axios.post(
      `${config.centrifugo.url}/api`,
      {
        method: 'publish',
        params: { channel, data },
      },
      {
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': config.centrifugo.apiKey,
        },
        timeout: 5000,
      }
    );
    console.log(`[WS] Published to ${channel}`);
  } catch (err) {
    console.error(`[WS] Centrifugo publish error: ${err.message}`);
  }
}

// ─── Web Push ─────────────────────────────────────────────────────────────────

if (config.webPush.vapidPublicKey && config.webPush.vapidPrivateKey) {
  webpush.setVapidDetails(
    config.webPush.subject,
    config.webPush.vapidPublicKey,
    config.webPush.vapidPrivateKey
  );
}

async function sendPushNotification(subscription, title, body, data = {}) {
  if (!config.webPush.vapidPublicKey) {
    console.log(`[PUSH] VAPID not configured, skipping`);
    return;
  }
  try {
    await webpush.sendNotification(
      subscription,
      JSON.stringify({ title, body, data })
    );
    console.log(`[PUSH] Sent push notification: ${title}`);
  } catch (err) {
    console.error(`[PUSH] Failed: ${err.message}`);
  }
}

// ─── Telegram Bot ────────────────────────────────────────────────────────────

async function sendTelegramMessage(chatId, text, inlineKeyboard = null) {
  if (!config.telegram.botToken) {
    console.log(`[TELEGRAM] Bot token not configured, skipping`);
    return;
  }
  try {
    const body = {
      chat_id: chatId,
      text,
      parse_mode: 'HTML',
    };
    if (inlineKeyboard) {
      body.reply_markup = { inline_keyboard: inlineKeyboard };
    }
    await axios.post(
      `${config.telegram.apiUrl}/bot${config.telegram.botToken}/sendMessage`,
      body,
      { timeout: 10000 }
    );
    console.log(`[TELEGRAM] Sent to ${chatId}: ${text.substring(0, 50)}...`);
  } catch (err) {
    console.error(`[TELEGRAM] Failed to send to ${chatId}: ${err.message}`);
  }
}

// ─── WhatsApp Bot ────────────────────────────────────────────────────────────

async function sendWhatsAppMessage(phoneNumber, text, buttons = null) {
  if (!config.whatsapp.accessToken || !config.whatsapp.phoneNumberId) {
    console.log(`[WHATSAPP] API not configured, skipping`);
    return;
  }
  try {
    const body = {
      messaging_product: 'whatsapp',
      to: phoneNumber,
      type: buttons ? 'interactive' : 'text',
    };
    if (buttons) {
      body.interactive = {
        type: 'button',
        body: { text },
        action: {
          buttons: buttons.map((b, i) => ({
            type: 'reply',
            reply: { id: b.id || `btn_${i}`, title: b.title },
          })),
        },
      };
    } else {
      body.text = { body: text };
    }
    await axios.post(
      `${config.whatsapp.apiUrl}/${config.whatsapp.phoneNumberId}/messages`,
      body,
      {
        headers: {
          Authorization: `Bearer ${config.whatsapp.accessToken}`,
          'Content-Type': 'application/json',
        },
        timeout: 10000,
      }
    );
    console.log(`[WHATSAPP] Sent to ${phoneNumber}: ${text.substring(0, 50)}...`);
  } catch (err) {
    console.error(`[WHATSAPP] Failed to send to ${phoneNumber}: ${err.message}`);
  }
}

// ─── Multi-channel notification helper ───────────────────────────────────────

async function notifyUser(userId, { channel, title, body, buttons, telegramChatId, whatsappPhone }) {
  // Always send WebSocket notification
  await publishCentrifugo(`notifications:${userId}`, {
    type: 'notification',
    title,
    body,
    timestamp: new Date().toISOString(),
  });

  // Telegram if chat ID available
  if (telegramChatId) {
    const keyboard = buttons
      ? buttons.map(b => [{ text: b.title, callback_data: b.action }])
      : null;
    await sendTelegramMessage(telegramChatId, `<b>${title}</b>\n${body}`, keyboard);
  }

  // WhatsApp if phone available
  if (whatsappPhone) {
    await sendWhatsAppMessage(whatsappPhone, `${title}\n${body}`, buttons);
  }
}

// ─── Event Handlers ───────────────────────────────────────────────────────────

const eventHandlers = {
  // Auth events
  'auth.registered': async (payload) => {
    await sendEmail(
      payload.email,
      'Welcome to Groupbuy!',
      `<h1>Welcome ${payload.email}!</h1><p>Your account has been created.</p>`,
      `Welcome ${payload.email}! Your account has been created.`
    );
  },

  // Purchase events
  'purchase.created': async (payload) => {
    await publishCentrifugo(`notifications:${payload.organizerId}`, {
      type: 'purchase_created',
      purchaseId: payload.purchaseId,
      title: payload.title,
      message: `Your group purchase "${payload.title}" has been created`,
    });
  },

  'purchase.voting.started': async (payload) => {
    await publishCentrifugo(`purchase:${payload.purchaseId}`, {
      type: 'voting_started',
      sessionId: payload.sessionId,
      closesAt: payload.closesAt,
      message: 'Voting has started! Cast your vote now.',
    });
  },

  'purchase.vote.cast': async (payload) => {
    await publishCentrifugo(`purchase:${payload.sessionId}`, {
      type: 'vote_cast',
      userId: payload.userId,
      candidateId: payload.candidateId,
      message: 'A new vote has been cast',
    });
  },

  'purchase.vote.changed': async (payload) => {
    await publishCentrifugo(`purchase:${payload.sessionId}`, {
      type: 'vote_changed',
      userId: payload.userId,
      oldCandidateId: payload.oldCandidateId,
      newCandidateId: payload.newCandidateId,
      message: 'A vote has been changed',
    });
  },

  'purchase.candidate.added': async (payload) => {
    await publishCentrifugo(`purchase:${payload.sessionId}`, {
      type: 'candidate_added',
      candidateId: payload.candidateId,
      supplierName: payload.supplierName,
      proposedBy: payload.proposedBy,
      message: `New supplier candidate added: ${payload.supplierName}`,
    });
  },

  'purchase.voting.closed': async (payload) => {
    await publishCentrifugo(`purchase:${payload.purchaseId}`, {
      type: 'voting_closed',
      sessionId: payload.sessionId,
      winnerId: payload.winnerId,
      totalVotes: payload.totalVotes,
      message: payload.winnerId
        ? 'Voting has closed. A winner has been selected!'
        : 'Voting has closed. No winner selected.',
    });
  },

  'purchase.cancelled': async (payload) => {
    await publishCentrifugo(`notifications:${payload.organizerId}`, {
      type: 'purchase_cancelled',
      purchaseId: payload.purchaseId,
      message: 'Your group purchase has been cancelled',
    });
  },

  // Payment events
  'payment.topup.completed': async (payload) => {
    await publishCentrifugo(`notifications:${payload.userId}`, {
      type: 'wallet_topup',
      amount: payload.amount,
      currency: payload.currency,
      message: `Wallet topped up: ${payload.amount / 100} ${payload.currency}`,
    });
  },

  'payment.hold.created': async (payload) => {
    await publishCentrifugo(`notifications:${payload.userId}`, {
      type: 'payment_hold',
      amount: payload.amount,
      purchaseId: payload.purchaseId,
      message: `Funds held for group purchase: ${payload.amount / 100}`,
    });
  },

  'payment.committed': async (payload) => {
    await publishCentrifugo(`notifications:${payload.walletId}`, {
      type: 'payment_committed',
      amount: payload.amount,
      transactionId: payload.transactionId,
      message: `Payment completed: ${payload.amount / 100}`,
    });
  },

  'payment.released': async (payload) => {
    await publishCentrifugo(`notifications:${payload.walletId}`, {
      type: 'payment_released',
      amount: payload.amount,
      message: `Held funds released: ${payload.amount / 100}`,
    });
  },

  // Voting tie event
  'purchase.voting.tie': async (payload) => {
    await publishCentrifugo(`purchase:${payload.purchaseId}`, {
      type: 'voting_tie',
      sessionId: payload.sessionId,
      candidates: payload.tiedCandidates,
      message: 'Voting ended in a tie! Organizer must select the winner.',
    });
    if (payload.organizerId) {
      await notifyUser(payload.organizerId, {
        title: 'Voting Tie - Action Required',
        body: `Voting for purchase "${payload.purchaseTitle}" ended in a tie. Please select the winner manually.`,
        buttons: [{ title: 'Select Winner', action: `resolve_tie:${payload.sessionId}` }],
        telegramChatId: payload.organizerTelegramId,
        whatsappPhone: payload.organizerWhatsappPhone,
      });
    }
  },

  // Commission events
  'commission.held': async (payload) => {
    await publishCentrifugo(`notifications:${payload.organizerId}`, {
      type: 'commission_held',
      purchaseId: payload.purchaseId,
      amount: payload.amount,
      percent: payload.percent,
      message: `Commission ${payload.percent}% held for purchase: ${payload.amount / 100}`,
    });
  },

  'commission.committed': async (payload) => {
    await publishCentrifugo(`notifications:${payload.organizerId}`, {
      type: 'commission_committed',
      purchaseId: payload.purchaseId,
      amount: payload.amount,
      message: `Commission earned: ${payload.amount / 100}`,
    });
  },

  'commission.released': async (payload) => {
    await publishCentrifugo(`notifications:${payload.organizerId}`, {
      type: 'commission_released',
      purchaseId: payload.purchaseId,
      message: 'Commission hold released (purchase cancelled)',
    });
  },

  // Escrow events
  'escrow.created': async (payload) => {
    await publishCentrifugo(`purchase:${payload.purchaseId}`, {
      type: 'escrow_created',
      threshold: payload.threshold,
      message: 'Escrow account created for this purchase (large amount protection)',
    });
  },

  'escrow.deposited': async (payload) => {
    await publishCentrifugo(`purchase:${payload.purchaseId}`, {
      type: 'escrow_deposited',
      userId: payload.userId,
      amount: payload.amount,
      message: `Payment deposited to escrow: ${payload.amount / 100}`,
    });
  },

  'escrow.confirmed': async (payload) => {
    await publishCentrifugo(`purchase:${payload.purchaseId}`, {
      type: 'escrow_confirmed',
      confirmations: payload.confirmationsReceived,
      required: payload.confirmationsRequired,
      message: `Delivery confirmed (${payload.confirmationsReceived}/${payload.confirmationsRequired})`,
    });
  },

  'escrow.released': async (payload) => {
    await publishCentrifugo(`purchase:${payload.purchaseId}`, {
      type: 'escrow_released',
      amount: payload.totalAmount,
      message: 'Escrow released - funds transferred to supplier',
    });
  },

  'escrow.disputed': async (payload) => {
    await publishCentrifugo(`purchase:${payload.purchaseId}`, {
      type: 'escrow_disputed',
      message: 'Escrow disputed - arbitration in progress',
    });
  },

  // Reputation events
  'review.created': async (payload) => {
    await notifyUser(payload.targetId, {
      title: 'New Review',
      body: `You received a ${payload.rating}-star review from a ${payload.reviewerRole}`,
      telegramChatId: payload.targetTelegramId,
      whatsappPhone: payload.targetWhatsappPhone,
    });
  },

  'complaint.filed': async (payload) => {
    await notifyUser(payload.targetId, {
      title: 'Complaint Filed',
      body: `A complaint has been filed against you. Type: ${payload.type}. Please respond within 72 hours.`,
      telegramChatId: payload.targetTelegramId,
      whatsappPhone: payload.targetWhatsappPhone,
    });
  },

  'complaint.resolved': async (payload) => {
    await notifyUser(payload.reporterId, {
      title: 'Complaint Resolved',
      body: `Your complaint has been resolved. Resolution: ${payload.resolution}`,
      telegramChatId: payload.reporterTelegramId,
      whatsappPhone: payload.reporterWhatsappPhone,
    });
  },

  'user.auto_blocked': async (payload) => {
    await notifyUser(payload.userId, {
      title: 'Account Temporarily Blocked',
      body: 'Your account has been temporarily blocked due to multiple unresolved complaints. Please contact support.',
      telegramChatId: payload.telegramChatId,
      whatsappPhone: payload.whatsappPhone,
    });
  },

  // Search notification for saved filters
  'search.new_match': async (payload) => {
    await notifyUser(payload.userId, {
      title: 'New Purchase Matches Your Filter',
      body: `"${payload.purchaseTitle}" matches your saved filter "${payload.filterName}"`,
      buttons: [{ title: 'View Purchase', action: `view_purchase:${payload.purchaseId}` }],
      telegramChatId: payload.telegramChatId,
      whatsappPhone: payload.whatsappPhone,
    });
  },
};

// ─── Kafka Consumer ───────────────────────────────────────────────────────────

const kafka = new Kafka({
  clientId: config.kafka.clientId,
  brokers: config.kafka.brokers,
  logLevel: logLevel.WARN,
  retry: {
    initialRetryTime: 300,
    retries: 10,
    maxRetryTime: 30000,
    factor: 0.2,
  },
});

const consumer = kafka.consumer({
  groupId: config.kafka.groupId,
  sessionTimeout: 30000,
  heartbeatInterval: 3000,
  maxWaitTimeInMs: 5000,
  retry: {
    initialRetryTime: 300,
    retries: 10,
    maxRetryTime: 30000,
  },
});

const TOPICS = Object.keys(eventHandlers);

async function startConsumer() {
  await consumer.connect();
  console.log('[KAFKA] Consumer connected');

  for (const topic of TOPICS) {
    await consumer.subscribe({ topic, fromBeginning: false });
  }
  console.log(`[KAFKA] Subscribed to: ${TOPICS.join(', ')}`);

  await consumer.run({
    eachMessage: async ({ topic, partition, message }) => {
      const raw = message.value?.toString();
      if (!raw) return;

      let payload;
      try {
        payload = JSON.parse(raw);
      } catch (err) {
        console.error(`[KAFKA] Invalid JSON on topic ${topic}: ${raw}`);
        return;
      }

      console.log(`[KAFKA] Processing ${topic} (partition ${partition})`);

      const handler = eventHandlers[topic];
      if (handler) {
        try {
          await handler(payload);
        } catch (err) {
          console.error(`[KAFKA] Handler error for ${topic}: ${err.message}`);
        }
      } else {
        console.warn(`[KAFKA] No handler for topic: ${topic}`);
      }
    },
  });
}

// ─── Health HTTP Server ────────────────────────────────────────────────────────

const server = http.createServer((req, res) => {
  if (req.url === '/health' && req.method === 'GET') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ status: 'ok', service: 'notification-service' }));
  } else if (req.url === '/internal/send-otp' && req.method === 'POST') {
    // Internal endpoint for auth-service to trigger OTP email delivery.
    let body = '';
    req.on('data', chunk => { body += chunk; });
    req.on('end', async () => {
      try {
        const { email, otp, subject, context } = JSON.parse(body);
        if (!email || !otp) {
          res.writeHead(400, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ error: 'email and otp are required' }));
          return;
        }
        const safeSubject = subject || (context === 'registration'
          ? 'Groupbuy — код подтверждения регистрации'
          : 'Groupbuy — код для входа');
        const html = `
          <div style="font-family:sans-serif;max-width:480px;margin:0 auto;">
            <h2 style="color:#2481cc;">GroupBuy</h2>
            <p>${context === 'registration' ? 'Для завершения регистрации введите код подтверждения:' : 'Ваш код для входа:'}</p>
            <div style="font-size:2rem;font-weight:bold;letter-spacing:0.3em;color:#2481cc;padding:12px 0;">${otp}</div>
            <p style="color:#999;font-size:0.9rem;">Код действителен 10 минут. Не передавайте его никому.</p>
          </div>`;
        const text = `Ваш код GroupBuy: ${otp}. Действителен 10 минут.`;
        await sendEmail(email, safeSubject, html, text);
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ sent: true }));
      } catch (err) {
        console.error(`[OTP] Handler error: ${err.message}`);
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'internal error' }));
      }
    });
  } else if (req.url === '/webhooks/telegram' && req.method === 'POST') {
    // Handle Telegram bot callbacks (interactive buttons)
    let body = '';
    req.on('data', chunk => { body += chunk; });
    req.on('end', () => {
      try {
        const update = JSON.parse(body);
        if (update.callback_query) {
          const callbackData = update.callback_query.data;
          const chatId = update.callback_query.message?.chat?.id;
          console.log(`[TELEGRAM] Callback: ${callbackData} from chat ${chatId}`);
          // Acknowledge the callback
          if (config.telegram.botToken) {
            axios.post(
              `${config.telegram.apiUrl}/bot${config.telegram.botToken}/answerCallbackQuery`,
              { callback_query_id: update.callback_query.id }
            ).catch(err => console.error(`[TELEGRAM] Callback answer error: ${err.message}`));
          }
        }
      } catch (err) {
        console.error(`[TELEGRAM] Webhook parse error: ${err.message}`);
      }
      res.writeHead(200);
      res.end('ok');
    });
  } else if (req.url === '/webhooks/whatsapp' && req.method === 'POST') {
    // Handle WhatsApp webhook callbacks
    let body = '';
    req.on('data', chunk => { body += chunk; });
    req.on('end', () => {
      try {
        const data = JSON.parse(body);
        console.log(`[WHATSAPP] Webhook received: ${JSON.stringify(data).substring(0, 200)}`);
      } catch (err) {
        console.error(`[WHATSAPP] Webhook parse error: ${err.message}`);
      }
      res.writeHead(200);
      res.end('ok');
    });
  } else if (req.method === 'GET' && req.url.startsWith('/webhooks/whatsapp')) {
    // WhatsApp webhook verification
    const urlObj = new URL(req.url, `http://localhost:${config.port}`);
    const mode = urlObj.searchParams.get('hub.mode');
    const token = urlObj.searchParams.get('hub.verify_token');
    const challenge = urlObj.searchParams.get('hub.challenge');
    if (mode === 'subscribe' && token === process.env.WHATSAPP_VERIFY_TOKEN) {
      res.writeHead(200, { 'Content-Type': 'text/plain' });
      res.end(challenge);
    } else {
      res.writeHead(403);
      res.end();
    }
  } else {
    res.writeHead(404);
    res.end();
  }
});

// ─── Startup ──────────────────────────────────────────────────────────────────

async function startConsumerWithRetry(maxRetries = 10, baseDelay = 3000) {
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      await startConsumer();
      return;
    } catch (err) {
      const delay = Math.min(baseDelay * attempt, 30000);
      console.error(`[KAFKA] Connection attempt ${attempt}/${maxRetries} failed: ${err.message}. Retrying in ${delay}ms...`);
      if (attempt === maxRetries) {
        throw err;
      }
      // Disconnect before retrying to reset consumer state and allow a clean reconnect
      try { await consumer.disconnect(); } catch (_) { /* ignore disconnect errors */ }
      await new Promise((resolve) => setTimeout(resolve, delay));
    }
  }
}

async function main() {
  server.listen(config.port, () => {
    console.log(`[HTTP] Health server running on :${config.port}`);
  });

  try {
    await startConsumerWithRetry();
  } catch (err) {
    console.error(`[KAFKA] Fatal error after all retries: ${err.message}`);
    process.exit(1);
  }
}

process.on('SIGINT', async () => {
  console.log('Shutting down...');
  await consumer.disconnect();
  server.close();
  process.exit(0);
});

process.on('SIGTERM', async () => {
  console.log('Shutting down...');
  await consumer.disconnect();
  server.close();
  process.exit(0);
});

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
