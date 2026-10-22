using DocumentAssistant.Api.Data;
using DocumentAssistant.Api.Entities;
using DocumentAssistant.Api.Models;
using DocumentAssistant.Api.Services.Background;
using Microsoft.EntityFrameworkCore;

namespace DocumentAssistant.Api.Services;

public interface IDocumentService
{
    Task<DocumentSummaryDto> UploadAsync(IFormFile file, string userId, CancellationToken ct = default);
    Task<List<DocumentSummaryDto>> GetUserDocumentsAsync(string userId, CancellationToken ct = default);
    Task<DocumentDetailDto?> GetDocumentByIdAsync(Guid documentId, string userId, CancellationToken ct = default);
    Task<(Stream Stream, string ContentType, string FileName)?> GetFileStreamAsync(Guid documentId, string userId, CancellationToken ct = default);
    Task<bool> DeleteAsync(Guid documentId, string userId, CancellationToken ct = default);
    Task<bool> RetryProcessingAsync(Guid documentId, string userId, CancellationToken ct = default);
}

public class DocumentService : IDocumentService
{
    private readonly AppDbContext _dbContext;
    private readonly IDocumentStorageService _storageService;
    private readonly IDocumentProcessingQueue _queue;
    private readonly IAiServiceClient _aiClient;
    private readonly ILogger<DocumentService> _logger;

    private const long MaxFileSizeBytes = 30 * 1024 * 1024; // 30 MB max

    public DocumentService(
        AppDbContext dbContext,
        IDocumentStorageService storageService,
        IDocumentProcessingQueue queue,
        IAiServiceClient aiClient,
        ILogger<DocumentService> logger)
    {
        _dbContext = dbContext;
        _storageService = storageService;
        _queue = queue;
        _aiClient = aiClient;
        _logger = logger;
    }

    public async Task<DocumentSummaryDto> UploadAsync(IFormFile file, string userId, CancellationToken ct = default)
    {
        if (file == null || file.Length == 0)
        {
            throw new ArgumentException("Uploaded file is empty.");
        }

        if (file.Length > MaxFileSizeBytes)
        {
            throw new ArgumentException($"File size exceeds the maximum limit of {MaxFileSizeBytes / (1024 * 1024)} MB.");
        }

        var extension = Path.GetExtension(file.FileName).ToLowerInvariant();
        if (extension != ".pdf")
        {
            throw new ArgumentException("Only PDF files (.pdf) are supported.");
        }

        using var fileStream = file.OpenReadStream();

        // Validate magic bytes
        var isPdf = await _storageService.IsPdfAsync(fileStream, ct);
        if (!isPdf)
        {
            throw new ArgumentException("The uploaded file does not have a valid PDF header.");
        }

        // Compute hash
        var hash = await _storageService.ComputeHashAsync(fileStream, ct);

        // Save to storage
        var (storedFileName, storagePath) = await _storageService.SaveAsync(fileStream, file.FileName, ct);

        var document = new Document
        {
            Id = Guid.NewGuid(),
            UserId = userId,
            FileName = Path.GetFileName(file.FileName),
            StoredFileName = storedFileName,
            StoragePath = storagePath,
            ContentType = "application/pdf",
            FileSizeBytes = file.Length,
            FileHashSha256 = hash,
            TotalPages = 0,
            Status = DocumentStatus.Pending,
            UploadedAtUtc = DateTime.UtcNow
        };

        _dbContext.Documents.Add(document);
        await _dbContext.SaveChangesAsync(ct);

        // Queue for background extraction, chunking, and embedding
        await _queue.QueueBackgroundWorkItemAsync(document.Id, ct);
        _logger.LogInformation("Document {DocumentId} ({FileName}) uploaded and queued for processing.", document.Id, document.FileName);

        return new DocumentSummaryDto(
            document.Id,
            document.FileName,
            document.FileSizeBytes,
            document.Status.ToString(),
            document.TotalPages,
            document.UploadedAtUtc,
            document.ErrorMessage
        );
    }

    public async Task<List<DocumentSummaryDto>> GetUserDocumentsAsync(string userId, CancellationToken ct = default)
    {
        return await _dbContext.Documents
            .AsNoTracking()
            .Where(d => d.UserId == userId)
            .OrderByDescending(d => d.UploadedAtUtc)
            .Select(d => new DocumentSummaryDto(
                d.Id,
                d.FileName,
                d.FileSizeBytes,
                d.Status.ToString(),
                d.TotalPages,
                d.UploadedAtUtc,
                d.ErrorMessage
            ))
            .ToListAsync(ct);
    }

    public async Task<DocumentDetailDto?> GetDocumentByIdAsync(Guid documentId, string userId, CancellationToken ct = default)
    {
        var d = await _dbContext.Documents
            .AsNoTracking()
            .FirstOrDefaultAsync(doc => doc.Id == documentId && doc.UserId == userId, ct);

        if (d == null) return null;

        return new DocumentDetailDto(
            d.Id,
            d.FileName,
            d.ContentType,
            d.FileSizeBytes,
            d.FileHashSha256 ?? string.Empty,
            d.Status.ToString(),
            d.TotalPages,
            d.UploadedAtUtc,
            d.ProcessedAtUtc,
            d.ErrorMessage
        );
    }

    public async Task<(Stream Stream, string ContentType, string FileName)?> GetFileStreamAsync(
        Guid documentId, string userId, CancellationToken ct = default)
    {
        var doc = await _dbContext.Documents
            .AsNoTracking()
            .FirstOrDefaultAsync(d => d.Id == documentId && d.UserId == userId, ct);

        if (doc == null) return null;

        var stream = await _storageService.GetStreamAsync(doc.StoragePath, ct);
        return (stream, doc.ContentType, doc.FileName);
    }

    public async Task<bool> DeleteAsync(Guid documentId, string userId, CancellationToken ct = default)
    {
        var doc = await _dbContext.Documents
            .FirstOrDefaultAsync(d => d.Id == documentId && d.UserId == userId, ct);

        if (doc == null) return false;

        // Delete physical file
        try
        {
            await _storageService.DeleteAsync(doc.StoragePath, ct);
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Failed to delete file from storage: {Path}", doc.StoragePath);
        }

        // Delete vectors from vector store
        try
        {
            await _aiClient.DeleteDocumentVectorsAsync(doc.Id.ToString(), ct);
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Failed to delete vectors from vector store for document: {Id}", doc.Id);
        }

        _dbContext.Documents.Remove(doc);
        await _dbContext.SaveChangesAsync(ct);
        return true;
    }

    public async Task<bool> RetryProcessingAsync(Guid documentId, string userId, CancellationToken ct = default)
    {
        var doc = await _dbContext.Documents
            .FirstOrDefaultAsync(d => d.Id == documentId && d.UserId == userId, ct);

        if (doc == null) return false;

        doc.Status = DocumentStatus.Pending;
        doc.ErrorMessage = null;
        await _dbContext.SaveChangesAsync(ct);

        await _queue.QueueBackgroundWorkItemAsync(doc.Id, ct);
        return true;
    }
}
