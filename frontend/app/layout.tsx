import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'DataBone | AI-Powered Student Performance Enhancer',
  description: 'Create accurate tutoring sessions from your course material in seconds. AI-powered gap detection and personalized tutoring for CS and Math courses.',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  )
}


