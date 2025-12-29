/**
 * API client for communicating with the backend
 */
import axios from 'axios';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// File upload requires multipart/form-data
export const uploadFile = async (file: File, courseInfo: any) => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('course_info_json', JSON.stringify(courseInfo));
  
  // Use axios directly with proper headers for file upload
  const response = await axios.post(
    `${API_BASE_URL}/api/upload`,
    formData,
    {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    }
  );
  
  return response.data;
};

// Health check
export const healthCheck = async () => {
  const response = await apiClient.get('/health');
  return response.data;
};

// Analyze document for gaps
export const analyzeDocument = async (documentId: string) => {
  const response = await apiClient.post('/api/analyze', {
    document_id: documentId,
  });
  return response.data;
};

// Chat API functions
export interface ChatRequest {
  documentId: string;
  message: string;
  conversationHistory?: Array<{ role: 'user' | 'assistant'; content: string }>;
  gapConcepts?: string[];
  filterType?: 'critical' | 'safe' | 'all';
}

export interface ChatResponse {
  response: string;
  document_id: string;
}

/**
 * Send a chat message to the AI tutor
 */
export const sendChatMessage = async (request: ChatRequest): Promise<ChatResponse> => {
  const response = await apiClient.post<ChatResponse>('/api/chat', {
    document_id: request.documentId,
    message: request.message,
    conversation_history: request.conversationHistory || [],
    gap_concepts: request.gapConcepts || [],
    filter_type: request.filterType || null,
  });
  return response.data;
};

/**
 * Auto-explain gap concepts (for auto-injection)
 */
export const explainGaps = async (
  documentId: string,
  gapConcepts: string[]
): Promise<{ explanation: string; gap_concept: string; document_id: string }> => {
  const response = await apiClient.post('/api/chat/explain-gap', {
    document_id: documentId,
    gap_concept: gapConcepts.join(', '), // Backend expects single string for now
  });
  return response.data;
};

export default apiClient;

