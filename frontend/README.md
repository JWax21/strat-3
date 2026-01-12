# Arbitrage Dashboard - Frontend

A real-time dashboard for viewing prediction market arbitrage opportunities between Polymarket and Kalshi.

## Features

- **Real-time Updates**: Auto-refreshes every 30 seconds
- **Beautiful UI**: Deep midnight theme with electric cyan/purple accents
- **Smooth Animations**: Powered by Framer Motion
- **Responsive Design**: Works on desktop and mobile
- **Filtering**: Search markets and set minimum price thresholds
- **Expandable Cards**: Click to see detailed trading strategies

## Tech Stack

- **Next.js 14** - React framework
- **TypeScript** - Type safety
- **Tailwind CSS** - Styling
- **Framer Motion** - Animations
- **Lucide React** - Icons
- **Recharts** - Charts
- **date-fns** - Date formatting

## Installation

```bash
npm install
```

## Development

```bash
npm run dev
```

The frontend will start at [http://localhost:3000](http://localhost:3000).

## Configuration

The frontend proxies API requests to the backend. Configure the backend URL in `next.config.js`:

```javascript
async rewrites() {
  return [
    {
      source: '/api/:path*',
      destination: 'http://localhost:8000/api/:path*',
    },
  ]
}
```

## Design System

### Colors
- **Midnight**: Deep dark backgrounds (#0a0b0f to #282d3a)
- **Electric Cyan**: Primary accent (#00fff7)
- **Electric Purple**: Secondary accent (#a855f7)
- **Profit Green**: Positive indicators (#10b981)
- **Loss Red**: Negative indicators (#ef4444)

### Typography
- **Display**: Clash Display for headings
- **Mono**: JetBrains Mono for data/numbers

## Build

```bash
npm run build
npm start
```

## Structure

```
frontend/
├── app/
│   ├── layout.tsx      # Root layout with fonts
│   ├── page.tsx        # Main dashboard page
│   └── globals.css     # Global styles + Tailwind
├── tailwind.config.ts  # Tailwind configuration
├── next.config.js      # Next.js configuration
└── package.json
```

