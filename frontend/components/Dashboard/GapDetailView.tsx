"use client";

import React, { useState } from 'react';
import { Gap } from '@/types';

interface GapDetailViewProps {
  gap: Gap | null;
  onLearnMore: (gap: Gap) => void;
}

export default function GapDetailView({ gap, onLearnMore }: GapDetailViewProps) {
  const [expanded, setExpanded] = useState(false);

  // Empty state when no gap is selected
  if (!gap) {
    return (
      <div className="flex-1 flex items-center justify-center bg-gradient-to-br from-gray-50 to-gray-100">
        <div className="text-center px-8">
          <div className="w-24 h-24 bg-gradient-to-br from-blue-100 to-indigo-100 rounded-full flex items-center justify-center mx-auto mb-6">
            <svg
              className="w-12 h-12 text-blue-600"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
              />
            </svg>
          </div>
          <h3 className="text-2xl font-bold text-gray-900 mb-3">
            Select a Gap to View Details
          </h3>
          <p className="text-gray-600 max-w-md mx-auto leading-relaxed">
            Click on any gap from the sidebar to see its explanation, why it's important, and get personalized tutoring.
          </p>
        </div>
      </div>
    );
  }

  const isCritical = gap.category === 'critical';

  return (
    <div className="flex-1 overflow-y-auto bg-gradient-to-br from-gray-50 to-gray-100">
      <div className="max-w-4xl mx-auto p-6 md:p-8">
        {/* Header Section */}
        <div
          className={`bg-white rounded-xl shadow-lg overflow-hidden mb-6 ${
            isCritical
              ? 'border-2 border-red-200'
              : 'border-2 border-green-200'
          }`}
        >
          <div
            className={`p-6 ${
              isCritical
                ? 'bg-gradient-to-r from-red-50 to-white'
                : 'bg-gradient-to-r from-green-50 to-white'
            }`}
          >
            <div className="flex items-start justify-between mb-4">
              <div className="flex-1">
                <div className="flex items-center space-x-3 mb-3">
                  <div
                    className={`flex-shrink-0 w-12 h-12 rounded-full flex items-center justify-center font-bold text-white shadow-md ${
                      isCritical ? 'bg-red-600' : 'bg-green-600'
                    }`}
                  >
                    {isCritical ? '🔴' : '🟢'}
                  </div>
                  <div>
                    <h2
                      className={`text-3xl md:text-4xl font-bold mb-2 break-words ${
                        isCritical ? 'text-red-900' : 'text-green-900'
                      }`}
                    >
                      {gap.concept || 'Unnamed Concept'}
                    </h2>
                    <div
                      className={`inline-block px-4 py-1 rounded-full text-sm font-semibold ${
                        isCritical
                          ? 'bg-red-100 text-red-800 border border-red-200'
                          : 'bg-green-100 text-green-800 border border-green-200'
                      }`}
                    >
                      {isCritical ? 'CRITICAL' : 'SAFE'}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Explanation Section */}
        {gap.explanation && gap.explanation.trim().length > 0 && (
          <div className="bg-white rounded-xl shadow-lg p-6 md:p-8 mb-6">
            <div className="flex items-center mb-4">
              <svg
                className="w-6 h-6 text-gray-500 mr-3"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
              <h3 className="text-xl font-bold text-gray-900 uppercase tracking-wide">
                Overview
              </h3>
            </div>
            <div className="pl-9">
              <p className="text-gray-700 leading-relaxed text-base md:text-lg whitespace-pre-wrap">
                {expanded || gap.explanation.length <= 300
                  ? gap.explanation
                  : `${gap.explanation.substring(0, 300).trim()}...`}
              </p>
              {gap.explanation.length > 300 && (
                <button
                  onClick={() => setExpanded(!expanded)}
                  className="mt-4 text-sm font-medium text-blue-600 hover:text-blue-800 transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1 rounded"
                >
                  {expanded ? 'Show less' : 'Read more'}
                </button>
              )}
            </div>
          </div>
        )}

        {/* Why Needed Section */}
        {gap.whyNeeded && gap.whyNeeded.trim().length > 0 && (
          <div
            className={`bg-white rounded-xl shadow-lg p-6 md:p-8 mb-6 border-l-4 ${
              isCritical
                ? 'bg-red-50/50 border-red-400'
                : 'bg-green-50/50 border-green-400'
            }`}
          >
            <div className="flex items-center mb-4">
              <svg
                className={`w-6 h-6 mr-3 flex-shrink-0 ${
                  isCritical ? 'text-red-600' : 'text-green-600'
                }`}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
              <h3
                className={`text-xl font-bold uppercase tracking-wide ${
                  isCritical ? 'text-red-900' : 'text-green-900'
                }`}
              >
                Why This Is Important
              </h3>
            </div>
            <div className="pl-9">
              <p
                className={`text-base md:text-lg leading-relaxed whitespace-pre-wrap ${
                  isCritical ? 'text-red-800' : 'text-green-800'
                }`}
              >
                {gap.whyNeeded}
              </p>
            </div>
          </div>
        )}

        {/* Learn More Button */}
        <div className="bg-white rounded-xl shadow-lg p-6">
          <button
            onClick={() => onLearnMore(gap)}
            className="w-full px-6 py-4 bg-gradient-to-r from-purple-500 to-indigo-600 text-white rounded-lg font-semibold hover:from-purple-600 hover:to-indigo-700 shadow-lg hover:shadow-xl transition-all duration-200 flex items-center justify-center space-x-3"
          >
            <svg
              className="w-6 h-6"
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
          <p className="text-sm text-gray-600 text-center mt-3">
            Get personalized tutoring and explanations for this gap
          </p>
        </div>
      </div>
    </div>
  );
}



