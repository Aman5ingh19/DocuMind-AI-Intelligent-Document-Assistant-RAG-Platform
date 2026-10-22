using DocumentAssistant.Api.Models;
using System.Net.Http.Json;
using System.Text.Json;

namespace DocumentAssistant.Api.Services;

public interface IAiServiceClient
{
    Task<AiProcessDocumentResponse> ProcessDocumentAsync(string documentId, string filePath, CancellationToken cancellationToken = default);
    Task<AiQueryResponse> QueryAsync(AiQueryRequest request, CancellationToken cancellationToken = default);
    Task<bool> DeleteDocumentVectorsAsync(string documentId, CancellationToken cancellationToken = default);
}

public class AiServiceClient : IAiServiceClient
{
    private readonly HttpClient _httpClient;
    private readonly IConfiguration _configuration;
    private readonly ILogger<AiServiceClient> _logger;
    private readonly JsonSerializerOptions _jsonOptions;

    public AiServiceClient(
        HttpClient httpClient,
        IConfiguration configuration,
        ILogger<AiServiceClient> _logger)
    {
        _httpClient = httpClient;
        _configuration = configuration;
        this._logger = _logger;
        _jsonOptions = new JsonSerializerOptions
        {
            PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
            PropertyNameCaseInsensitive = true
        };
    }

    private void AddInternalApiKeyHeader(HttpRequestMessage request)
    {
        var apiKey = _configuration["AiService:InternalApiKey"] ?? "dev-internal-secret-key-change-in-production";
        request.Headers.Add("X-Internal-API-Key", apiKey);
    }

    public async Task<AiProcessDocumentResponse> ProcessDocumentAsync(
        string documentId,
        string filePath,
        CancellationToken cancellationToken = default)
    {
        _logger.LogInformation("Calling AI service to process document: {DocumentId}", documentId);

        var requestBody = new { document_id = documentId, file_path = filePath };
        using var request = new HttpRequestMessage(HttpMethod.Post, "/api/v1/process-document")
        {
            Content = JsonContent.Create(requestBody)
        };
        AddInternalApiKeyHeader(request);

        using var response = await _httpClient.SendAsync(request, cancellationToken);
        if (!response.IsSuccessStatusCode)
        {
            var errorContent = await response.Content.ReadAsStringAsync(cancellationToken);
            _logger.LogError("AI service process-document failed with status {StatusCode}: {Error}",
                response.StatusCode, errorContent);
            throw new HttpRequestException($"AI service processing failed: {response.StatusCode} - {errorContent}");
        }

        var result = await response.Content.ReadFromJsonAsync<AiProcessDocumentResponse>(_jsonOptions, cancellationToken);
        return result ?? throw new InvalidOperationException("Empty response from AI service.");
    }

    public async Task<AiQueryResponse> QueryAsync(
        AiQueryRequest queryRequest,
        CancellationToken cancellationToken = default)
    {
        _logger.LogInformation("Calling AI service query with question: '{Question}' on {Count} documents",
            queryRequest.Question, queryRequest.DocumentIds.Count);

        var payload = new
        {
            question = queryRequest.Question,
            document_ids = queryRequest.DocumentIds,
            conversation_history = queryRequest.ConversationHistory?.Select(m => new
            {
                role = m.Role,
                content = m.Content
            })
        };

        using var request = new HttpRequestMessage(HttpMethod.Post, "/api/v1/query")
        {
            Content = JsonContent.Create(payload)
        };
        AddInternalApiKeyHeader(request);

        using var response = await _httpClient.SendAsync(request, cancellationToken);
        if (!response.IsSuccessStatusCode)
        {
            var errorContent = await response.Content.ReadAsStringAsync(cancellationToken);
            _logger.LogError("AI service query failed with status {StatusCode}: {Error}",
                response.StatusCode, errorContent);
            throw new HttpRequestException($"AI service query failed: {response.StatusCode} - {errorContent}");
        }

        var result = await response.Content.ReadFromJsonAsync<AiQueryResponse>(_jsonOptions, cancellationToken);
        return result ?? throw new InvalidOperationException("Empty response from AI service query.");
    }

    public async Task<bool> DeleteDocumentVectorsAsync(
        string documentId,
        CancellationToken cancellationToken = default)
    {
        _logger.LogInformation("Calling AI service to delete vectors for document {DocumentId}", documentId);

        using var request = new HttpRequestMessage(HttpMethod.Delete, $"/api/v1/documents/{documentId}");
        AddInternalApiKeyHeader(request);

        using var response = await _httpClient.SendAsync(request, cancellationToken);
        if (!response.IsSuccessStatusCode)
        {
            var errorContent = await response.Content.ReadAsStringAsync(cancellationToken);
            _logger.LogWarning("AI service vector deletion returned {StatusCode}: {Error}",
                response.StatusCode, errorContent);
            return false;
        }

        return true;
    }
}
