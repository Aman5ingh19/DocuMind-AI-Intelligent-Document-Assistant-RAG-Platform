import { Injectable, signal } from '@angular/core';
import { HttpClient, HttpEvent, HttpRequest } from '@angular/common/http';
import { Observable, tap } from 'rxjs';
import { environment } from '../../environments/environment';
import { DocumentDetail, DocumentSummary } from '../models/document.models';

@Injectable({
  providedIn: 'root'
})
export class DocumentService {
  documents = signal<DocumentSummary[]>([]);
  isLoading = signal<boolean>(false);

  constructor(private http: HttpClient) {}

  loadDocuments(): Observable<DocumentSummary[]> {
    this.isLoading.set(true);
    return this.http.get<DocumentSummary[]>(`${environment.apiUrl}/documents`).pipe(
      tap({
        next: (docs) => {
          this.documents.set(docs);
          this.isLoading.set(false);
        },
        error: () => this.isLoading.set(false)
      })
    );
  }

  getDocument(id: string): Observable<DocumentDetail> {
    return this.http.get<DocumentDetail>(`${environment.apiUrl}/documents/${id}`);
  }

  uploadDocument(file: File): Observable<HttpEvent<DocumentSummary>> {
    const formData = new FormData();
    formData.append('file', file, file.name);

    const req = new HttpRequest('POST', `${environment.apiUrl}/documents`, formData, {
      reportProgress: true
    });

    return this.http.request<DocumentSummary>(req);
  }

  deleteDocument(id: string): Observable<void> {
    return this.http.delete<void>(`${environment.apiUrl}/documents/${id}`).pipe(
      tap(() => {
        this.documents.update(docs => docs.filter(d => d.id !== id));
      })
    );
  }

  retryProcessing(id: string): Observable<{ message: string }> {
    return this.http.post<{ message: string }>(`${environment.apiUrl}/documents/${id}/retry`, {}).pipe(
      tap(() => {
        this.documents.update(docs => docs.map(d => d.id === id ? { ...d, status: 'Pending', errorMessage: null } : d));
      })
    );
  }

  downloadDocument(id: string): Observable<Blob> {
    return this.http.get(`${environment.apiUrl}/documents/${id}/file`, {
      responseType: 'blob'
    });
  }
}
