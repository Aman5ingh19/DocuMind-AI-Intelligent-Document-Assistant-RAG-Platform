using DocumentAssistant.Api.Models;
using DocumentAssistant.Api.Services;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using System.Security.Claims;

namespace DocumentAssistant.Api.Controllers;

[ApiController]
[Route("api/[controller]")]
[Authorize]
public class ChatController : ControllerBase
{
    private readonly IChatService _chatService;
    private readonly ILogger<ChatController> _logger;

    public ChatController(IChatService chatService, ILogger<ChatController> logger)
    {
        _chatService = chatService;
        _logger = logger;
    }

    private string GetCurrentUserId()
    {
        var userId = User.FindFirstValue(ClaimTypes.NameIdentifier);
        if (string.IsNullOrEmpty(userId))
        {
            throw new UnauthorizedAccessException("User identifier not present in claims token.");
        }
        return userId;
    }

    [HttpPost("sessions")]
    [ProducesResponseType(typeof(ChatSessionDto), StatusCodes.Status201Created)]
    public async Task<IActionResult> CreateSession([FromBody] CreateChatSessionRequest? request, CancellationToken ct)
    {
        var userId = GetCurrentUserId();
        var session = await _chatService.CreateSessionAsync(userId, request?.Title, ct);
        return CreatedAtAction(nameof(GetSessionMessages), new { id = session.Id }, session);
    }

    [HttpGet("sessions")]
    [ProducesResponseType(typeof(List<ChatSessionDto>), StatusCodes.Status200OK)]
    public async Task<IActionResult> GetSessions(CancellationToken ct)
    {
        var userId = GetCurrentUserId();
        var sessions = await _chatService.GetSessionsAsync(userId, ct);
        return Ok(sessions);
    }

    [HttpGet("sessions/{id:guid}/messages")]
    [ProducesResponseType(typeof(List<ChatMessageDto>), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<IActionResult> GetSessionMessages(Guid id, CancellationToken ct)
    {
        var userId = GetCurrentUserId();
        var messages = await _chatService.GetSessionMessagesAsync(id, userId, ct);
        if (messages == null)
        {
            return NotFound(new ApiErrorResponse("Chat session not found."));
        }
        return Ok(messages);
    }

    [HttpDelete("sessions/{id:guid}")]
    [ProducesResponseType(StatusCodes.Status204NoContent)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<IActionResult> DeleteSession(Guid id, CancellationToken ct)
    {
        var userId = GetCurrentUserId();
        var deleted = await _chatService.DeleteSessionAsync(id, userId, ct);
        if (!deleted)
        {
            return NotFound(new ApiErrorResponse("Chat session not found."));
        }
        return NoContent();
    }

    [HttpPost("sessions/{id:guid}/messages")]
    [ProducesResponseType(typeof(ChatMessageDto), StatusCodes.Status200OK)]
    [ProducesResponseType(typeof(ApiErrorResponse), StatusCodes.Status400BadRequest)]
    [ProducesResponseType(typeof(ApiErrorResponse), StatusCodes.Status404NotFound)]
    public async Task<IActionResult> SendMessage(Guid id, [FromBody] SendMessageRequest request, CancellationToken ct)
    {
        try
        {
            var userId = GetCurrentUserId();
            var message = await _chatService.SendMessageAsync(id, userId, request, ct);
            return Ok(message);
        }
        catch (KeyNotFoundException ex)
        {
            return NotFound(new ApiErrorResponse(ex.Message));
        }
        catch (ArgumentException ex)
        {
            return BadRequest(new ApiErrorResponse(ex.Message));
        }
        catch (UnauthorizedAccessException ex)
        {
            return StatusCode(StatusCodes.Status403Forbidden, new ApiErrorResponse(ex.Message));
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error processing chat question in session {SessionId}", id);
            return StatusCode(StatusCodes.Status500InternalServerError,
                new ApiErrorResponse("Failed to process question via AI assistant.", ex.Message));
        }
    }
}
