"use client";

import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { analyzeDocument } from '@/lib/api';
import { Gap, AnalysisResult } from '@/types';
import Logo from '@/components/Common/Logo';
import ChatSlideOver from '@/components/Chat/ChatSlideOver';
import FloatingChatButton from '@/components/Chat/FloatingChatButton';

export default function DashboardPage() {
  const searchParams = useSearchParams();
  const documentId = searchParams.get('documentId');
  
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [analysisResult, setAnalysisResult] = useState<AnalysisResult | null>(null);
  const [activeFilter, setActiveFilter] = useState<'all' | 'critical' | 'safe'>('critical'); // Default to critical
  
  // Chat state
  const [chatOpen, setChatOpen] = useState(false);
  const [chatGapConcepts, setChatGapConcepts] = useState<string[]>([]);
  const [chatFilterType, setChatFilterType] = useState<'critical' | 'safe' | 'all' | undefined>(undefined);

  useEffect(() => {
    if (documentId) {
      analyzeDocumentGaps();
    } else {
      setError('No document ID provided');
      setLoading(false);
    }
  }, [documentId]);

  const analyzeDocumentGaps = async () => {
    if (!documentId) return;
    
    setAnalyzing(true);
    setError(null);
    
    try {
      const result = await analyzeDocument(documentId);
      setAnalysisResult(result);
    } catch (err: any) {
      console.error('Analysis error:', err);
      setError(err.response?.data?.detail || 'Failed to analyze document. Please try again.');
    } finally {
      setLoading(false);
      setAnalyzing(false);
    }
  };

  if (loading || analyzing) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">
            {analyzing ? 'Analyzing document and detecting gaps...' : 'Loading...'}
          </p>
          {analyzing && (
            <div className="mt-4 space-y-2 text-sm text-gray-500">
              <p>✓ Document uploaded</p>
              <p>✓ Text extracted</p>
              <p>⏳ Generating embeddings...</p>
              <p>⏳ Analyzing with AI...</p>
              <p>⏳ Detecting gaps...</p>
            </div>
          )}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center">
        <div className="bg-white rounded-lg shadow-lg p-8 max-w-md">
          <p className="text-red-600 mb-4">{error}</p>
          <button
            onClick={analyzeDocumentGaps}
            className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700"
          >
            Try Again
          </button>
        </div>
      </div>
    );
  }

  if (!analysisResult) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center">
        <div className="bg-white rounded-lg shadow-lg p-8 max-w-md">
          <p className="text-gray-600">No analysis results available.</p>
        </div>
      </div>
    );
  }

  // Keep all gaps in state (never filter the source data)
  const allGaps = analysisResult.gaps;
  const criticalGaps = allGaps.filter(g => g.category === 'critical');
  const safeGaps = allGaps.filter(g => g.category === 'safe');
  
  // Filter gaps for display based on active filter
  const displayedGaps = activeFilter === 'all' 
    ? allGaps 
    : activeFilter === 'critical' 
      ? criticalGaps 
      : safeGaps;

  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-50 via-pink-50 to-indigo-50">
      {/* Navigation */}
      <nav className="bg-white/80 backdrop-blur-md border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-20 md:h-24">
            <Link href="/" className="flex items-center space-x-3 hover:opacity-80 transition-opacity">
              <Logo size="lg" showText={true} />
            </Link>
            <Link
              href="/upload"
              className="text-gray-700 hover:text-purple-600 font-medium transition-colors"
            >
              Upload Another Document
            </Link>
          </div>
        </div>
      </nav>

      <div className="max-w-6xl mx-auto py-8 md:py-12 px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="text-center mb-10">
          <div className="inline-block mb-4">
            <div className="w-16 h-16 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-2xl flex items-center justify-center mx-auto shadow-lg">
              <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
              </svg>
            </div>
          </div>
          <h1 className="text-4xl md:text-5xl font-bold text-gray-900 mb-3">
            Analysis Results
          </h1>
          <p className="text-lg md:text-xl text-gray-600 max-w-2xl mx-auto">
            Knowledge gaps detected in your document. Review critical gaps first, then explore safe gaps for deeper understanding.
          </p>
        </div>

        {/* Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
          {/* Total Gaps Card */}
          <div className="bg-white rounded-lg shadow-md hover:shadow-lg transition-shadow duration-300 p-4 border-2 border-gray-200">
            <div className="flex items-center justify-between mb-2">
              <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-lg flex items-center justify-center">
                <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
              </div>
            </div>
            <div className="text-3xl font-bold text-gray-900 mb-1">{analysisResult.totalGaps}</div>
            <div className="text-xs font-semibold text-gray-600 uppercase tracking-wide">Total Gaps</div>
            <div className="text-xs text-gray-500 mt-1">Detected in your document</div>
          </div>

          {/* Critical Gaps Card */}
          <div className="bg-gradient-to-br from-red-50 to-red-100 rounded-lg shadow-md hover:shadow-lg transition-shadow duration-300 p-4 border-2 border-red-300">
            <div className="flex items-center justify-between mb-2">
              <div className="w-10 h-10 bg-red-600 rounded-lg flex items-center justify-center">
                <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
              </div>
            </div>
            <div className="text-3xl font-bold text-red-700 mb-1">{analysisResult.criticalGaps}</div>
            <div className="text-xs font-semibold text-red-800 uppercase tracking-wide">Critical Gaps</div>
            <div className="text-xs text-red-700 mt-1 font-medium">⚠️ Must know for exams</div>
          </div>

          {/* Safe Gaps Card */}
          <div className="bg-gradient-to-br from-green-50 to-green-100 rounded-lg shadow-md hover:shadow-lg transition-shadow duration-300 p-4 border-2 border-green-300">
            <div className="flex items-center justify-between mb-2">
              <div className="w-10 h-10 bg-green-600 rounded-lg flex items-center justify-center">
                <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
            </div>
            <div className="text-3xl font-bold text-green-700 mb-1">{analysisResult.safeGaps}</div>
            <div className="text-xs font-semibold text-green-800 uppercase tracking-wide">Safe Gaps</div>
            <div className="text-xs text-green-700 mt-1 font-medium">✓ Nice to know</div>
          </div>
        </div>

        {/* Learn More & Chat Button */}
        {displayedGaps.length > 0 && (
          <div className="mb-6 text-center">
            <button
              onClick={() => {
                const concepts = displayedGaps.map(g => g.concept);
                setChatGapConcepts(concepts);
                setChatFilterType(activeFilter);
                setChatOpen(true);
              }}
              className="px-6 py-3 bg-gradient-to-r from-purple-500 to-indigo-600 text-white rounded-lg font-semibold hover:from-purple-600 hover:to-indigo-700 shadow-lg hover:shadow-xl transition-all duration-200 flex items-center space-x-2 mx-auto"
            >
              <svg
                className="w-5 h-5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
                />
              </svg>
              <span>Learn More & Chat</span>
            </button>
          </div>
        )}

        {/* Filter Buttons */}
        <div className="mb-6">
          <div className="flex flex-wrap gap-4 justify-center">
            <button
              onClick={() => setActiveFilter('critical')}
              className={`px-6 py-3 rounded-lg font-semibold transition-all duration-200 flex items-center space-x-2 ${
                activeFilter === 'critical'
                  ? 'bg-red-600 text-white shadow-lg scale-105'
                  : 'bg-red-50 text-red-700 hover:bg-red-100 border-2 border-red-200'
              }`}
            >
              <span className="text-lg">🔴</span>
              <span>Critical ({criticalGaps.length})</span>
            </button>
            
            <button
              onClick={() => setActiveFilter('safe')}
              className={`px-6 py-3 rounded-lg font-semibold transition-all duration-200 flex items-center space-x-2 ${
                activeFilter === 'safe'
                  ? 'bg-green-600 text-white shadow-lg scale-105'
                  : 'bg-green-50 text-green-700 hover:bg-green-100 border-2 border-green-200'
              }`}
            >
              <span className="text-lg">🟢</span>
              <span>Safe ({safeGaps.length})</span>
            </button>
            
            <button
              onClick={() => setActiveFilter('all')}
              className={`px-6 py-3 rounded-lg font-semibold transition-all duration-200 flex items-center space-x-2 ${
                activeFilter === 'all'
                  ? 'bg-blue-600 text-white shadow-lg scale-105'
                  : 'bg-blue-50 text-blue-700 hover:bg-blue-100 border-2 border-blue-200'
              }`}
            >
              <span className="text-lg">📋</span>
              <span>All ({allGaps.length})</span>
            </button>
          </div>
        </div>

        {/* Total Count Display */}
        <div className="mb-6 text-center">
          <p className="text-lg font-semibold text-gray-700">
            Total: <span className="font-bold text-gray-900">{allGaps.length}</span> {allGaps.length === 1 ? 'gap' : 'gaps'} detected
          </p>
        </div>

        {/* Unified Gap List */}
        {displayedGaps.length > 0 ? (
          <div className="space-y-6">
            {displayedGaps.map((gap, index) => (
              <GapCard 
                key={gap.id} 
                gap={gap} 
                isCritical={gap.category === 'critical'} 
                index={index + 1} 
              />
            ))}
          </div>
        ) : (
          <div className="bg-gray-50 rounded-xl p-8 text-center border-2 border-gray-200">
            <p className="text-gray-600">
              {activeFilter === 'critical' 
                ? 'No critical gaps found.' 
                : activeFilter === 'safe'
                  ? 'No safe gaps found.'
                  : 'No gaps found.'}
            </p>
          </div>
        )}

        {/* No Gaps */}
        {analysisResult.gaps.length === 0 && (
          <div className="bg-gradient-to-br from-green-50 to-blue-50 rounded-xl shadow-lg p-12 text-center border-2 border-green-200">
            <div className="w-20 h-20 bg-gradient-to-br from-green-500 to-blue-500 rounded-full flex items-center justify-center mx-auto mb-6 shadow-lg">
              <svg className="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <h3 className="text-2xl font-bold text-gray-900 mb-3">
              Excellent Work! 🎉
            </h3>
            <p className="text-gray-700 text-lg max-w-md mx-auto leading-relaxed">
              No significant knowledge gaps detected. You're well prepared for your exams and assignments!
            </p>
          </div>
        )}
      </div>

      {/* Floating Chat Button (General Chat - No Gap Context) */}
      {analysisResult && documentId && (
        <FloatingChatButton
          onClick={() => {
            setChatGapConcepts([]); // No gap context for general chat
            setChatFilterType(undefined);
            setChatOpen(true);
          }}
        />
      )}

      {/* Chat Slide-Over */}
      {documentId && (
        <ChatSlideOver
          isOpen={chatOpen}
          onClose={() => setChatOpen(false)}
          documentId={documentId}
          gapConcepts={chatGapConcepts}
          filterType={chatFilterType}
          autoExplain={chatGapConcepts.length > 0} // Auto-explain if gap context provided
        />
      )}
    </div>
  );
}

// Gap Card Component
function GapCard({ gap, isCritical, index }: { gap: Gap; isCritical: boolean; index: number }) {
  const [expanded, setExpanded] = React.useState(false);

  return (
    <div
      className={`bg-white rounded-xl shadow-lg hover:shadow-xl transition-all duration-300 overflow-hidden ${
        isCritical 
          ? 'border-2 border-red-200 hover:border-red-300' 
          : 'border-2 border-green-200 hover:border-green-300'
      }`}
    >
      {/* Header Section */}
      <div className={`p-6 ${isCritical ? 'bg-gradient-to-r from-red-50 to-white' : 'bg-gradient-to-r from-green-50 to-white'}`}>
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-start space-x-4 flex-1">
            <div className={`flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center font-bold text-white shadow-md ${
              isCritical ? 'bg-red-600' : 'bg-green-600'
            }`}>
              {index}
            </div>
            <div className="flex-1 min-w-0">
              <h3 className={`text-xl md:text-2xl font-bold mb-2 break-words ${
                isCritical ? 'text-red-900' : 'text-green-900'
              }`}>
                {gap.concept || 'Unnamed Concept'}
              </h3>
              <div className={`inline-block px-3 py-1 rounded-full text-xs font-semibold ${
                isCritical 
                  ? 'bg-red-100 text-red-800 border border-red-200' 
                  : 'bg-green-100 text-green-800 border border-green-200'
              }`}>
                {isCritical ? 'CRITICAL' : 'SAFE'}
              </div>
            </div>
          </div>
        </div>

        {/* Explanation Section */}
        {gap.explanation && gap.explanation.trim().length > 0 && (
          <div className="mt-4 mb-4">
            <div className="flex items-center mb-2">
              <svg className="w-5 h-5 text-gray-500 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <p className="text-sm font-semibold text-gray-700 uppercase tracking-wide">Overview</p>
            </div>
            <p className="text-gray-700 leading-relaxed text-base pl-7 whitespace-pre-wrap">
              {expanded || gap.explanation.length <= 200 
                ? gap.explanation 
                : `${gap.explanation.substring(0, 200).trim()}...`}
            </p>
            {gap.explanation.length > 200 && (
              <button
                onClick={() => setExpanded(!expanded)}
                aria-expanded={expanded}
                className="mt-2 text-sm font-medium text-blue-600 hover:text-blue-800 pl-7 transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1 rounded"
              >
                {expanded ? 'Show less' : 'Read more'}
              </button>
            )}
          </div>
        )}

        {/* Why Needed Section */}
        {gap.whyNeeded && gap.whyNeeded.trim().length > 0 && (
          <div className={`mt-4 p-4 rounded-lg border-l-4 ${
            isCritical 
              ? 'bg-red-50 border-red-400' 
              : 'bg-green-50 border-green-400'
          }`}>
            <div className="flex items-center mb-2">
              <svg className={`w-5 h-5 mr-2 flex-shrink-0 ${
                isCritical ? 'text-red-600' : 'text-green-600'
              }`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <p className={`text-sm font-bold uppercase tracking-wide ${
                isCritical ? 'text-red-900' : 'text-green-900'
              }`}>
                Why This Is Important
              </p>
            </div>
            <p className={`text-sm leading-relaxed pl-7 whitespace-pre-wrap ${
              isCritical ? 'text-red-800' : 'text-green-800'
            }`}>
              {gap.whyNeeded}
            </p>
          </div>
        )}

        {/* Note: Chat functionality is available via "Learn More & Chat" button above filter buttons */}
      </div>
    </div>
  );
}
