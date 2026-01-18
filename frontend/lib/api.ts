/**
 * API client for communicating with the backend
 */
import axios from 'axios';
import type { AnalysisResult } from '@/types';

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

// Analyze document for gaps (legacy - non-streaming)
export const analyzeDocument = async (documentId: string) => {
  const response = await apiClient.post('/api/analyze', {
    document_id: documentId,
  });
  return response.data;
};

// Analyze document with real-time progress (SSE)
export interface ProgressEvent {
  stage: string;
  message: string;
  timestamp: string;
  data?: any;
}

export const analyzeDocumentStream = async (
  documentId: string,
  onProgress: (event: ProgressEvent) => void
): Promise<AnalysisResult> => {
  return new Promise((resolve, reject) => {
    // Use fetch with POST for SSE (EventSource only supports GET)
    fetch(`${API_BASE_URL}/api/analyze/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ document_id: documentId }),
    })
      .then((response) => {
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }

        const reader = response.body?.getReader();
        const decoder = new TextDecoder();

        if (!reader) {
          throw new Error('No response body');
        }

        let buffer = '';

        let completedReceived = false;
        
        const processStream = async () => {
          try {
            while (true) {
              const { done, value } = await reader.read();

              if (done) {
                // Check if we have any remaining data in buffer
                if (buffer.trim()) {
                  const lines = buffer.split('\n');
                  for (const line of lines) {
                    if (line.trim() && line.startsWith('data: ')) {
                      try {
                        const eventData = JSON.parse(line.slice(6));
                        console.log('Final SSE Event:', eventData.stage, eventData);
                        onProgress(eventData);
                        
                        if (eventData.stage === 'completed' && eventData.data) {
                          console.log('Resolving with final event data:', eventData.data);
                          completedReceived = true;
                          resolve(eventData.data);
                          return;
                        }
                      } catch (e) {
                        console.error('Error parsing final SSE event:', e);
                      }
                    }
                  }
                }
                // If we reach here and haven't resolved, the stream ended without completion
                if (!completedReceived) {
                  console.error('Stream ended without completed event. Buffer:', buffer);
                  reject(new Error('Analysis stream ended unexpectedly. The analysis may have completed, but the result was not received. Please try again.'));
                }
                break;
              }

              buffer += decoder.decode(value, { stream: true });
              const lines = buffer.split('\n');
              buffer = lines.pop() || ''; // Keep incomplete line in buffer

              for (const line of lines) {
                if (line.trim() && line.startsWith('data: ')) {
                  try {
                    const eventData = JSON.parse(line.slice(6));
                    console.log('SSE Event received:', eventData.stage, eventData);
                    onProgress(eventData);

                    if (eventData.stage === 'completed') {
                      console.log('Completed event received, data:', eventData.data);
                      if (eventData.data && eventData.data.gaps) {
                        // Validate that we have the expected structure
                        if (Array.isArray(eventData.data.gaps)) {
                          completedReceived = true;
                          resolve(eventData.data);
                          return;
                        } else {
                          console.error('Completed event data.gaps is not an array:', eventData.data);
                          reject(new Error('Analysis completed but data format is invalid'));
                          return;
                        }
                      } else {
                        console.error('Completed event missing data or gaps field:', eventData);
                        reject(new Error('Analysis completed but no gap data received'));
                        return;
                      }
                    } else if (eventData.stage === 'error') {
                      reject(new Error(eventData.message || 'Analysis failed'));
                      return;
                    }
                  } catch (e) {
                    console.error('Error parsing SSE event:', e, line);
                  }
                }
              }
            }
          } catch (error) {
            if (!completedReceived) {
              reject(error);
            }
          }
        };

        processStream();
      })
      .catch(reject);
  });
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

