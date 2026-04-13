# GroupBuy React Frontend

A Telegram-like web interface for the GroupBuy group purchasing platform, built with React.

## Features

- Telegram-like design with dark/light theme support
- Real-time chat via WebSocket
- Procurement management (view, create, join)
- User registration and personal cabinet
- Responsive design for mobile and desktop

## Technology Stack

- **React 18** - UI framework
- **React Router 6** - Client-side routing
- **Zustand** - State management
- **Vite** - Build tool
- **CSS Variables** - Theming

## Development

### Prerequisites

- Node.js 18+
- npm 9+

### Setup

```bash
# Install dependencies
npm install

# Start development server
npm run dev
```

The development server will start at http://localhost:3000 with hot reloading enabled.

### API Proxy

In development mode, API requests are proxied to `http://localhost:8000`:

- `/api/*` -> Backend API
- `/ws/*` -> WebSocket server

### Build

```bash
# Build for production
npm run build

# Preview production build
npm run preview
```

## Docker

### Build and run with Docker

```bash
# Build the image
docker build -t groupbuy-frontend .

# Run the container
docker run -p 3000:80 groupbuy-frontend
```

### With docker-compose

The frontend is included in the main `docker-compose.yml`:

```bash
# Start all services including frontend
docker-compose up -d

# Access the frontend at http://localhost:3000
```

## Project Structure

```
frontend-react/
├── public/             # Static assets
├── src/
│   ├── components/     # React components
│   ├── hooks/          # Custom hooks
│   ├── services/       # API and WebSocket services
│   ├── store/          # Zustand state management
│   ├── styles/         # CSS styles
│   ├── utils/          # Helper functions
│   ├── App.jsx         # Main application component
│   └── main.jsx        # Entry point
├── index.html          # HTML template
├── vite.config.js      # Vite configuration
├── package.json        # Dependencies
├── Dockerfile          # Docker build configuration
└── nginx.conf          # Nginx configuration for production
```

## Components

- **Layout** - Main application layout with sidebar
- **Sidebar** - Chat list and navigation
- **ProcurementSlider** - Horizontal slider of active procurements
- **ChatView** - Chat interface with messages
- **Cabinet** - User personal cabinet
- **LoginModal** - Registration form
- **ProcurementModal** - Procurement details
- **CreateProcurementModal** - Create new procurement
- **DepositModal** - Balance deposit
- **Toast** - Toast notifications

## State Management

The application uses Zustand for state management. The main store is located in `src/store/useStore.js` and includes:

- User authentication state
- Procurements list
- Chat messages
- Modal states
- Theme preferences

## Theming

The application supports dark and light themes using CSS variables. Theme can be toggled via the button in the header. The theme preference is persisted in localStorage.
