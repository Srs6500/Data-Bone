"use client";

import React, { useState } from 'react';
import { Gap } from '@/types';

interface GapSidebarProps {
  criticalGaps: Gap[];
  safeGaps: Gap[];
  selectedGapId: string | null;
  onGapSelect: (gap: Gap) => void;
  expandedSection: 'critical' | 'safe' | null;
  onSectionToggle: (section: 'critical' | 'safe' | null) => void;
}

export default function GapSidebar({
  criticalGaps,
  safeGaps,
  selectedGapId,
  onGapSelect,
  expandedSection,
  onSectionToggle,
}: GapSidebarProps) {
  const handleSectionClick = (section: 'critical' | 'safe') => {
    // If clicking the same section, collapse it
    if (expandedSection === section) {
      onSectionToggle(null);
    } else {
      // Otherwise, expand this section and collapse the other
      onSectionToggle(section);
    }
  };

  return (
    <div className="w-full lg:w-80 bg-white border-r border-gray-200 flex flex-col h-auto lg:h-full max-h-[50vh] lg:max-h-none overflow-hidden">
      {/* Sidebar Header */}
      <div className="p-4 border-b border-gray-200 bg-gradient-to-r from-purple-50 to-indigo-50">
        <h2 className="text-lg font-semibold text-gray-900">Knowledge Gaps</h2>
        <p className="text-xs text-gray-600 mt-1">
          {criticalGaps.length + safeGaps.length} total gaps detected
        </p>
      </div>

      {/* Scrollable Gap List */}
      <div className="flex-1 overflow-y-auto">
        {/* Critical Gaps Section */}
        <div className="border-b border-gray-200">
          <button
            onClick={() => handleSectionClick('critical')}
            className="w-full px-4 py-3 flex items-center justify-between hover:bg-red-50 transition-colors"
          >
            <div className="flex items-center space-x-3">
              <span className="text-lg">🔴</span>
              <span className="font-semibold text-red-700">Critical Gaps</span>
              <span className="text-sm text-gray-600">({criticalGaps.length})</span>
            </div>
            <svg
              className={`w-5 h-5 text-gray-600 transition-transform ${
                expandedSection === 'critical' ? 'rotate-180' : ''
              }`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M19 9l-7 7-7-7"
              />
            </svg>
          </button>

          {/* Critical Gaps List (shown when expanded) */}
          {expandedSection === 'critical' && (
            <div className="bg-red-50/30">
              {criticalGaps.length > 0 ? (
                <div className="py-2">
                  {criticalGaps.map((gap, index) => (
                    <button
                      key={gap.id}
                      onClick={() => onGapSelect(gap)}
                      className={`w-full px-4 py-3 text-left hover:bg-red-100 transition-colors border-l-4 ${
                        selectedGapId === gap.id
                          ? 'bg-red-100 border-red-600 font-semibold'
                          : 'border-transparent'
                      }`}
                    >
                      <div className="flex items-start space-x-2">
                        <span className="text-sm text-red-700 font-medium min-w-[24px]">
                          {index + 1}.
                        </span>
                        <span
                          className={`text-sm ${
                            selectedGapId === gap.id
                              ? 'text-red-900 font-semibold'
                              : 'text-red-800'
                          }`}
                        >
                          {gap.concept || 'Unnamed Concept'}
                        </span>
                      </div>
                    </button>
                  ))}
                </div>
              ) : (
                <div className="px-4 py-6 text-center text-sm text-gray-500">
                  No critical gaps found
                </div>
              )}
            </div>
          )}
        </div>

        {/* Safe Gaps Section */}
        <div className="border-b border-gray-200">
          <button
            onClick={() => handleSectionClick('safe')}
            className="w-full px-4 py-3 flex items-center justify-between hover:bg-green-50 transition-colors"
          >
            <div className="flex items-center space-x-3">
              <span className="text-lg">🟢</span>
              <span className="font-semibold text-green-700">Safe Gaps</span>
              <span className="text-sm text-gray-600">({safeGaps.length})</span>
            </div>
            <svg
              className={`w-5 h-5 text-gray-600 transition-transform ${
                expandedSection === 'safe' ? 'rotate-180' : ''
              }`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M19 9l-7 7-7-7"
              />
            </svg>
          </button>

          {/* Safe Gaps List (shown when expanded) */}
          {expandedSection === 'safe' && (
            <div className="bg-green-50/30">
              {safeGaps.length > 0 ? (
                <div className="py-2">
                  {safeGaps.map((gap, index) => (
                    <button
                      key={gap.id}
                      onClick={() => onGapSelect(gap)}
                      className={`w-full px-4 py-3 text-left hover:bg-green-100 transition-colors border-l-4 ${
                        selectedGapId === gap.id
                          ? 'bg-green-100 border-green-600 font-semibold'
                          : 'border-transparent'
                      }`}
                    >
                      <div className="flex items-start space-x-2">
                        <span className="text-sm text-green-700 font-medium min-w-[24px]">
                          {index + 1}.
                        </span>
                        <span
                          className={`text-sm ${
                            selectedGapId === gap.id
                              ? 'text-green-900 font-semibold'
                              : 'text-green-800'
                          }`}
                        >
                          {gap.concept || 'Unnamed Concept'}
                        </span>
                      </div>
                    </button>
                  ))}
                </div>
              ) : (
                <div className="px-4 py-6 text-center text-sm text-gray-500">
                  No safe gaps found
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

