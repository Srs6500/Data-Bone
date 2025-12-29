"use client";

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import PDFUpload from '@/components/Upload/PDFUpload';
import CourseForm from '@/components/Upload/CourseForm';
import { CourseInfo } from '@/types';
import { uploadFile } from '@/lib/api';
import Logo from '@/components/Common/Logo';

export default function UploadPage() {
  const router = useRouter();
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [courseInfo, setCourseInfo] = useState<CourseInfo>({
    courseCode: '',
    institution: '',
    courseType: 'prerequisite',
    learningGoal: 'pass_exam',
    currentLevel: 'intermediate',
  });
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFileSelect = (file: File | null) => {
    setSelectedFile(file);
    setError(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    // Validation
    if (!selectedFile) {
      setError('Please select a PDF file');
      return;
    }

    if (!courseInfo.courseCode || !courseInfo.institution) {
      setError('Please fill in all required fields');
      return;
    }

    setIsUploading(true);

    try {
      const response = await uploadFile(selectedFile, courseInfo);
      
      // Store document ID for later use
      localStorage.setItem('documentId', response.document_id);
      
      // Redirect to dashboard
      router.push(`/dashboard?documentId=${response.document_id}`);
    } catch (err: any) {
      console.error('Upload error:', err);
      const errorMessage = err.response?.data?.detail 
        || err.message 
        || 'Failed to upload document. Please try again.';
      setError(errorMessage);
      setIsUploading(false);
    }
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
              href="/"
              className="text-gray-700 hover:text-purple-600 font-medium transition-colors"
            >
              ← Back to Home
            </Link>
          </div>
        </div>
      </nav>

      <div className="max-w-3xl mx-auto py-12 px-4">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-4xl md:text-5xl font-bold text-gray-900 mb-3">
            Upload Your Documents
          </h1>
          <p className="text-lg md:text-xl text-gray-600">
            Let DataBone identify knowledge gaps in your course materials
          </p>
        </div>

        {/* Upload Form */}
        <form onSubmit={handleSubmit} className="bg-white rounded-2xl shadow-xl p-8 md:p-10 space-y-8">
          {/* PDF Upload */}
          <PDFUpload
            onFileSelect={handleFileSelect}
            selectedFile={selectedFile}
          />

          {/* Course Info Form */}
          <CourseForm
            courseInfo={courseInfo}
            onCourseInfoChange={setCourseInfo}
          />

          {/* Error Message */}
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
              {error}
            </div>
          )}

          {/* Submit Button */}
          <button
            type="submit"
            disabled={isUploading || !selectedFile}
            className={`
              w-full py-4 px-6 rounded-xl font-bold text-lg text-white
              transition-all duration-200 shadow-lg
              ${isUploading || !selectedFile
                ? 'bg-gray-400 cursor-not-allowed'
                : 'bg-gradient-to-r from-blue-600 via-cyan-500 to-green-500 hover:from-blue-700 hover:via-cyan-600 hover:to-green-600 active:scale-95 shadow-xl hover:shadow-2xl'
              }
            `}
          >
            {isUploading ? (
              <span className="flex items-center justify-center">
                <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Analyzing Document...
              </span>
            ) : (
              'Analyze Document'
            )}
          </button>
        </form>
      </div>
    </div>
  );
}

