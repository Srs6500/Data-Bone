"use client";

import React from 'react';
import { CourseInfo } from '@/types';

interface CourseFormProps {
  courseInfo: CourseInfo;
  onCourseInfoChange: (info: CourseInfo) => void;
}

export default function CourseForm({ courseInfo, onCourseInfoChange }: CourseFormProps) {
  const handleChange = (field: keyof CourseInfo, value: string) => {
    onCourseInfoChange({
      ...courseInfo,
      [field]: value,
    });
  };

  return (
    <div className="space-y-6">
      <h3 className="text-lg font-semibold text-gray-900">Course Information</h3>
      
      <div className="grid grid-cols-1 gap-6">
        {/* Course Code */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Course Code <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            value={courseInfo.courseCode}
            onChange={(e) => handleChange('courseCode', e.target.value)}
            placeholder="e.g., CS 101, MATH 301"
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            required
          />
        </div>

        {/* Institution */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Institution Name <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            value={courseInfo.institution}
            onChange={(e) => handleChange('institution', e.target.value)}
            placeholder="e.g., Stanford University"
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            required
          />
        </div>

        {/* Course Name (Optional) */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Course Name <span className="text-gray-500 text-xs">(Optional)</span>
          </label>
          <input
            type="text"
            value={courseInfo.courseName || ''}
            onChange={(e) => handleChange('courseName', e.target.value)}
            placeholder="e.g., Introduction to Computer Science"
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          />
          <p className="mt-1 text-xs text-gray-500">
            Helps improve analysis accuracy by providing semantic context
          </p>
        </div>

        {/* Course Type */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Course Type <span className="text-red-500">*</span>
          </label>
          <select
            value={courseInfo.courseType}
            onChange={(e) => handleChange('courseType', e.target.value as CourseInfo['courseType'])}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            required
          >
            <option value="prerequisite">Prerequisite</option>
            <option value="core">Core</option>
            <option value="elective">Elective</option>
            <option value="advanced">Advanced</option>
          </select>
        </div>

        {/* Learning Goal */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Learning Goal <span className="text-red-500">*</span>
          </label>
          <select
            value={courseInfo.learningGoal}
            onChange={(e) => handleChange('learningGoal', e.target.value as CourseInfo['learningGoal'])}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            required
          >
            <option value="pass_exam">Pass Exam</option>
            <option value="ace_assignment">Ace Assignment</option>
            <option value="understand">Understand Concepts</option>
            <option value="all">All of the Above</option>
          </select>
        </div>

        {/* Current Level */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Your Current Level <span className="text-red-500">*</span>
          </label>
          <select
            value={courseInfo.currentLevel}
            onChange={(e) => handleChange('currentLevel', e.target.value as CourseInfo['currentLevel'])}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            required
          >
            <option value="beginner">Beginner</option>
            <option value="intermediate">Intermediate</option>
            <option value="advanced">Advanced</option>
          </select>
        </div>
      </div>
    </div>
  );
}


