using DocumentAssistant.Api.Models;
using DocumentAssistant.Api.Services;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.RateLimiting;
using System.Security.Claims;

namespace DocumentAssistant.Api.Controllers;

[ApiController]
[Route("api/[controller]")]
[Authorize]
public class DocumentsController : ControllerBase
{
    private readonly IDocumentService _documentService;
    private readonly ILogger<DocumentsController> _logger;

    public DocumentsController(IDocumentService documentService, ILogger<DocumentsController> logger)
    {
        _documentService = documentService;
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

    [HttpPost]
    [EnableRateLimiting("upload")]
    [Consumes("multipart/form-data")]
    [ProducesResponseType(typeof(DocumentSummaryDto), StatusCodes.Status201Created)]
    [ProducesResponseType(typeof(ApiErrorResponse), StatusCodes.Status400BadRequest)]
    public async Task<IActionResult> UploadDocument([FromForm] IFormFile file, CancellationToken ct)
    {
        try
        {
            var userId = GetCurrentUserId();
            var result = await _documentService.UploadAsync(file, userId, ct);
            return CreatedAtAction(nameof(GetDocumentById), new { id = result.Id }, result);
        }
        catch (ArgumentException ex)
        {
            return BadRequest(new ApiErrorResponse(ex.Message));
        }
    }

    [HttpGet]
    [ProducesResponseType(typeof(List<DocumentSummaryDto>), StatusCodes.Status200OK)]
    public async Task<IActionResult> GetDocuments(CancellationToken ct)
    {
        var userId = GetCurrentUserId();
        var documents = await _documentService.GetUserDocumentsAsync(userId, ct);
        return Ok(documents);
    }

    [HttpGet("{id:guid}")]
    [ProducesResponseType(typeof(DocumentDetailDto), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<IActionResult> GetDocumentById(Guid id, CancellationToken ct)
    {
        var userId = GetCurrentUserId();
        var document = await _documentService.GetDocumentByIdAsync(id, userId, ct);
        if (document == null)
        {
            return NotFound(new ApiErrorResponse("Document not found."));
        }
        return Ok(document);
    }

    [HttpGet("{id:guid}/file")]
    [ProducesResponseType(StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<IActionResult> GetDocumentFile(Guid id, CancellationToken ct)
    {
        var userId = GetCurrentUserId();
        var fileResult = await _documentService.GetFileStreamAsync(id, userId, ct);
        if (fileResult == null)
        {
            return NotFound(new ApiErrorResponse("Document file not found."));
        }

        return File(fileResult.Value.Stream, fileResult.Value.ContentType, fileResult.Value.FileName);
    }

    [HttpDelete("{id:guid}")]
    [ProducesResponseType(StatusCodes.Status204NoContent)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<IActionResult> DeleteDocument(Guid id, CancellationToken ct)
    {
        var userId = GetCurrentUserId();
        var deleted = await _documentService.DeleteAsync(id, userId, ct);
        if (!deleted)
        {
            return NotFound(new ApiErrorResponse("Document not found."));
        }
        return NoContent();
    }

    [HttpPost("{id:guid}/retry")]
    [ProducesResponseType(StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<IActionResult> RetryProcessing(Guid id, CancellationToken ct)
    {
        var userId = GetCurrentUserId();
        var retried = await _documentService.RetryProcessingAsync(id, userId, ct);
        if (!retried)
        {
            return NotFound(new ApiErrorResponse("Document not found or cannot be retried."));
        }
        return Ok(new { message = "Document re-queued for processing." });
    }
}
