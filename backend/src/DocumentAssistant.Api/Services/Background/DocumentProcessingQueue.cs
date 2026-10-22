using System.Threading.Channels;

namespace DocumentAssistant.Api.Services.Background;

public interface IDocumentProcessingQueue
{
    ValueTask QueueBackgroundWorkItemAsync(Guid documentId, CancellationToken cancellationToken = default);
    ValueTask<Guid> DequeueAsync(CancellationToken cancellationToken);
}

public class DocumentProcessingQueue : IDocumentProcessingQueue
{
    private readonly Channel<Guid> _queue;

    public DocumentProcessingQueue()
    {
        // Unbounded or bounded channel with backpressure
        var options = new BoundedChannelOptions(100)
        {
            FullMode = BoundedChannelFullMode.Wait
        };
        _queue = Channel.CreateBounded<Guid>(options);
    }

    public async ValueTask QueueBackgroundWorkItemAsync(Guid documentId, CancellationToken cancellationToken = default)
    {
        await _queue.Writer.WriteAsync(documentId, cancellationToken);
    }

    public async ValueTask<Guid> DequeueAsync(CancellationToken cancellationToken)
    {
        return await _queue.Reader.ReadAsync(cancellationToken);
    }
}
