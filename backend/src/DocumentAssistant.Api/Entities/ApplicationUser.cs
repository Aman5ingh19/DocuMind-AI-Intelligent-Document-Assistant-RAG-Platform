using Microsoft.AspNetCore.Identity;
using System.ComponentModel.DataAnnotations;

namespace DocumentAssistant.Api.Entities;

/// <summary>
/// Extended Identity user with application-specific fields.
/// ASP.NET Core Identity stores password hashes, roles, claims, etc.
/// We only add our custom fields here.
/// </summary>
public class ApplicationUser : IdentityUser
{
    /// <summary>When the account was created (UTC).</summary>
    public DateTime CreatedAtUtc { get; set; } = DateTime.UtcNow;

    // Navigation properties
    public ICollection<Document> Documents { get; set; } = [];
    public ICollection<ChatSession> ChatSessions { get; set; } = [];
}
