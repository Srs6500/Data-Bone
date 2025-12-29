"use client";

import Link from 'next/link';
import Image from 'next/image';
import Navbar from '@/components/Common/Navbar';
import Logo from '@/components/Common/Logo';

export default function Home() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-cyan-50 to-green-50">
      <Navbar />
      
      {/* Hero Section */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-20 pb-16">
        <div className="text-center">
          {/* Main Headline */}
          <h1 className="text-5xl md:text-6xl lg:text-7xl font-bold text-gray-900 mb-6 leading-tight">
            Create accurate <span className="bg-gradient-to-r from-blue-600 via-cyan-500 to-green-500 bg-clip-text text-transparent">tutoring sessions</span> from your course material in seconds
          </h1>
          
          <p className="text-xl md:text-2xl text-gray-600 mb-10 max-w-3xl mx-auto leading-relaxed">
            AI-powered gap detection that identifies what you're missing and tutors you through it. 
            No more panicking before exams.
          </p>

          {/* CTA Button */}
          <Link
            href="/upload"
            className="inline-block bg-gradient-to-r from-blue-600 via-cyan-500 to-green-500 text-white font-bold text-lg px-8 py-4 rounded-xl hover:from-blue-700 hover:via-cyan-600 hover:to-green-600 transition-all duration-200 shadow-xl hover:shadow-2xl transform hover:scale-105"
          >
            Try For Free
          </Link>

          {/* Feature Icons Circle */}
          <div className="mt-16 relative">
            <div className="relative w-96 h-96 mx-auto">
              {/* Central Logo */}
              <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 z-10">
                <div className="bg-white rounded-full p-4 md:p-6 shadow-2xl border-4 border-blue-100">
                  <div className="w-24 h-24 md:w-32 md:h-32 relative">
                    <Image
                      src="/logo.png"
                      alt="DataBone Logo"
                      fill
                      className="object-contain"
                      priority
                    />
                  </div>
                </div>
              </div>

              {/* Feature Icons arranged in a circle */}
              <div className="absolute top-0 left-1/2 transform -translate-x-1/2">
                <FeatureIcon icon="📚" label="Notes" color="blue" />
              </div>
              <div className="absolute top-1/4 right-0 transform translate-x-1/2">
                <FeatureIcon icon="📝" label="Assignments" color="pink" />
              </div>
              <div className="absolute bottom-1/4 right-0 transform translate-x-1/2">
                <FeatureIcon icon="📄" label="Sample Papers" color="green" />
              </div>
              <div className="absolute bottom-0 left-1/2 transform -translate-x-1/2">
                <FeatureIcon icon="🎯" label="Gap Detection" color="orange" />
              </div>
              <div className="absolute bottom-1/4 left-0 transform -translate-x-1/2">
                <FeatureIcon icon="💬" label="AI Tutor" color="blue" />
              </div>
              <div className="absolute top-1/4 left-0 transform -translate-x-1/2">
                <FeatureIcon icon="🧠" label="Second Brain" color="yellow" />
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section id="features" className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
        <div className="text-center mb-16">
          <h2 className="text-4xl md:text-5xl font-bold text-gray-900 mb-4">
            Everything You Need to Excel
          </h2>
          <p className="text-xl text-gray-600 max-w-2xl mx-auto">
            Powerful features designed specifically for CS and Math students
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          <FeatureCard
            icon="📚"
            title="Multi-Document Support"
            description="Upload professor notes, assignments, sample papers, or lecture slides. Our AI works with any combination to give you complete coverage."
            color="blue"
          />
          <FeatureCard
            icon="🧠"
            title="Second Brain Intelligence"
            description="Our AI proactively suggests complex exam variations after you master a topic. No need to constantly prompt—we think ahead for you."
            color="cyan"
          />
          <FeatureCard
            icon="⚡"
            title="Instant Analysis"
            description="Get comprehensive gap analysis in seconds. No waiting, no manual work. Just upload and see what you're missing immediately."
            color="green"
          />
        </div>
      </section>

      {/* How It Works Section */}
      <section id="how-it-works" className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20 bg-white/50 rounded-3xl mx-4 mb-20">
        <div className="text-center mb-16">
          <h2 className="text-4xl md:text-5xl font-bold text-gray-900 mb-4">
            How It Works
          </h2>
          <p className="text-xl text-gray-600 max-w-2xl mx-auto">
            Our advanced RAG pipeline processes your documents and delivers insights
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-12">
          <StepCard
            number="1"
            title="Document Processing"
            description="We extract text from your PDFs, chunk it intelligently, and generate semantic embeddings using our local ML model (Sentence Transformers)."
            icon="📄"
          />
          <StepCard
            number="2"
            title="Vector Search & Analysis"
            description="Your document chunks are stored in ChromaDB. Our AI uses semantic search to find relevant context and analyzes gaps using Gemini."
            icon="🔎"
          />
          <StepCard
            number="3"
            title="Personalized Results"
            description="Get categorized gaps (Critical/Safe), detailed explanations, and context-aware tutoring—all tailored to your course and level."
            icon="🎓"
          />
        </div>
      </section>

      {/* Dashboard Section */}
      <section id="dashboard" className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
        <div className="text-center mb-16">
          <h2 className="text-4xl md:text-5xl font-bold text-gray-900 mb-4">
            Your Personal Learning Dashboard
          </h2>
          <p className="text-xl text-gray-600 max-w-2xl mx-auto">
            Visual insights and interactive tools to guide your study journey
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-12">
          {/* Summary Cards Preview */}
          <div className="bg-white rounded-2xl p-8 shadow-lg hover:shadow-xl transition-all border-2 border-blue-100">
            <div className="w-16 h-16 bg-gradient-to-br from-blue-500 to-cyan-500 rounded-xl flex items-center justify-center text-3xl mb-6">
              📊
            </div>
            <h3 className="text-2xl font-bold text-gray-900 mb-3">Summary Overview</h3>
            <p className="text-gray-600 leading-relaxed mb-4">
              Get an instant snapshot with three key metrics displayed in beautiful, color-coded cards.
            </p>
            <ul className="space-y-2 text-gray-600">
              <li className="flex items-center">
                <span className="text-blue-500 mr-2">📈</span>
                Total gaps count at a glance
              </li>
              <li className="flex items-center">
                <span className="text-red-500 mr-2">🔴</span>
                Critical gaps highlighted in red
              </li>
              <li className="flex items-center">
                <span className="text-green-500 mr-2">🟢</span>
                Safe gaps shown in green
              </li>
            </ul>
          </div>

          {/* Interactive Gap Cards Preview */}
          <div className="bg-white rounded-2xl p-8 shadow-lg hover:shadow-xl transition-all border-2 border-green-100">
            <div className="w-16 h-16 bg-gradient-to-br from-cyan-500 to-green-500 rounded-xl flex items-center justify-center text-3xl mb-6">
              🎯
            </div>
            <h3 className="text-2xl font-bold text-gray-900 mb-3">Detailed Gap Cards</h3>
            <p className="text-gray-600 leading-relaxed mb-4">
              Each gap comes with a beautifully formatted card showing concept name, explanation, why it's needed, and a chat button.
            </p>
            <ul className="space-y-2 text-gray-600">
              <li className="flex items-center">
                <span className="text-green-500 mr-2">💡</span>
                Expandable explanations
              </li>
              <li className="flex items-center">
                <span className="text-green-500 mr-2">💬</span>
                One-click chat access
              </li>
              <li className="flex items-center">
                <span className="text-green-500 mr-2">🎨</span>
                Color-coded by priority
              </li>
            </ul>
          </div>
        </div>

        {/* Dashboard Preview Info */}
        <div className="bg-gradient-to-br from-blue-50 via-cyan-50 to-green-50 rounded-2xl p-8 md:p-12 border-2 border-blue-200">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
            <div className="text-center">
              <div className="text-5xl mb-2">
                📚
              </div>
              <div className="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-1">Total Gaps</div>
              <div className="text-xs text-gray-600">Upload to see count</div>
            </div>
            <div className="text-center">
              <div className="text-5xl mb-2">
                ⚠️
              </div>
              <div className="text-sm font-semibold text-red-800 uppercase tracking-wide mb-1">Critical Gaps</div>
              <div className="text-xs text-red-700 font-medium">Must know for exams</div>
            </div>
            <div className="text-center">
              <div className="text-5xl mb-2">
                ✓
              </div>
              <div className="text-sm font-semibold text-green-800 uppercase tracking-wide mb-1">Safe Gaps</div>
              <div className="text-xs text-green-700 font-medium">Nice to know</div>
            </div>
          </div>
          <p className="text-center text-gray-700 text-lg">
            After uploading your documents, you'll see a comprehensive breakdown with actual numbers, helping you prioritize what to study first.
          </p>
        </div>
      </section>

      {/* CTA Section */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
        <div className="bg-gradient-to-r from-blue-600 via-cyan-500 to-green-500 rounded-3xl p-12 text-center text-white shadow-2xl">
          <h2 className="text-4xl md:text-5xl font-bold mb-4">
            Ready to Transform Your Learning?
          </h2>
          <p className="text-xl mb-8 opacity-90">
            Join students who are already using DataBone to ace their exams
          </p>
          <Link
            href="/upload"
            className="inline-block bg-white text-gray-900 font-bold text-lg px-8 py-4 rounded-xl hover:bg-gray-100 transition-all duration-200 shadow-xl hover:shadow-2xl transform hover:scale-105"
          >
            Get Started Free
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-gray-200 bg-white/50 py-8">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col md:flex-row items-center justify-between">
            <Logo size="md" showText={true} />
            <p className="text-gray-600 text-sm mt-4 md:mt-0">
              © 2025 DataBone. Built for students, powered by AI.
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}

// Feature Icon Component
function FeatureIcon({ icon, label, color }: { icon: string; label: string; color: 'blue' | 'cyan' | 'green' | 'orange' | 'pink' | 'yellow' }) {
  const colorClasses = {
    blue: 'bg-blue-100 border-blue-300',
    cyan: 'bg-cyan-100 border-cyan-300',
    green: 'bg-green-100 border-green-300',
    orange: 'bg-orange-100 border-orange-300',
    pink: 'bg-pink-100 border-pink-300',
    yellow: 'bg-yellow-100 border-yellow-300',
  };

  return (
    <div className={`${colorClasses[color]} rounded-full p-4 border-2 shadow-lg hover:scale-110 transition-transform cursor-pointer group`}>
      <div className="text-3xl mb-1">{icon}</div>
      <div className="text-xs font-semibold text-gray-700 group-hover:text-gray-900">{label}</div>
    </div>
  );
}

// Feature Card Component
function FeatureCard({ icon, title, description, color }: { icon: string; title: string; description: string; color: 'blue' | 'cyan' | 'green' }) {
  const colorClasses = {
    blue: 'from-blue-500 to-cyan-500',
    cyan: 'from-cyan-500 to-green-500',
    green: 'from-green-500 to-emerald-500',
  };

  return (
    <div className="bg-white rounded-2xl p-8 shadow-lg hover:shadow-xl transition-all duration-300 transform hover:-translate-y-2">
      <div className={`w-16 h-16 bg-gradient-to-br ${colorClasses[color]} rounded-xl flex items-center justify-center text-3xl mb-6`}>
        {icon}
      </div>
      <h3 className="text-2xl font-bold text-gray-900 mb-3">{title}</h3>
      <p className="text-gray-600 leading-relaxed">{description}</p>
    </div>
  );
}

// Step Card Component
function StepCard({ number, title, description, icon }: { number: string; title: string; description: string; icon: string }) {
  return (
    <div className="text-center">
      <div className="relative inline-block mb-6">
        <div className="w-20 h-20 bg-gradient-to-br from-blue-600 via-cyan-500 to-green-500 rounded-full flex items-center justify-center text-white text-3xl font-bold shadow-lg">
          {number}
        </div>
        <div className="absolute -top-2 -right-2 text-4xl">{icon}</div>
      </div>
      <h3 className="text-2xl font-bold text-gray-900 mb-3">{title}</h3>
      <p className="text-gray-600 leading-relaxed">{description}</p>
    </div>
  );
}


