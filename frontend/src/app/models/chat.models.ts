export interface Citation {
  documentId: string;
  documentName?: string | null;
  pageNumber: number;
  snippet: string;
  relevanceScore: number;
}

export interface ChatMessage {
  id: string;
  chatSessionId: string;
  role: 'User' | 'Assistant';
  content: string;
  citations?: Citation[] | null;
  createdAtUtc: string;
  isLoading?: boolean; // UI flag for pending assistant response
}

export interface ChatSession {
  id: string;
  title: string;
  createdAtUtc: string;
  updatedAtUtc: string;
}

export interface SendMessageRequest {
  question: string;
  documentIds: string[];
}
