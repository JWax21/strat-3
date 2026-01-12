import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'Arbitrage Scanner | Polymarket × Kalshi',
  description: 'Real-time arbitrage opportunities between prediction markets',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link 
          href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;600;700&display=swap" 
          rel="stylesheet" 
        />
        <link
          href="https://api.fontshare.com/v2/css?f[]=clash-display@400,500,600,700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="bg-midnight-950 text-white antialiased">
        {children}
      </body>
    </html>
  )
}

