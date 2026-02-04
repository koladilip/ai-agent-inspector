# Design Document: Streaming LLM Response Support

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Data Model](#data-model)
3. [Core Tracing Changes](#core-tracing-changes)
4. [Storage Layer](#storage-layer)
5. [API Design](#api-design)
6. [UI Implementation](#ui-implementation)
7. [Adapter Integration](#adapter-integration)
8. [Performance Optimization](#performance-optimization)
9. [Security Considerations](#security-considerations)
10. [Testing Strategy](#testing-strategy)
11. [Rollout Plan](#rollout-plan)

## Architecture Overview

### System Diagram

```
[ Agent with Streaming LLM ]
           |
           v
[ LangChain Adapter - Streaming Callbacks ]
           |
           v
[ Core Tracing - emit_llm_token() ]
           |
           v
[ Event Queue - Non-Blocking ]
           |
           v
[ Batch Processor ]
           |
           +---> [ Redaction ]
           |
           +---> [ Serialization ]
           |
           +---> [ Compression ]
           |
           v
[ Storage - llm_call + llm_token tables ]
           |
           v
[ API - Streaming Endpoints ]
           |
           v
[ UI - Timeline + Detail View ]
```

### Key Design Decisions

1. **Separate Event Table**: `llm_token` events stored in dedicated table for efficient querying
2. **Parent-Child Relationship**: Token events reference parent `llm_call` via foreign key
3. **Batch Token Writes**: Tokens collected in memory batch, written together to minimize I/O
4. **Optional Aggregation**: Configurable aggregation period (e.g., after 7 days, keep only aggregates)
5. **Streaming-Aware Timeline**: Visual representation shows continuous stream with token rate
6. **Token Replay**: UI can animate token arrival for debugging timing issues

## Data Model

### Database Schema Changes

#### New Table: `llm_tokens`

```sql
CREATE TABLE llm_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    llm_call_id TEXT NOT NULL,  -- References steps.id where event_type='llm_call'
    token_index INTEGER NOT NULL,
    token TEXT NOT NULL,
    timestamp_ms INTEGER NOT NULL,
    delta_ms INTEGER NOT NULL,  -- Time since previous token
    metadata TEXT,  -- JSON: any additional token-level metadata
    
    FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE,
    FOREIGN KEY (llm_call_id) REFERENCES steps(id) ON DELETE CASCADE
);

-- Indexes for efficient queries
CREATE INDEX idx_llm_tokens_run_id ON llm_tokens(run_id);
CREATE INDEX idx_llm_tokens_llm_call_id ON llm_tokens(llm_call_id);
CREATE INDEX idx_llm_tokens_timestamp ON llm_tokens(timestamp_ms);
```

#### Enhanced `steps` Table

The existing `steps` table already stores event blobs. No schema changes required, but `llm_call` event JSON will include streaming metadata:

```json
{
  "run_id": "uuid",
  "timestamp": 1738322150000,
  "type": "llm_call",
  "model": "gpt-4-turbo",
  "streaming": true,
  "first_token_latency_ms": 150,
  "last_token_latency_ms": 2300,
  "total_tokens": 45,
  "tokens_per_second": 19.5,
  "prompt": "...",
  "full_response": "...",  // Complete response still stored
  "token_ids": ["token1-id", "token2-id", ...]  // References to llm_tokens
}
```

### In-Memory Token Buffer

During streaming, tokens are buffered in memory before batch write:

```python
class TokenBuffer:
    """In-memory buffer for streaming tokens"""
    
    def __init__(self, llm_call_id: str, run_id: str):
        self.llm_call_id = llm_call_id
        self.run_id = run_id
        self.tokens: List[TokenData] = []
        self.start_time = time.time()
        self.last_token_time = self.start_time
    
    def add_token(self, token: str, metadata: Dict = None):
        now = time.time()
        delta_ms = int((now - self.last_token_time) * 1000)
        token_index = len(self.tokens)
        
        token_data = TokenData(
            token_index=token_index,
            token=token,
            timestamp_ms=int(now * 1000),
            delta_ms=delta_ms,
            metadata=metadata or {}
        )
        
        self.tokens.append(token_data)
        self.last_token_time = now
        
        # Flush if buffer gets too large (e.g., 1000 tokens)
        if len(self.tokens) >= 1000:
            self.flush()
    
    def flush(self):
        """Write buffered tokens to database"""
        if not self.tokens:
            return
        
        # Batch insert
        insert_tokens_batch(self.run_id, self.llm_call_id, self.tokens)
        self.tokens.clear()
    
    def finalize(self):
        """Final flush when stream ends"""
        self.flush()
        
        # Update llm_call event with streaming statistics
        total_time = (self.last_token_time - self.start_time) * 1000
        update_llm_call_with_stats(
            self.llm_call_id,
            first_token_latency_ms=self.tokens[0].timestamp_ms if self.tokens else 0,
            last_token_latency_ms=total_time,
            total_tokens=len(self.tokens),
            tokens_per_second=len(self.tokens) / (total_time / 1000) if total_time > 0 else 0
        )
```

## Core Tracing Changes

### New Public API Methods

```python
class Trace:
    # Existing methods...
    
    def start_llm_stream(self, model: str, prompt: str) -> LLMStreamContext:
        """
        Start capturing a streaming LLM call.
        
        Returns a context manager that captures tokens.
        
        Usage:
            with trace.start_llm_stream("gpt-4", "Hello, world!") as stream:
                for token in llm.stream():
                    stream.add_token(token)
        """
        pass
    
    def add_llm_token(self, token: str, metadata: Dict = None):
        """
        Add a single token to the current streaming LLM call.
        Automatically called by LLMStreamContext.
        """
        pass
```

### LLMStreamContext Implementation

```python
class LLMStreamContext:
    """Context manager for streaming LLM calls"""
    
    def __init__(self, trace, model: str, prompt: str):
        self.trace = trace
        self.model = model
        self.prompt = prompt
        self.llm_call_id = None
        self.token_buffer = None
        self.token_count = 0
        self.start_time = None
    
    def __enter__(self):
        # Create initial llm_call event with streaming flag
        self.llm_call_id = self.trace._create_llm_call_event(
            model=self.model,
            prompt=self.prompt,
            streaming=True
        )
        self.start_time = time.time()
        
        # Initialize token buffer
        self.token_buffer = TokenBuffer(
            llm_call_id=self.llm_call_id,
            run_id=self.trace.current_run_id
        )
        
        return self
    
    def add_token(self, token: str, metadata: Dict = None):
        """Add a streaming token"""
        self.token_count += 1
        self.token_buffer.add_token(token, metadata)
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Finalize the stream
        full_response = self.token_buffer.get_accumulated_text()
        
        self.token_buffer.finalize()
        
        # Update the llm_call event with complete response
        self.trace._update_llm_call_event(
            llm_call_id=self.llm_call_id,
            response=full_response,
            streaming_stats={
                'token_count': self.token_count,
                'total_duration_ms': int((time.time() - self.start_time) * 1000)
            }
        )
        
        if exc_type:
            self.trace.error(f"LLM streaming failed: {exc_val}")
```

### Event Model Updates

```python
@dataclass
class LLMTokenEvent:
    """Represents a single token in a streaming LLM response"""
    run_id: str
    llm_call_id: str
    token_index: int
    token: str
    timestamp_ms: int
    delta_ms: int  # Time since previous token
    metadata: Dict[str, Any]
```

## Storage Layer

### Database Queries

#### Get tokens for an LLM call

```python
def get_llm_tokens(llm_call_id: str) -> List[LLMTokenEvent]:
    """
    Retrieve all tokens for a specific LLM call.
    Returns ordered by token_index.
    """
    query = """
        SELECT id, run_id, llm_call_id, token_index, token, 
               timestamp_ms, delta_ms, metadata
        FROM llm_tokens
        WHERE llm_call_id = ?
        ORDER BY token_index ASC
    """
    # Execute and return results
```

#### Get streaming statistics

```python
def get_streaming_stats(run_id: str) -> Dict[str, Any]:
    """
    Get aggregate streaming statistics for a run.
    """
    query = """
        SELECT 
            COUNT(*) as total_tokens,
            AVG(delta_ms) as avg_token_latency_ms,
            MIN(delta_ms) as min_token_latency_ms,
            MAX(delta_ms) as max_token_latency_ms,
            MAX(timestamp_ms) - MIN(timestamp_ms) as total_duration_ms,
            COUNT(*) * 1000.0 / (MAX(timestamp_ms) - MIN(timestamp_ms)) as tokens_per_second
        FROM llm_tokens
        WHERE run_id = ?
    """
    # Execute and return aggregated stats
```

#### Get tokens with time range (for replay)

```python
def get_tokens_in_time_range(run_id: str, start_ms: int, end_ms: int) -> List[LLMTokenEvent]:
    """
    Get tokens within a specific time window.
    Useful for replaying specific segments.
    """
    query = """
        SELECT * FROM llm_tokens
        WHERE run_id = ? AND timestamp_ms BETWEEN ? AND ?
        ORDER BY timestamp_ms ASC
    """
    # Execute and return results
```

### Token Aggregation Job

```python
def aggregate_old_tokens(days: int = 7):
    """
    Aggregate old token events to save storage space.
    
    Keeps:
    - Total token count
    - Streaming statistics
    - First 10 and last 10 tokens
    
    Removes:
    - Individual token records (except first and last 10)
    """
    
    # Find LLM calls older than threshold
    cutoff_time = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)
    
    # For each old LLM call
    for llm_call_id in get_old_llm_calls(cutoff_time):
        # Get statistics
        stats = get_streaming_stats_for_call(llm_call_id)
        
        # Get first and last 10 tokens
        first_tokens = get_n_tokens(llm_call_id, 10, 'ASC')
        last_tokens = get_n_tokens(llm_call_id, 10, 'DESC')
        
        # Store aggregated data in llm_call metadata
        update_llm_call_metadata(llm_call_id, {
            'aggregated': True,
            'total_tokens': stats['total_tokens'],
            'avg_token_latency_ms': stats['avg_token_latency_ms'],
            'tokens_per_second': stats['tokens_per_second'],
            'first_tokens': [t.token for t in first_tokens],
            'last_tokens': [t.token for t in last_tokens]
        })
        
        # Delete intermediate tokens
        delete_intermediate_tokens(llm_call_id, keep_first=10, keep_last=10)
```

## API Design

### New Endpoints

#### Get streaming tokens for an LLM call

```
GET /v1/runs/{run_id}/llm-calls/{llm_call_id}/tokens
```

**Response:**

```json
{
  "llm_call_id": "abc-123",
  "tokens": [
    {
      "index": 0,
      "token": "Hello",
      "timestamp_ms": 1738322150150,
      "delta_ms": 150
    },
    {
      "index": 1,
      "token": ",",
      "timestamp_ms": 1738322150202,
      "delta_ms": 52
    }
  ],
  "stats": {
    "total_tokens": 45,
    "avg_token_latency_ms": 51,
    "tokens_per_second": 19.5
  },
  "total": 45
}
```

#### Get streaming statistics for a run

```
GET /v1/runs/{run_id}/streaming-stats
```

**Response:**

```json
{
  "run_id": "xyz-789",
  "llm_calls": [
    {
      "llm_call_id": "abc-123",
      "model": "gpt-4-turbo",
      "total_tokens": 45,
      "total_duration_ms": 2300,
      "tokens_per_second": 19.5,
      "first_token_latency_ms": 150,
      "last_token_latency_ms": 2300,
      "min_token_latency_ms": 20,
      "max_token_latency_ms": 150
    }
  ],
  "aggregated": {
    "total_tokens": 150,
    "avg_tokens_per_second": 18.2,
    "total_llm_calls": 3
  }
}
```

#### Get tokens in time range (for replay)

```
GET /v1/runs/{run_id}/tokens/timeseries?start=1738322150000&end=1738322200000
```

**Response:**

```json
{
  "tokens": [
    {
      "llm_call_id": "abc-123",
      "token_index": 10,
      "token": "world",
      "timestamp_ms": 1738322151000
    }
  ]
}
```

### Updated Endpoints

#### Enhanced run detail

```
GET /v1/runs/{run_id}
```

**Enhanced Response:**

```json
{
  "id": "xyz-789",
  "name": "streaming_demo",
  "status": "completed",
  "started_at": 1738322150000,
  "completed_at": 1738322155000,
  "duration_ms": 5000,
  "metadata": {
    "streaming_llm_calls": 3,
    "total_tokens": 150
  },
  "streaming_enabled": true
}
```

#### Enhanced timeline endpoint

```
GET /v1/runs/{run_id}/timeline
```

**Enhanced Response for LLM calls:**

```json
{
  "events": [
    {
      "id": "abc-123",
      "type": "llm_call",
      "name": "gpt-4-turbo",
      "timestamp": 1738322150000,
      "duration_ms": 2300,
      "status": "success",
      "streaming": true,
      "tokens_per_second": 19.5,
      "token_count": 45
    }
  ]
}
```

## UI Implementation

### Timeline Enhancements

#### Streaming Event Visualization

```
┌─────────────────────────────────────────────────┐
│ [LLM] gpt-4-turbo (45 tokens, 19.5 tok/s)     │
│ ████████████████████████████████████████████   │
│ ^^^^  <-- Hover shows token rate at position    │
└─────────────────────────────────────────────────┘
```

**Visual Features:**
- Continuous bar representing the stream
- Color gradient to show token generation rate
- Hover tooltip showing token rate at specific position
- Click to expand detail view

#### Timeline Detail View

When a streaming LLM event is clicked:

```
┌──────────────────────────────────────────────────┐
│ LLM Call: gpt-4-turbo                            │
├──────────────────────────────────────────────────┤
│ Model: gpt-4-turbo                               │
│ Streaming: Yes                                   │
│ Tokens: 45                                       │
│ Duration: 2,300ms                                │
│ Token Rate: 19.5 tokens/sec                      │
│ First Token Latency: 150ms                       │
├──────────────────────────────────────────────────┤
│ [🎬 Replay Token Stream]                         │
│ [📊 Token Rate Graph]                            │
│ [📋 View All Tokens]                             │
└──────────────────────────────────────────────────┘
```

### Detail Panel Enhancements

#### Streaming Timeline

```
Token Generation Timeline
─────────────────────────────────────────────────
Time (ms) │ 0    500    1000   1500   2000   2500
          │ ────────┬────────┬────────┬────────
          │     TTTTTTTTTTT   TTTT    TTTTT
          │
Legend:   │ T = Token generated at this time
```

**Features:**
- Visual timeline showing token arrival
- Hover shows token text and exact time
- Highlight gaps/pauses in streaming
- Click on timeline to jump to that position

#### Token Replay Animation

```
┌──────────────────────────────────────────────────┐
│ Token Replay: gpt-4-turbo                        │
├──────────────────────────────────────────────────┤
│ Hello, world! How are you today? ▮               │
│                                    (cursor)     │
│                                                  │
│ [⏮️] [⏸️] [▶️] [⏭️]  Speed: 1x ▾                  │
│ Token: 12/45  Time: 620ms / 2300ms              │
└──────────────────────────────────────────────────┘
```

**Features:**
- Animated text showing tokens arriving in real-time
- Playback controls (play, pause, step forward/back)
- Speed control (0.5x, 1x, 2x, 5x)
- Timeline scrubber

#### Token List View

```
┌──────────────────────────────────────────────────┐
│ Tokens (45)                                       │
├──────────────────────────────────────────────────┤
│ #  Token       Time    Delta                     │
│ 0  Hello       150ms   -                         │
│ 1  ,           202ms   52ms                      │
│ 2  world       254ms   52ms                      │
│ 3  !           280ms   26ms                      │
│ 4  How         310ms   30ms                      │
│ ...                                          [↓] │
└──────────────────────────────────────────────────┘
```

**Features:**
- Paginated list of all tokens
- Show timing information (absolute and delta)
- Filter by token text
- Search functionality

### Performance Optimizations

#### Virtual Scrolling for Large Token Lists

```javascript
// Only render visible tokens
const TokenList = ({ tokens }) => {
  const { startIndex, endIndex } = useVirtualScroll();
  const visibleTokens = tokens.slice(startIndex, endIndex);
  
  return (
    <div>
      {visibleTokens.map(token => <TokenRow key={token.index} {...token} />)}
    </div>
  );
};
```

#### Debounced Token Updates

```javascript
// Don't update UI on every token (too fast)
// Instead, batch updates every 100ms
const useDebouncedTokenUpdate = () => {
  const [tokens, setTokens] = useState([]);
  const pendingTokens = useRef([]);
  
  useEffect(() => {
    const timer = setInterval(() => {
      if (pendingTokens.current.length > 0) {
        setTokens(prev => [...prev, ...pendingTokens.current]);
        pendingTokens.current = [];
      }
    }, 100);
    
    return () => clearInterval(timer);
  }, []);
  
  return { addToken: (token) => pendingTokens.current.push(token), tokens };
};
```

## Adapter Integration

### LangChain Adapter Streaming Support

```python
from langchain.callbacks.base import BaseCallbackHandler
from agent_inspector import trace

class StreamingInspectorCallback(BaseCallbackHandler):
    """LangChain callback that captures streaming tokens"""
    
    def __init__(self, trace_context):
        self.trace_context = trace_context
        self.current_llm_stream = None
    
    def on_llm_start(self, serialized, prompts, **kwargs):
        """Called when LLM starts (before any tokens)"""
        model = kwargs.get("invocation_params", {}).get("model_name", "unknown")
        prompt = prompts[0] if prompts else ""
        
        # Start streaming context
        self.current_llm_stream = self.trace_context.start_llm_stream(
            model=model,
            prompt=prompt
        )
        self.current_llm_stream.__enter__()
    
    def on_llm_new_token(self, token, **kwargs):
        """Called for each streaming token"""
        if self.current_llm_stream:
            self.current_llm_stream.add_token(token)
    
    def on_llm_end(self, response, **kwargs):
        """Called when LLM finishes"""
        if self.current_llm_stream:
            self.current_llm_stream.__exit__(None, None, None)
            self.current_llm_stream = None

# Enable the adapter
from agent_inspector.adapters.langchain import enable

def enable():
    """Enable LangChain adapter with streaming support"""
    from langchain.callbacks.manager import CallbackManager
    
    # Add our streaming callback
    tracer = trace.get_current_tracer()
    if tracer:
        streaming_callback = StreamingInspectorCallback(tracer)
        
        # Inject into existing callbacks
        # (implementation details depend on LangChain version)
        ...
```

### Custom Framework Integration

```python
# For custom agents, provide a simple API
from agent_inspector import trace

class CustomLLMClient:
    def __init__(self, model="gpt-4"):
        self.model = model
    
    def stream(self, prompt):
        """Stream LLM responses with automatic tracing"""
        
        # Start tracing
        with trace.start_llm_stream(self.model, prompt) as stream:
            # Call the actual LLM API
            for token in self._call_openai_stream(prompt):
                # Capture each token
                stream.add_token(token)
                
                # Yield to caller
                yield token
```

## Performance Optimization

### Minimizing Overhead

1. **Non-Blocking Token Capture**
   - Tokens added to in-memory buffer (O(1) operation)
   - Background thread writes to database
   - No blocking I/O on agent thread

2. **Batch Token Writes**
   - Buffer tokens in memory (up to 1000 or stream end)
   - Single batch insert transaction
   - Reduces database round trips by 1000x

3. **Optional Token Storage**
   - Configuration flag: `store_tokens`
   - When false, only aggregate statistics stored
   - Useful for high-volume production scenarios

4. **Token Sampling**
   - Configuration: `token_sample_rate` (e.g., 0.1 = capture 10% of tokens)
   - Deterministic sampling based on token index
   - Maintains approximate statistics

### Database Performance

1. **Efficient Indexes**
   - Index on `(llm_call_id, token_index)` for ordered retrieval
   - Index on `(run_id, timestamp_ms)` for time-series queries
   - Index on `timestamp_ms` for aggregation queries

2. **Connection Pooling**
   - Reuse database connections
   - Batch inserts use single connection

3. **WAL Mode**
   - Already enabled for concurrent access
   - Allows reads during writes

4. **Periodic VACUUM**
   - Weekly cleanup of deleted tokens
   - Reclaims free space
   - Maintains query performance

### Memory Management

1. **Token Buffer Limits**
   - Maximum 1000 tokens in buffer before flush
   - Prevents unbounded memory growth
   - Typical streams: 100-500 tokens

2. **Automatic Flush on Stream End**
   - Guarantees all tokens written
   - No lost data

3. **Buffer Cleanup**
   - Buffer cleared after flush
   - Memory freed immediately

## Security Considerations

### Token Redaction

Tokens are redacted just like other event data:

```python
# Redaction applies to individual tokens
redact_token(token: str, patterns: List[Pattern]) -> str:
    for pattern in patterns:
        if pattern.match(token):
            return "***REDACTED***"
    return token
```

**Example:**
- Input token: "My API key is sk-1234567890abc"
- Redaction pattern: `sk-[a-zA-Z0-9]{32}`
- Output token: "My API key is ***REDACTED***"

### Encryption

Tokens are encrypted alongside other event data:
- Stored as BLOB in `llm_tokens` table
- Encrypted using same key as other events
- Decryption happens in API layer before sending to UI

### Sensitive Token Handling

**Configuration:**

```python
TraceConfig(
    # Don't store tokens that look like secrets
    redact_patterns=[
        r'sk-[a-zA-Z0-9]{32}',  # OpenAI keys
        r'Bearer [a-zA-Z0-9]{32,}',  # Bearer tokens
        r'\b\d{16}\b',  # Credit card numbers
    ],
    # Or disable token storage entirely for sensitive data
    store_tokens=False  # Only store aggregate stats
)
```

## Testing Strategy

### Unit Tests

#### Core Tracing
```python
def test_llm_stream_context():
    """Test streaming context manager"""
    with trace.run("test"):
        with trace.start_llm_stream("gpt-4", "Hello") as stream:
            stream.add_token("Hello")
            stream.add_token(",")
            stream.add_token("world")
        
        # Verify tokens were captured
        tokens = get_llm_tokens(stream.llm_call_id)
        assert len(tokens) == 3
        assert tokens[0].token == "Hello"
```

#### Token Buffer
```python
def test_token_buffer_flush():
    """Test token buffer flushes correctly"""
    buffer = TokenBuffer("call-id", "run-id")
    
    # Add many tokens
    for i in range(1500):  # > 1000 threshold
        buffer.add_token(f"token{i}")
    
    # Should have flushed automatically
    assert len(buffer.tokens) < 1000

def test_token_buffer_finalize():
    """Test buffer finalization updates stats"""
    buffer = TokenBuffer("call-id", "run-id")
    buffer.add_token("Hello")
    buffer.add_token(",")
    buffer.finalize()
    
    # Verify stats were updated
    llm_call = get_llm_call("call-id")
    assert llm_call['total_tokens'] == 2
```

### Integration Tests

#### LangChain Streaming
```python
def test_langchain_streaming_capture():
    """Test LangChain adapter captures streaming tokens"""
    from langchain.chat_models import ChatOpenAI
    from langchain.schema import HumanMessage
    
    enable()  # Enable streaming adapter
    
    llm = ChatOpenAI(model="g-4", streaming=True)
    
    with trace.run("langchain_test"):
        response = llm.invoke([HumanMessage(content="Say 'test'")])
    
    # Verify tokens were captured
    run = get_run(trace.current_run_id)
    tokens = get_llm_tokens(run.id)
    assert len(tokens) > 0
```

### Performance Tests

#### Throughput Test
```python
def test_streaming_throughput():
    """Test streaming performance overhead"""
    import time
    
    start = time.time()
    
    with trace.run("perf_test"):
        with trace.start_llm_stream("gpt-4", "test") as stream:
            for i in range(10000):  # 10k tokens
                stream.add_token(f"token{i}")
    
    duration = time.time() - start
    
    # Should process 10k tokens in < 1 second
    assert duration < 1.0
    print(f"Processed 10k tokens in {duration:.3f}s")
```

### End-to-End Tests

#### UI Token Replay
```python
def test_ui_token_replay(selenium):
    """Test UI can replay streaming tokens"""
    # Start server
    # Navigate to run with streaming LLM
    # Click on LLM event
    # Click "Replay Token Stream"
    # Verify tokens animate correctly
```

### Load Tests

```python
def test_concurrent_streams():
    """Test multiple concurrent streaming LLM calls"""
    import concurrent.futures
    
    def stream_run(run_id):
        with trace.run(run_id):
            with trace.start_llm_stream("gpt-4", "test") as stream:
                for i in range(500):
                    stream.add_token(f"token{i}")
    
    # Run 50 concurrent streams
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        futures = [executor.submit(stream_run, f"run-{i}") for i in range(50)]
        concurrent.futures.wait(futures)
    
    # Verify all tokens captured
    total_tokens = sum(len(get_llm_tokens(f"run-{i}")) for i in range(50))
    assert total_tokens == 50 * 500  # 25,000 tokens total
```

## Rollout Plan

### Phase 1: Backend Foundation (Week 1)

**Goals:**
- Add `llm_tokens` table to schema
- Implement core streaming tracing API
- Add streaming capture to LangChain adapter
- Implement batch token writes
- Add API endpoints for token retrieval

**Deliverables:**
- Database migration script
- `trace.start_llm_stream()` and `trace.add_llm_token()` methods
- Enhanced LangChain adapter with streaming support
- API endpoints: `/llm-calls/{id}/tokens`, `/streaming-stats`
- Unit tests for core functionality

**Success Criteria:**
- All unit tests pass
- LangChain streaming capture works
- API returns tokens correctly
- Performance: <1ms overhead per token

### Phase 2: UI Implementation (Week 2)

**Goals:**
- Timeline visualization for streaming events
- Detail panel enhancements
- Token replay animation
- Token list view
- Real-time updates for running streams

**Deliverables:**
- Enhanced timeline with streaming bars
- Streaming timeline detail view
- Token replay component
- Token list component
- E2E tests for UI

**Success Criteria:**
- UI renders streaming events correctly
- Token replay animation works smoothly
- Real-time updates display tokens as they arrive
- Responsive design works on mobile

### Phase 3: Optimization & Polish (Week 3)

**Goals:**
- Performance tuning
- Token aggregation job
- Documentation
- Additional framework adapters
- Bug fixes

**Deliverables:**
- Token aggregation script
- Performance benchmarks
- Documentation: usage guide, API reference
- AutoGen adapter (if time permits)
- Demo showing streaming debugging

**Success Criteria:**
- Storage overhead <10MB per 100k tokens (with aggregation)
- API response <100ms for 1000 tokens
- Documentation complete
- Demo showcases streaming debugging

### Migration Strategy

#### Database Migration

```sql
-- Migration v1.0.0 -> v1.1.0
CREATE TABLE llm_tokens (...);

-- Create indexes
CREATE INDEX idx_llm_tokens_run_id ON llm_tokens(run_id);
CREATE INDEX idx_llm_tokens_llm_call_id ON llm_tokens(llm_call_id);
CREATE INDEX idx_llm_tokens_timestamp ON llm_tokens(timestamp_ms);
```

**Rollback Plan:**
```sql
DROP TABLE IF EXISTS llm_tokens;
```

#### Backwards Compatibility

- Existing non-streaming traces continue to work
- New streaming features are additive
- UI gracefully handles missing token data

#### Feature Flags

```python
# Gradual rollout
TraceConfig(
    enable_streaming=True,  # Feature flag
    store_tokens=True,      # Individual tokens
    aggregate_after_days=7   # Aggregation policy
)
```

### Monitoring

**Metrics to Track:**

1. **Storage Metrics**
   - `llm_tokens.table_size` - Size of token table
   - `llm_tokens.total_count` - Total tokens stored
   - `llm_tokens.aggregated_count` - Tokens aggregated

2. **Performance Metrics**
   - `streaming.token_capture_latency_ms` - Time to capture token
   - `streaming.token_write_latency_ms` - Time to write batch
   - `streaming.buffer_flush_count` - Number of buffer flushes

3. **Feature Usage**
   - `streaming.llm_calls_count` - Number of streaming LLM calls
   - `streaming.active_streams` - Currently active streams
   - `streaming.token_replay_count` - Number of token replays in UI

### Deployment Checklist

- [ ] Database migration tested on staging
- [ ] Backend deployed and verified
- [ ] API endpoints responding correctly
- [ ] UI deployed and tested
- [ ] Documentation updated
- [ ] Feature flags configured
- [ ] Monitoring dashboards updated
- [ ] Rollback procedure documented
- [ ] Team trained on new features
- [ ] Demo prepared for users

---

**Document Version:** 1.0  
**Last Updated:** 2025-01-15  
**Author:** Agent Inspector Team  
**Status:** Draft - Ready for Review