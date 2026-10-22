using DocumentAssistant.Api.Data;
using DocumentAssistant.Api.Entities;
using Microsoft.EntityFrameworkCore;

namespace DocumentAssistant.Api.Services.Background;

public class DocumentProcessingWorker : BackgroundService
{
    private readonly IDocumentProcessingQueue _queue;
    private readonly IServiceProvider _serviceProvider;
    private readonly ILogger<DocumentProcessingWorker> _logger;

    public DocumentProcessingWorker(
        IDocumentProcessingQueue queue,
        IServiceProvider serviceProvider,
        ILogger<DocumentProcessingWorker> logger)
    {
        _queue = queue;
        _serviceProvider = serviceProvider;
        _logger = logger;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        _logger.LogInformation("DocumentProcessingWorker hosted service started.");

        while (!stoppingToken.IsCancellationRequested)
        {
            try
            {
                var documentId = await _queue.DequeueAsync(stoppingToken);
                await ProcessDocumentAsync(documentId, stoppingToken);
            }
            catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested)
            {
                break;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Unexpected error in DocumentProcessingWorker loop.");
            }
        }

        _logger.LogInformation("DocumentProcessingWorker hosted service stopped.");
    }

    private async Task ProcessDocumentAsync(Guid documentId, CancellationToken ct)
    {
        using var scope = _serviceProvider.CreateScope();
        var dbContext = scope.ServiceProvider.GetRequiredService<AppDbContext>();
        var storage = scope.ServiceProvider.GetRequiredService<IDocumentStorageService>();
        var aiClient = scope.ServiceProvider.GetRequiredService<IAiServiceClient>();

        var document = await dbContext.Documents
            .Include(d => d.ProcessingJobs)
            .FirstOrDefaultAsync(d => d.Id == documentId, ct);

        if (document == null)
        {
            _logger.LogWarning("Document {DocumentId} queued for processing was not found in database.", documentId);
            return;
        }

        // Create or get job
        var attemptCount = document.ProcessingJobs.Count + 1;
        var job = new DocumentProcessingJob
        {
            DocumentId = document.Id,
            AttemptCount = attemptCount,
            CurrentStep = "Extracting & Indexing",
            StartedAtUtc = DateTime.UtcNow
        };
        dbContext.DocumentProcessingJobs.Add(job);

        document.Status = DocumentStatus.Processing;
        document.ErrorMessage = null;
        await dbContext.SaveChangesAsync(ct);

        try
        {
            var absolutePath = storage.GetAbsolutePath(document.StoragePath);
            _logger.LogInformation("Invoking AI service for document {DocumentId} at path: {Path}", documentId, absolutePath);

            var aiResult = await aiClient.ProcessDocumentAsync(document.Id.ToString(), absolutePath, ct);

            document.Status = DocumentStatus.Completed;
            document.TotalPages = aiResult.TotalPages;
            document.ProcessedAtUtc = DateTime.UtcNow;
            document.ErrorMessage = null;

            job.CurrentStep = "Completed";
            job.FinishedAtUtc = DateTime.UtcNow;

            await dbContext.SaveChangesAsync(ct);
            _logger.LogInformation("Document {DocumentId} processing completed successfully. Pages: {Pages}, Chunks: {Chunks}",
                document.Id, aiResult.TotalPages, aiResult.ChunkCount);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Document {DocumentId} processing failed.", documentId);

            document.Status = DocumentStatus.Failed;
            document.ErrorMessage = ex.Message.Length > 1950 ? ex.Message[..1950] : ex.Message;

            job.CurrentStep = "Failed";
            job.FailureReason = ex.Message.Length > 1950 ? ex.Message[..1950] : ex.Message;
            job.FinishedAtUtc = DateTime.UtcNow;

            await dbContext.SaveChangesAsync(ct);
        }
    }
}
