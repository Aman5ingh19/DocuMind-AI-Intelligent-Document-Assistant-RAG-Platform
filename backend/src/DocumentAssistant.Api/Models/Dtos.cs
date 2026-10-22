namespace DocumentAssistant.Api.Models;

// ─────────────────────────────────────────────────────────────────────────────
// Auth DTOs
// ─────────────────────────────────────────────────────────────────────────────

public record RegisterRequest(
    string Email,
    string Password,
    string ConfirmPassword
);

public record LoginRequest(
    string Email,
    string Password
);

public record AuthResponse(
    string Token,
    DateTime ExpiresAt,
    UserDto User
);

public record UserDto(
    string Id,
    string Email,
    DateTime CreatedAtUtc
);

// ─────────────────────────────────────────────────────────────────────────────
// Document DTOs
// ─────────────────────────────────────────────────────────────────────────────

public record DocumentSummaryDto(
    Guid Id,
    string FileName,
    long FileSizeBytes,
    string Status,
    int TotalPages,
    DateTime UploadedAtUtc,
    string? ErrorMessage
);

public record DocumentDetailDto(
    Guid Id,
    string FileName,
    string ContentType,
    long FileSizeBytes,
    string FileHashSha256,
    string Status,
    int TotalPages,
    DateTime UploadedAtUtc,
    DateTime? ProcessedAtUtc,
    string? ErrorMessage
);

public record DocumentStatusDto(
    Guid Id,
    string Status,
    int TotalPages,
    string? ErrorMessage
);

// ─────────────────────────────────────────────────────────────────────────────
// Chat DTOs
// ─────────────────────────────────────────────────────────────────────────────

public record CreateChatSessionRequest(
    string? Title = null
);

public record ChatSessionDto(
    Guid Id,
    string Title,
    DateTime CreatedAtUtc,
    DateTime UpdatedAtUtc
);

public record SendMessageRequest(
    string Question,
    List<Guid> DocumentIds
);

public record ChatMessageDto(
    Guid Id,
    Guid ChatSessionId,
    string Role,
    string Content,
    List<CitationDto>? Citations,
    DateTime CreatedAtUtc
);

public record CitationDto(
    string DocumentId,
    string? DocumentName,
    int PageNumber,
    string Snippet,
    double RelevanceScore
);

// ─────────────────────────────────────────────────────────────────────────────
// AI Service API contracts (internal – not exposed to Angular directly)
// ─────────────────────────────────────────────────────────────────────────────

public record AiProcessDocumentRequest(
    string DocumentId,
    string FilePath
);

public record AiProcessDocumentResponse(
    string DocumentId,
    int TotalPages,
    int ChunkCount,
    string Status
);

public record AiQueryRequest(
    string Question,
    List<string> DocumentIds,
    List<AiConversationMessage>? ConversationHistory = null
);

public record AiConversationMessage(
    string Role,
    string Content
);

public record AiQueryResponse(
    string Answer,
    List<AiCitation> Citations,
    string ModelUsed
);

public record AiCitation(
    string DocumentId,
    int PageNumber,
    string Snippet,
    double RelevanceScore
);

// ─────────────────────────────────────────────────────────────────────────────
// Error response
// ─────────────────────────────────────────────────────────────────────────────

public record ApiErrorResponse(
    string Error,
    string? Detail = null
);
