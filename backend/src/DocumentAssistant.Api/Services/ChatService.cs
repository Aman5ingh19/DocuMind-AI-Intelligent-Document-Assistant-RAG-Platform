using DocumentAssistant.Api.Data;
using DocumentAssistant.Api.Entities;
using DocumentAssistant.Api.Models;
using Microsoft.EntityFrameworkCore;
using System.Text.Json;

namespace DocumentAssistant.Api.Services;

public interface IChatService
{
    Task<ChatSessionDto> CreateSessionAsync(string userId, string? title = null, CancellationToken ct = default);
    Task<List<ChatSessionDto>> GetSessionsAsync(string userId, CancellationToken ct = default);
    Task<List<ChatMessageDto>?> GetSessionMessagesAsync(Guid sessionId, string userId, CancellationToken ct = default);
    Task<bool> DeleteSessionAsync(Guid sessionId, string userId, CancellationToken ct = default);
    Task<ChatMessageDto> SendMessageAsync(Guid sessionId, string userId, SendMessageRequest request, CancellationToken ct = default);
}

public class ChatService : IChatService
{
    private readonly AppDbContext _dbContext;
    private readonly IAiServiceClient _aiClient;
    private readonly ILogger<ChatService> _logger;
    private static readonly JsonSerializerOptions JsonOptions = new() { PropertyNamingPolicy = JsonNamingPolicy.CamelCase };

    public ChatService(
        AppDbContext dbContext,
        IAiServiceClient aiClient,
        ILogger<ChatService> logger)
    {
        _dbContext = dbContext;
        _aiClient = aiClient;
        _logger = logger;
    }

    public async Task<ChatSessionDto> CreateSessionAsync(string userId, string? title = null, CancellationToken ct = default)
    {
        var session = new ChatSession
        {
            Id = Guid.NewGuid(),
            UserId = userId,
            Title = string.IsNullOrWhiteSpace(title) ? "New Chat" : title.Trim(),
            CreatedAtUtc = DateTime.UtcNow,
            UpdatedAtUtc = DateTime.UtcNow
        };

        _dbContext.ChatSessions.Add(session);
        await _dbContext.SaveChangesAsync(ct);

        return new ChatSessionDto(session.Id, session.Title, session.CreatedAtUtc, session.UpdatedAtUtc);
    }

    public async Task<List<ChatSessionDto>> GetSessionsAsync(string userId, CancellationToken ct = default)
    {
        return await _dbContext.ChatSessions
            .AsNoTracking()
            .Where(s => s.UserId == userId)
            .OrderByDescending(s => s.UpdatedAtUtc)
            .Select(s => new ChatSessionDto(s.Id, s.Title, s.CreatedAtUtc, s.UpdatedAtUtc))
            .ToListAsync(ct);
    }

    public async Task<List<ChatMessageDto>?> GetSessionMessagesAsync(Guid sessionId, string userId, CancellationToken ct = default)
    {
        var session = await _dbContext.ChatSessions
            .AsNoTracking()
            .FirstOrDefaultAsync(s => s.Id == sessionId && s.UserId == userId, ct);

        if (session == null) return null;

        var messages = await _dbContext.ChatMessages
            .AsNoTracking()
            .Where(m => m.ChatSessionId == sessionId)
            .OrderBy(m => m.CreatedAtUtc)
            .ToListAsync(ct);

        return messages.Select(m =>
        {
            List<CitationDto>? citations = null;
            if (!string.IsNullOrEmpty(m.CitationsJson))
            {
                try
                {
                    citations = JsonSerializer.Deserialize<List<CitationDto>>(m.CitationsJson, JsonOptions);
                }
                catch
                {
                    // ignore invalid JSON
                }
            }

            return new ChatMessageDto(
                m.Id,
                m.ChatSessionId,
                m.Role,
                m.Content,
                citations,
                m.CreatedAtUtc
            );
        }).ToList();
    }

    public async Task<bool> DeleteSessionAsync(Guid sessionId, string userId, CancellationToken ct = default)
    {
        var session = await _dbContext.ChatSessions
            .Include(s => s.Messages)
            .FirstOrDefaultAsync(s => s.Id == sessionId && s.UserId == userId, ct);

        if (session == null) return false;

        _dbContext.ChatSessions.Remove(session);
        await _dbContext.SaveChangesAsync(ct);
        return true;
    }

    public async Task<ChatMessageDto> SendMessageAsync(
        Guid sessionId,
        string userId,
        SendMessageRequest request,
        CancellationToken ct = default)
    {
        if (string.IsNullOrWhiteSpace(request.Question))
        {
            throw new ArgumentException("Question cannot be empty.");
        }

        if (request.DocumentIds == null || request.DocumentIds.Count == 0)
        {
            throw new ArgumentException("At least one document must be selected.");
        }

        var session = await _dbContext.ChatSessions
            .Include(s => s.Messages)
            .FirstOrDefaultAsync(s => s.Id == sessionId && s.UserId == userId, ct);

        if (session == null)
        {
            throw new KeyNotFoundException("Chat session not found or you do not have permission.");
        }

        // Validate user ownership of all selected documents
        var ownedDocs = await _dbContext.Documents
            .AsNoTracking()
            .Where(d => d.UserId == userId && request.DocumentIds.Contains(d.Id))
            .ToDictionaryAsync(d => d.Id.ToString(), d => d.FileName, ct);

        if (ownedDocs.Count != request.DocumentIds.Count)
        {
            throw new UnauthorizedAccessException("One or more selected documents do not belong to the current user or do not exist.");
        }

        // Auto-generate title if currently default
        if (session.Title == "New Chat")
        {
            var cleanQuestion = request.Question.Trim();
            session.Title = cleanQuestion.Length > 50 ? cleanQuestion[..47] + "..." : cleanQuestion;
        }

        // Save user message
        var userMessage = new ChatMessage
        {
            Id = Guid.NewGuid(),
            ChatSessionId = session.Id,
            Role = "User",
            Content = request.Question.Trim(),
            CreatedAtUtc = DateTime.UtcNow
        };
        _dbContext.ChatMessages.Add(userMessage);

        // Prepare conversation history (last 6 messages before this one)
        var historyMessages = session.Messages
            .OrderBy(m => m.CreatedAtUtc)
            .TakeLast(6)
            .Select(m => new AiConversationMessage(m.Role, m.Content))
            .ToList();

        // Call AI Service
        var aiRequest = new AiQueryRequest(
            request.Question.Trim(),
            request.DocumentIds.Select(id => id.ToString()).ToList(),
            historyMessages
        );

        var aiResponse = await _aiClient.QueryAsync(aiRequest, ct);

        // Map citations and enrich with filename
        var citations = aiResponse.Citations.Select(c =>
        {
            ownedDocs.TryGetValue(c.DocumentId, out var fileName);
            return new CitationDto(
                c.DocumentId,
                fileName,
                c.PageNumber,
                c.Snippet,
                c.RelevanceScore
            );
        }).ToList();

        var citationsJson = JsonSerializer.Serialize(citations, JsonOptions);

        // Save Assistant message
        var assistantMessage = new ChatMessage
        {
            Id = Guid.NewGuid(),
            ChatSessionId = session.Id,
            Role = "Assistant",
            Content = aiResponse.Answer,
            CitationsJson = citationsJson,
            CreatedAtUtc = DateTime.UtcNow
        };
        _dbContext.ChatMessages.Add(assistantMessage);

        session.UpdatedAtUtc = DateTime.UtcNow;
        await _dbContext.SaveChangesAsync(ct);

        return new ChatMessageDto(
            assistantMessage.Id,
            assistantMessage.ChatSessionId,
            assistantMessage.Role,
            assistantMessage.Content,
            citations,
            assistantMessage.CreatedAtUtc
        );
    }
}
