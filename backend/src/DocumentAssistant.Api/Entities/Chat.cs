using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace DocumentAssistant.Api.Entities;

/// <summary>
/// A conversation session between a user and the AI assistant.
/// Each session has a set of messages and is tied to one or more documents.
/// </summary>
public class ChatSession
{
    [Key]
    public Guid Id { get; set; } = Guid.NewGuid();

    [Required]
    public string UserId { get; set; } = string.Empty;

    [ForeignKey(nameof(UserId))]
    public ApplicationUser? User { get; set; }

    /// <summary>Auto-generated from the first user question (truncated to 100 chars).</summary>
    [MaxLength(200)]
    public string Title { get; set; } = "New Chat";

    public DateTime CreatedAtUtc { get; set; } = DateTime.UtcNow;
    public DateTime UpdatedAtUtc { get; set; } = DateTime.UtcNow;

    public ICollection<ChatMessage> Messages { get; set; } = [];
}

/// <summary>
/// A single message within a ChatSession.
/// Stores both user questions and AI assistant answers, along with structured citations.
/// </summary>
public class ChatMessage
{
    [Key]
    public Guid Id { get; set; } = Guid.NewGuid();

    [Required]
    public Guid ChatSessionId { get; set; }

    [ForeignKey(nameof(ChatSessionId))]
    public ChatSession? ChatSession { get; set; }

    /// <summary>"User" or "Assistant"</summary>
    [Required]
    [MaxLength(20)]
    public string Role { get; set; } = string.Empty;

    /// <summary>The question text or AI answer text.</summary>
    [Required]
    public string Content { get; set; } = string.Empty;

    /// <summary>
    /// JSON array of citation objects returned by the AI service.
    /// Stored as a JSON column to avoid a complex normalised schema for variable-length citations.
    /// Format: [{ documentId, pageNumber, snippet, relevanceScore }]
    /// </summary>
    public string? CitationsJson { get; set; }

    public DateTime CreatedAtUtc { get; set; } = DateTime.UtcNow;
}
