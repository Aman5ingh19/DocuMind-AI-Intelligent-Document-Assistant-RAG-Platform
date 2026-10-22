using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace DocumentAssistant.Api.Entities;

/// <summary>
/// Tracks individual document processing pipeline runs.
/// A document can have multiple jobs if processing fails and is retried.
/// </summary>
public class DocumentProcessingJob
{
    [Key]
    public Guid Id { get; set; } = Guid.NewGuid();

    [Required]
    public Guid DocumentId { get; set; }

    [ForeignKey(nameof(DocumentId))]
    public Document? Document { get; set; }

    public int AttemptCount { get; set; } = 1;

    [MaxLength(100)]
    public string CurrentStep { get; set; } = "Started";

    [MaxLength(2000)]
    public string? FailureReason { get; set; }

    public DateTime StartedAtUtc { get; set; } = DateTime.UtcNow;
    public DateTime? FinishedAtUtc { get; set; }
}
