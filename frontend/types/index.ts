// Type definitions for the application

export interface CourseInfo {
  courseCode: string;
  institution: string;
  courseName?: string; // Optional: Course name for better RAG semantic matching
  courseType: 'prerequisite' | 'core' | 'elective' | 'advanced';
  learningGoal: 'pass_exam' | 'ace_assignment' | 'understand' | 'all';
  currentLevel: 'beginner' | 'intermediate' | 'advanced';
}

export interface Gap {
  id: string;
  concept: string;
  category: 'critical' | 'safe';
  explanation: string;
  whyNeeded: string;
  estimatedTime?: number;
}

export interface AnalysisResult {
  documentId: string;
  gaps: Gap[];
  totalGaps: number;
  criticalGaps: number;
  safeGaps: number;
  analyzedAt: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
}

export interface Question {
  id: string;
  concept: string;
  question: string;
  difficulty: 'basic' | 'intermediate' | 'advanced';
  type: 'concept_check' | 'application' | 'exam_style';
}


