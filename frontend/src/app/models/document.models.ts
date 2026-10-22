export type DocumentStatus = 'Pending' | 'Processing' | 'Completed' | 'Failed';

export interface DocumentSummary {
  id: string;
  fileName: string;
  fileSizeBytes: number;
  status: DocumentStatus;
  totalPages: number;
  uploadedAtUtc: string;
  errorMessage?: string | null;
}

export interface DocumentDetail {
  id: string;
  fileName: string;
  contentType: string;
  fileSizeBytes: number;
  fileHashSha256: string;
  status: DocumentStatus;
  totalPages: number;
  uploadedAtUtc: string;
  processedAtUtc?: string | null;
  errorMessage?: string | null;
}
