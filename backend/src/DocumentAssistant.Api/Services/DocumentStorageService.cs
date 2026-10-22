using System.Security.Cryptography;

namespace DocumentAssistant.Api.Services;

/// <summary>Abstract storage interface (supports local disk and cloud providers).</summary>
public interface IDocumentStorageService
{
    /// <summary>Save an uploaded file securely and return its storage path.</summary>
    Task<(string StoredFileName, string StoragePath)> SaveAsync(
        Stream fileStream, string originalFileName, CancellationToken ct = default);

    /// <summary>Open a stream to read a stored file.</summary>
    Task<Stream> GetStreamAsync(string storagePath, CancellationToken ct = default);

    /// <summary>Get the absolute filesystem path for a stored file (used by AI service).</summary>
    string GetAbsolutePath(string storagePath);

    /// <summary>Delete a stored file. Does not throw if the file does not exist.</summary>
    Task DeleteAsync(string storagePath, CancellationToken ct = default);

    /// <summary>Validate that the stream starts with the PDF magic bytes.</summary>
    Task<bool> IsPdfAsync(Stream stream, CancellationToken ct = default);

    /// <summary>Compute SHA-256 hash of a stream (resets position after reading).</summary>
    Task<string> ComputeHashAsync(Stream stream, CancellationToken ct = default);
}

/// <summary>
/// Local filesystem storage implementation.
///
/// Security measures:
/// - Stored filename is a GUID + .pdf → no user-controlled path components.
/// - The absolute path is constructed from a trusted base path setting.
/// - PDF magic bytes are checked BEFORE accepting the file (not just the extension).
/// - Files are never executed; they are only read as binary blobs by the AI service.
/// </summary>
public class LocalDocumentStorageService : IDocumentStorageService
{
    private readonly string _basePath;
    private readonly ILogger<LocalDocumentStorageService> _logger;
    private static readonly byte[] PdfMagicBytes = "%PDF-"u8.ToArray();

    public LocalDocumentStorageService(IConfiguration configuration, ILogger<LocalDocumentStorageService> logger)
    {
        _basePath = configuration["Storage:LocalPath"]
            ?? Path.Combine(Directory.GetCurrentDirectory(), "data", "documents");
        Directory.CreateDirectory(_basePath);
        _logger = logger;
    }

    public async Task<(string StoredFileName, string StoragePath)> SaveAsync(
        Stream fileStream, string originalFileName, CancellationToken ct = default)
    {
        var storedFileName = $"{Guid.NewGuid()}.pdf";
        var storagePath = Path.Combine("documents", storedFileName);
        var absolutePath = GetAbsolutePath(storagePath);

        // Ensure the target directory exists
        Directory.CreateDirectory(Path.GetDirectoryName(absolutePath)!);

        using var fileOutput = new FileStream(absolutePath, FileMode.CreateNew, FileAccess.Write, FileShare.None);
        fileStream.Position = 0;
        await fileStream.CopyToAsync(fileOutput, ct);

        _logger.LogInformation("File saved: {Path} (original: {OriginalName})", absolutePath, originalFileName);
        return (storedFileName, storagePath);
    }

    public Task<Stream> GetStreamAsync(string storagePath, CancellationToken ct = default)
    {
        var absolutePath = GetAbsolutePath(storagePath);
        if (!File.Exists(absolutePath))
            throw new FileNotFoundException($"Document file not found at storage path: {storagePath}");

        Stream stream = new FileStream(absolutePath, FileMode.Open, FileAccess.Read, FileShare.Read);
        return Task.FromResult(stream);
    }

    public string GetAbsolutePath(string storagePath)
    {
        // Combine with base path and resolve to prevent path traversal
        var combined = Path.GetFullPath(Path.Combine(_basePath, storagePath));
        if (!combined.StartsWith(Path.GetFullPath(_basePath), StringComparison.OrdinalIgnoreCase))
            throw new UnauthorizedAccessException("Path traversal detected in storage path.");
        return combined;
    }

    public async Task DeleteAsync(string storagePath, CancellationToken ct = default)
    {
        try
        {
            var absolutePath = GetAbsolutePath(storagePath);
            if (File.Exists(absolutePath))
            {
                File.Delete(absolutePath);
                _logger.LogInformation("Deleted file: {Path}", absolutePath);
            }
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Failed to delete file at {Path}", storagePath);
        }
        await Task.CompletedTask;
    }

    public async Task<bool> IsPdfAsync(Stream stream, CancellationToken ct = default)
    {
        var buffer = new byte[5];
        var originalPosition = stream.CanSeek ? stream.Position : 0;

        if (stream.CanSeek) stream.Position = 0;
        var bytesRead = await stream.ReadAsync(buffer.AsMemory(0, 5), ct);
        if (stream.CanSeek) stream.Position = originalPosition;

        if (bytesRead < 5) return false;
        return buffer.AsSpan().SequenceEqual(PdfMagicBytes);
    }

    public async Task<string> ComputeHashAsync(Stream stream, CancellationToken ct = default)
    {
        var originalPosition = stream.CanSeek ? stream.Position : 0;
        if (stream.CanSeek) stream.Position = 0;

        using var sha256 = SHA256.Create();
        var hashBytes = await sha256.ComputeHashAsync(stream, ct);

        if (stream.CanSeek) stream.Position = originalPosition;
        return Convert.ToHexString(hashBytes).ToLowerInvariant();
    }
}
