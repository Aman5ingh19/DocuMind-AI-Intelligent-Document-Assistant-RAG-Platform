using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace DocumentAssistant.Api.Entities;

/// <summary>
/// Represents an uploaded PDF document and its processing state.
/// The actual file content is stored on disk (or cloud storage).
/// Only metadata is stored in MySQL.
/// </summary>
public class Document
{
    [Key]
    public Guid Id { get; set; } = Guid.NewGuid();

    /// <summary>Owner of this document.</summary>
    [Required]
    public string UserId { get; set; } = string.Empty;

    [ForeignKey(nameof(UserId))]
    public ApplicationUser? User { get; set; }

    /// <summary>Original filename as provided by the user (display only).</summary>
    [Required]
    [MaxLength(260)]
    public string FileName { get; set; } = string.Empty;

    /// <summary>Sanitised GUID-based filename used in storage (no path traversal risk).</summary>
    [Required]
    [MaxLength(260)]
    public string StoredFileName { get; set; } = string.Empty;

    /// <summary>Relative storage path. Combined with the configured base path at runtime.</summary>
    [Required]
    [MaxLength(512)]
    public string StoragePath { get; set; } = string.Empty;

    [Required]
    [MaxLength(100)]
    public string ContentType { get; set; } = "application/pdf";

    public long FileSizeBytes { get; set; }

    /// <summary>SHA-256 hash of the file for integrity verification and deduplication.</summary>
    [MaxLength(64)]
    public string? FileHashSha256 { get; set; }

    /// <summary>Number of pages (populated after processing).</summary>
    public int TotalPages { get; set; }

    /// <summary>Current processing status.</summary>
    [Required]
    [MaxLength(50)]
    public DocumentStatus Status { get; set; } = DocumentStatus.Pending;

    /// <summary>Human-readable error description when Status is Failed.</summary>
    [MaxLength(2000)]
    public string? ErrorMessage { get; set; }

    public DateTime UploadedAtUtc { get; set; } = DateTime.UtcNow;
    public DateTime? ProcessedAtUtc { get; set; }

    // Navigation properties
    public ICollection<DocumentProcessingJob> ProcessingJobs { get; set; } = [];
}

public enum DocumentStatus
{
    Pending,
    Processing,
    Completed,
    Failed
}
