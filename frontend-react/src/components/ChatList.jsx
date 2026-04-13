import React from 'react';
import { ChatIcon } from './Icons';

function ChatList() {
  return (
    <div className="welcome-screen flex flex-col items-center justify-center" style={{ flex: 1 }}>
      <ChatIcon />
      <h2 className="mt-lg text-secondary">Добро пожаловать в GroupBuy</h2>
      <p className="mt-sm text-muted">Выберите закупку или создайте новую</p>
    </div>
  );
}

export default ChatList;
