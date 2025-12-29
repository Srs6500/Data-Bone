"use client";

import Link from 'next/link';
import Logo from './Logo';

export default function Navbar() {
  return (
    <nav className="bg-white/80 backdrop-blur-md border-b border-gray-200 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-20 md:h-24">
          {/* Logo */}
          <Link href="/" className="flex items-center space-x-3 hover:opacity-80 transition-opacity">
            <Logo size="lg" showText={true} />
          </Link>

          {/* Navigation Links */}
          <div className="hidden md:flex items-center space-x-8">
            <Link
              href="/#features"
              className="text-gray-700 hover:bg-gradient-to-r hover:from-blue-600 hover:to-green-600 hover:bg-clip-text hover:text-transparent font-medium transition-all"
            >
              Features
            </Link>
            <Link
              href="/#how-it-works"
              className="text-gray-700 hover:bg-gradient-to-r hover:from-blue-600 hover:to-green-600 hover:bg-clip-text hover:text-transparent font-medium transition-all"
            >
              How It Works
            </Link>
            <Link
              href="/#dashboard"
              className="text-gray-700 hover:bg-gradient-to-r hover:from-blue-600 hover:to-green-600 hover:bg-clip-text hover:text-transparent font-medium transition-all"
            >
              Dashboard
            </Link>
          </div>

          {/* CTA Button */}
          <div className="flex items-center">
            <Link
              href="/upload"
              className="px-6 py-2 bg-gradient-to-r from-blue-600 via-cyan-500 to-green-500 text-white font-semibold rounded-lg hover:from-blue-700 hover:via-cyan-600 hover:to-green-600 transition-all shadow-md hover:shadow-lg transform hover:scale-105"
            >
              Get Started
            </Link>
          </div>
        </div>
      </div>
    </nav>
  );
}

