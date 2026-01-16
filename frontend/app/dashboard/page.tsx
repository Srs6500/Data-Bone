"use client";

import React, { useEffect, useState, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { analyzeDocument, analyzeDocumentStream, ProgressEvent } from '@/lib/api';
import { Gap, AnalysisResult } from '@/types';
import Logo from '@/components/Common/Logo';
import ChatSlideOver from '@/components/Chat/ChatSlideOver';
import FloatingChatButton from '@/components/Chat/FloatingChatButton';
import GapSidebar from '@/components/Dashboard/GapSidebar';
import GapDetailView from '@/components/Dashboard/GapDetailView';

function DashboardContent() {
  const searchParams = useSearchParams();
  // Get documentId from URL params, with localStorage fallback for robustness
  const urlDocumentId = searchParams.get('documentId');
  const storedDocumentId = typeof window !== 'undefined' ? localStorage.getItem('documentId') : null;
  const documentId = urlDocumentId || storedDocumentId;
  
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [analysisResult, setAnalysisResult] = useState<AnalysisResult | null>(null);
  const [progressStage, setProgressStage] = useState<string>('');
  
  // Define stage order for progress tracking
  const stageOrder: { [key: string]: number } = {
    'uploaded': 1,
    'extracted': 2,
    'embeddings_generating': 3,
    'embeddings_generated': 4,
    'vector_db_storing': 5,
    'vector_db_stored': 6,
    'rag_retrieving': 7,
    'rag_retrieved': 8,
    'llm_analyzing': 9,
    'llm_analyzed': 10,
    'gaps_parsing': 11,
    'gaps_parsed': 12,
    'gaps_enhancing': 13,
    'gaps_enhanced': 14,
    'completed': 15,
  };
  
  const isStageCompleted = (stage: string): boolean => {
    if (!progressStage) return false;
    const currentOrder = stageOrder[progressStage] || 0;
    const checkOrder = stageOrder[stage] || 0;
    return currentOrder >= checkOrder;
  };
  
  // Sidebar state
  const [selectedGap, setSelectedGap] = useState<Gap | null>(null);
  const [expandedSection, setExpandedSection] = useState<'critical' | 'safe' | null>(null);
  
  // Chat state
  const [chatOpen, setChatOpen] = useState(false);
  const [chatGapConcepts, setChatGapConcepts] = useState<string[]>([]);
  const [chatFilterType, setChatFilterType] = useState<'critical' | 'safe' | 'all' | undefined>(undefined);

  useEffect(() => {
    if (documentId) {
      // If we used localStorage fallback, update URL to include documentId for proper navigation
      if (!urlDocumentId && storedDocumentId && typeof window !== 'undefined') {
        const newUrl = new URL(window.location.href);
        newUrl.searchParams.set('documentId', storedDocumentId);
        window.history.replaceState({}, '', newUrl.toString());
      }
      analyzeDocumentGaps();
    } else {
      setError('No document ID provided. Please upload a document first.');
      setLoading(false);
    }
  }, [documentId]);

  const analyzeDocumentGaps = async () => {
    if (!documentId) return;
    
    setAnalyzing(true);
    setError(null);
    setProgressStage('uploaded'); // Reset progress
    
    try {
      const result = await analyzeDocumentStream(documentId, (event: ProgressEvent) => {
        // Update progress stage
        setProgressStage(event.stage);
        console.log('Progress:', event.stage, event.message);
        
        // EMERGENCY FIX: Don't overwrite valid gaps with 0-gap results
        if (event.stage === 'completed' && event.data) {
          const gaps = event.data.gaps || [];
          const totalGaps = event.data.totalGaps || 0;
          
          // If we already have valid gaps and new result has 0 gaps, don't overwrite
          if (analysisResult && analysisResult.gaps.length > 0 && totalGaps === 0) {
            console.warn('⚠️ Received 0 gaps but we have valid gaps. Keeping existing gaps.');
            return; // Don't process this event
          }
        }
      });
      
      // EMERGENCY FIX: Only update if we got valid gaps or don't have any yet
      if (result && result.gaps && result.gaps.length > 0) {
        setAnalysisResult(result);
      } else if (!analysisResult) {
        // Only set if we don't have any result yet
        setAnalysisResult(result);
      } else {
        console.warn('⚠️ Received 0 gaps but we have existing gaps. Keeping existing gaps.');
      }
    } catch (err: any) {
      console.error('Analysis error:', err);
      setError(err.message || 'Failed to analyze document. Please try again.');
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
              <p className={isStageCompleted('uploaded') ? 'text-green-600' : ''}>
                {isStageCompleted('uploaded') ? '✓' : '⏳'} Document uploaded
              </p>
              <p className={isStageCompleted('extracted') ? 'text-green-600' : ''}>
                {isStageCompleted('extracted') ? '✓' : '⏳'} Text extracted
              </p>
              <p className={isStageCompleted('embeddings_generated') ? 'text-green-600' : ''}>
                {isStageCompleted('embeddings_generated') ? '✓' : '⏳'} Generating embeddings...
              </p>
              <p className={isStageCompleted('vector_db_stored') ? 'text-green-600' : ''}>
                {isStageCompleted('vector_db_stored') ? '✓' : '⏳'} Storing in vector database...
              </p>
              <p className={isStageCompleted('rag_retrieved') ? 'text-green-600' : ''}>
                {isStageCompleted('rag_retrieved') ? '✓' : '⏳'} RAG retrieval...
              </p>
              <p className={isStageCompleted('llm_analyzed') ? 'text-green-600' : ''}>
                {isStageCompleted('llm_analyzed') ? '✓' : '⏳'} Analyzing with AI...
              </p>
              <p className={isStageCompleted('gaps_parsed') ? 'text-green-600' : ''}>
                {isStageCompleted('gaps_parsed') ? '✓' : '⏳'} Detecting gaps...
              </p>
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

  // Separate gaps by category
  const allGaps = analysisResult.gaps;
  const criticalGaps = allGaps.filter(g => g.category === 'critical');
  const safeGaps = allGaps.filter(g => g.category === 'safe');

  // Handle gap selection from sidebar
  const handleGapSelect = (gap: Gap) => {
    setSelectedGap(gap);
  };

  // Handle "Learn More" button click - opens chat with specific gap context
  const handleLearnMore = (gap: Gap) => {
    setChatGapConcepts([gap.concept]);
    setChatFilterType(gap.category);
    setChatOpen(true);
  };

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

      {/* Summary Cards Section */}
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="text-center mb-6">
            <h1 className="text-3xl md:text-4xl font-bold text-gray-900 mb-2">
              Analysis Results
            </h1>
            <p className="text-lg text-gray-600">
              Knowledge gaps detected in your document
            </p>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
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
        </div>
      </div>

      {/* 3-Column Layout: Sidebar + Main + Chat Panel */}
      {analysisResult.gaps.length > 0 ? (
        <div className="flex flex-col lg:flex-row h-[calc(100vh-200px)] overflow-hidden">
          {/* Left Sidebar: Gap List */}
          <GapSidebar
            criticalGaps={criticalGaps}
            safeGaps={safeGaps}
            selectedGapId={selectedGap?.id || null}
            onGapSelect={handleGapSelect}
            expandedSection={expandedSection}
            onSectionToggle={setExpandedSection}
          />

          {/* Main Content Area: Gap Detail View */}
          <GapDetailView
            gap={selectedGap}
            onLearnMore={handleLearnMore}
          />
        </div>
      ) : (
        <div className="flex items-center justify-center min-h-[400px]">
          <div className="bg-gradient-to-br from-green-50 to-blue-50 rounded-xl shadow-lg p-12 text-center border-2 border-green-200 max-w-2xl mx-4">
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
        </div>
      )}

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

export default function DashboardPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading...</p>
        </div>
      </div>
    }>
      <DashboardContent />
    </Suspense>
  );
}
