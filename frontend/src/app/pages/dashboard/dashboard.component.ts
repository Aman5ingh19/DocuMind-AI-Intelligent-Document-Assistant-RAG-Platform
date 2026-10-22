import { Component, OnInit, OnDestroy, inject, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpEventType } from '@angular/common/http';
import { AuthService } from '../../services/auth.service';
import { DocumentService } from '../../services/document.service';
import { ChatService } from '../../services/chat.service';
import { ToastService } from '../../services/toast.service';
import { DocumentSummary } from '../../models/document.models';
import { ChatMessage, Citation } from '../../models/chat.models';
import { marked } from 'marked';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './dashboard.component.html',
  styleUrls: ['./dashboard.component.scss']
})
export class DashboardComponent implements OnInit, OnDestroy {
  authService = inject(AuthService);
  docService = inject(DocumentService);
  chatService = inject(ChatService);
  toastService = inject(ToastService);

  // UI state
  activeTab = signal<'docs' | 'chats'>('docs');
  isDragging = false;
  uploadProgress = signal<number | null>(null);
  currentQuestion = '';
  documentSearchQuery = '';
  activeModalCitation = signal<Citation | null>(null);
  selectedDocumentDetail = signal<DocumentSummary | null>(null);
  isDarkMode = signal<boolean>(true);

  private pollInterval: any = null;

  // Computed properties
  filteredDocuments = computed(() => {
    const query = this.documentSearchQuery.toLowerCase().trim();
    const docs = this.docService.documents();
    if (!query) return docs;
    return docs.filter(d => d.fileName.toLowerCase().includes(query));
  });

  completedDocuments = computed(() => {
    return this.docService.documents().filter(d => d.status === 'Completed');
  });

  selectedDocsSummary = computed(() => {
    const selectedIds = this.chatService.selectedDocumentIds();
    const allDocs = this.docService.documents();
    return allDocs.filter(d => selectedIds.includes(d.id));
  });

  allCompletedSelected = computed(() => {
    const completed = this.completedDocuments();
    if (completed.length === 0) return false;
    const selected = this.chatService.selectedDocumentIds();
    return completed.every(d => selected.includes(d.id));
  });

  ngOnInit() {
    this.refreshData();
    // Start polling every 4 seconds for processing documents
    this.pollInterval = setInterval(() => {
      const hasProcessing = this.docService.documents().some(
        d => d.status === 'Processing' || d.status === 'Pending'
      );
      if (hasProcessing) {
        this.docService.loadDocuments().subscribe();
      }
    }, 4000);
  }

  ngOnDestroy() {
    if (this.pollInterval) {
      clearInterval(this.pollInterval);
    }
  }

  refreshData() {
    this.docService.loadDocuments().subscribe({
      next: (docs) => {
        // Auto-select completed documents if none selected yet
        if (this.chatService.selectedDocumentIds().length === 0) {
          const completedIds = docs.filter(d => d.status === 'Completed').map(d => d.id);
          this.chatService.selectAllDocuments(completedIds);
        }
      }
    });

    this.chatService.loadSessions().subscribe({
      next: (sessions) => {
        if (sessions.length > 0 && !this.chatService.activeSessionId()) {
          this.chatService.selectSession(sessions[0].id);
        } else if (sessions.length === 0) {
          this.createNewChat();
        }
      }
    });
  }

  // --- Document Upload ---

  onDragOver(event: DragEvent) {
    event.preventDefault();
    event.stopPropagation();
    this.isDragging = true;
  }

  onDragLeave(event: DragEvent) {
    event.preventDefault();
    event.stopPropagation();
    this.isDragging = false;
  }

  onDrop(event: DragEvent) {
    event.preventDefault();
    event.stopPropagation();
    this.isDragging = false;

    if (event.dataTransfer?.files && event.dataTransfer.files.length > 0) {
      this.handleFileSelected(event.dataTransfer.files[0]);
    }
  }

  onFileChange(event: Event) {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      this.handleFileSelected(input.files[0]);
      input.value = ''; // Reset input
    }
  }

  private handleFileSelected(file: File) {
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      this.toastService.error('Please upload a PDF file (.pdf).');
      return;
    }

    if (file.size > 30 * 1024 * 1024) {
      this.toastService.error('File size exceeds the 30MB limit.');
      return;
    }

    this.uploadProgress.set(0);
    this.docService.uploadDocument(file).subscribe({
      next: (event) => {
        if (event.type === HttpEventType.UploadProgress && event.total) {
          this.uploadProgress.set(Math.round((100 * event.loaded) / event.total));
        } else if (event.type === HttpEventType.Response) {
          this.uploadProgress.set(null);
          this.toastService.success(`"${file.name}" uploaded! Processing started.`);
          this.docService.loadDocuments().subscribe((docs) => {
            const uploaded = docs.find(d => d.fileName === file.name);
            if (uploaded) {
              this.chatService.toggleDocumentSelection(uploaded.id);
            }
          });
        }
      },
      error: (err) => {
        this.uploadProgress.set(null);
        const msg = err.error?.detail || err.error?.error || 'Failed to upload document.';
        this.toastService.error(msg);
      }
    });
  }

  // --- Document Actions ---

  toggleDocument(id: string) {
    this.chatService.toggleDocumentSelection(id);
  }

  toggleSelectAll() {
    if (this.allCompletedSelected()) {
      this.chatService.clearSelectedDocuments();
    } else {
      const allIds = this.completedDocuments().map(d => d.id);
      this.chatService.selectAllDocuments(allIds);
    }
  }

  downloadDocument(id: string, fileName: string) {
    this.docService.downloadDocument(id).subscribe({
      next: (blob) => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = fileName;
        a.click();
        window.URL.revokeObjectURL(url);
      },
      error: () => this.toastService.error('Could not download document file.')
    });
  }

  retryDocument(id: string) {
    this.docService.retryProcessing(id).subscribe({
      next: () => this.toastService.info('Processing re-queued.'),
      error: () => this.toastService.error('Failed to retry processing.')
    });
  }

  deleteDocument(doc: DocumentSummary, event: Event) {
    event.stopPropagation();
    if (!confirm(`Are you sure you want to delete "${doc.fileName}"? Its vector index will also be cleared.`)) {
      return;
    }

    this.docService.deleteDocument(doc.id).subscribe({
      next: () => {
        this.toastService.success(`Deleted "${doc.fileName}".`);
        // Remove from selected list if present
        if (this.chatService.selectedDocumentIds().includes(doc.id)) {
          this.chatService.toggleDocumentSelection(doc.id);
        }
      },
      error: () => this.toastService.error('Failed to delete document.')
    });
  }

  // --- Chat Actions ---

  createNewChat() {
    this.chatService.createSession().subscribe({
      next: () => {
        this.currentQuestion = '';
      },
      error: () => this.toastService.error('Failed to create new chat.')
    });
  }

  selectChat(sessionId: string) {
    this.chatService.selectSession(sessionId);
  }

  deleteChat(sessionId: string, event: Event) {
    event.stopPropagation();
    if (!confirm('Are you sure you want to delete this chat session?')) return;

    this.chatService.deleteSession(sessionId).subscribe({
      next: () => this.toastService.info('Chat session removed.'),
      error: () => this.toastService.error('Failed to delete chat session.')
    });
  }

  sendQuestion() {
    const question = this.currentQuestion.trim();
    if (!question || this.chatService.isSending()) return;

    const selectedDocIds = this.chatService.selectedDocumentIds();
    if (selectedDocIds.length === 0) {
      this.toastService.error('Please select at least one ready document on the left panel.');
      return;
    }

    let activeId = this.chatService.activeSessionId();
    if (!activeId) {
      this.chatService.createSession().subscribe({
        next: (session) => {
          this.executeSendMessage(session.id, question, selectedDocIds);
        }
      });
    } else {
      this.executeSendMessage(activeId, question, selectedDocIds);
    }
  }

  private executeSendMessage(sessionId: string, question: string, docIds: string[]) {
    this.currentQuestion = '';
    this.chatService.sendMessage(sessionId, question, docIds).subscribe({
      next: () => {
        this.scrollChatToBottom();
      },
      error: (err) => {
        const msg = err.error?.detail || err.error?.error || 'Failed to get answer from AI.';
        this.toastService.error(msg);
      }
    });
  }

  useStarterPrompt(prompt: string) {
    this.currentQuestion = prompt;
    this.sendQuestion();
  }

  onTextareaKeydown(event: KeyboardEvent) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      this.sendQuestion();
    }
  }

  scrollChatToBottom() {
    setTimeout(() => {
      const container = document.getElementById('chatMessagesContainer');
      if (container) {
        container.scrollTop = container.scrollHeight;
      }
    }, 100);
  }

  // --- Citation Modal ---

  openCitationModal(citation: Citation) {
    this.activeModalCitation.set(citation);
  }

  closeCitationModal() {
    this.activeModalCitation.set(null);
  }

  // --- Formatters ---

  renderMarkdown(text: string): string {
    if (!text) return '';
    try {
      return marked.parse(text) as string;
    } catch {
      return text;
    }
  }

  formatFileSize(bytes: number): string {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  }

  formatDate(dateStr: string): string {
    try {
      const date = new Date(dateStr);
      return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
    } catch {
      return dateStr;
    }
  }

  toggleTheme() {
    this.isDarkMode.update(dark => !dark);
    if (this.isDarkMode()) {
      document.body.classList.remove('theme-light');
      document.body.classList.add('theme-dark');
    } else {
      document.body.classList.remove('theme-dark');
      document.body.classList.add('theme-light');
    }
  }

  logout() {
    this.authService.logout();
  }
}
