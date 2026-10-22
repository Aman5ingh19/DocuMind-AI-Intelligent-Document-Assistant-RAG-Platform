import { Injectable, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, tap } from 'rxjs';
import { environment } from '../../environments/environment';
import { ChatMessage, ChatSession, SendMessageRequest } from '../models/chat.models';

@Injectable({
  providedIn: 'root'
})
export class ChatService {
  sessions = signal<ChatSession[]>([]);
  activeSessionId = signal<string | null>(null);
  messages = signal<ChatMessage[]>([]);
  selectedDocumentIds = signal<string[]>([]);
  isSending = signal<boolean>(false);

  constructor(private http: HttpClient) {}

  loadSessions(): Observable<ChatSession[]> {
    return this.http.get<ChatSession[]>(`${environment.apiUrl}/chat/sessions`).pipe(
      tap(sessions => this.sessions.set(sessions))
    );
  }

  createSession(title?: string): Observable<ChatSession> {
    return this.http.post<ChatSession>(`${environment.apiUrl}/chat/sessions`, { title }).pipe(
      tap(session => {
        this.sessions.update(list => [session, ...list]);
        this.activeSessionId.set(session.id);
        this.messages.set([]);
      })
    );
  }

  deleteSession(sessionId: string): Observable<void> {
    return this.http.delete<void>(`${environment.apiUrl}/chat/sessions/${sessionId}`).pipe(
      tap(() => {
        this.sessions.update(list => list.filter(s => s.id !== sessionId));
        if (this.activeSessionId() === sessionId) {
          const remaining = this.sessions();
          if (remaining.length > 0) {
            this.selectSession(remaining[0].id);
          } else {
            this.activeSessionId.set(null);
            this.messages.set([]);
          }
        }
      })
    );
  }

  loadMessages(sessionId: string): Observable<ChatMessage[]> {
    return this.http.get<ChatMessage[]>(`${environment.apiUrl}/chat/sessions/${sessionId}/messages`).pipe(
      tap(msgs => this.messages.set(msgs))
    );
  }

  selectSession(sessionId: string) {
    this.activeSessionId.set(sessionId);
    this.loadMessages(sessionId).subscribe();
  }

  sendMessage(sessionId: string, question: string, documentIds: string[]): Observable<ChatMessage> {
    this.isSending.set(true);

    // Optimistically add user question message
    const userMsg: ChatMessage = {
      id: 'temp-' + Date.now(),
      chatSessionId: sessionId,
      role: 'User',
      content: question,
      createdAtUtc: new Date().toISOString()
    };

    // Add placeholder assistant message with loading state
    const assistantMsgPlaceholder: ChatMessage = {
      id: 'temp-ai-' + Date.now(),
      chatSessionId: sessionId,
      role: 'Assistant',
      content: '',
      isLoading: true,
      createdAtUtc: new Date().toISOString()
    };

    this.messages.update(msgs => [...msgs, userMsg, assistantMsgPlaceholder]);

    const payload: SendMessageRequest = { question, documentIds };

    return this.http.post<ChatMessage>(`${environment.apiUrl}/chat/sessions/${sessionId}/messages`, payload).pipe(
      tap({
        next: (assistantMsg) => {
          // Replace placeholder with actual response
          this.messages.update(msgs =>
            msgs.map(m => m.id === assistantMsgPlaceholder.id ? assistantMsg : m)
          );
          // Refresh sessions list to update session title and timestamp
          this.loadSessions().subscribe();
          this.isSending.set(false);
        },
        error: () => {
          // Remove placeholder on error
          this.messages.update(msgs => msgs.filter(m => m.id !== assistantMsgPlaceholder.id));
          this.isSending.set(false);
        }
      })
    );
  }

  toggleDocumentSelection(documentId: string) {
    this.selectedDocumentIds.update(ids => {
      if (ids.includes(documentId)) {
        return ids.filter(id => id !== documentId);
      } else {
        return [...ids, documentId];
      }
    });
  }

  selectAllDocuments(documentIds: string[]) {
    this.selectedDocumentIds.set([...documentIds]);
  }

  clearSelectedDocuments() {
    this.selectedDocumentIds.set([]);
  }
}
