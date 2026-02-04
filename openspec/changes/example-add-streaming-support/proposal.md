# Proposal: Add Streaming LLM Response Support

## Overview
Add support for capturing and displaying streaming LLM responses in the Agent Inspector timeline and detail views.

## Motivation

### Current State
Currently, the Agent Inspector captures LLM calls as discrete events with complete prompt-response pairs. This works well for traditional LLM interactions but doesn't support the increasingly common pattern of streaming responses, where tokens are generated and delivered incrementally.

### Problem
When agents use streaming LLM APIs (e.g., OpenAI's streaming mode, Anthropic's streaming, etc.), the current implementation:
- Only captures the final complete response
- Misses the intermediate tokens that are generated
- Cannot visualize the streaming behavior
- Doesn't capture timing information for individual token generation
- Cannot show partial responses during generation

### Impact
Developers debugging agents that use streaming LLMs:
- Cannot see how responses unfold over time
- Can't analyze latency patterns during streaming
- Miss opportunities to identify slow token generation
- Can't observe early cancellation or interruption scenarios
- Have limited visibility into streaming-based reasoning chains

## Proposed Solution

### Core Changes

1. **New Event Type: `llm_token`**
   - Captures individual tokens as they are generated
   - Includes: token text, token index, generation timestamp
   - Linked to parent `llm_call` event

2. **Enhanced `llm_call` Event**
   - Add `streaming: boolean` flag
   - Include `token_count` (when streaming)
   - Track `first_token_latency_ms`
   - Track `last_token_latency_ms`

3. **Timeline Visualization**
   - Display streaming events as a continuous bar in the timeline
   - Show token generation rate (tokens/second)
   - Highlight gaps or pauses in streaming
   - Expandable to show individual tokens

4. **Detail Panel Enhancement**
   - Show streaming timeline within the detail view
   - Display tokens as they appear (animated replay)
   - Show cumulative token count over time
   - Highlight slow token generation periods

5. **Adapter Updates**
   - LangChain adapter: Hook into streaming callbacks
   - Custom adapter support: Provide API for manual token emission
   - Auto-detect streaming mode from LLM configuration

### Data Model

```json
{
  "event_type": "llm_call",
  "streaming": true,
  "first_token_latency_ms": 150,
  "last_token_latency_ms": 2300,
  "total_tokens": 45,
  "tokens_per_second": 19.5
}
```

```json
{
  "event_type": "llm_token",
  "parent_llm_call_id": "abc-123",
  "token_index": 12,
  "token": "the",
  "timestamp_ms": 1738322150123,
  "delta_ms": 52  // time since previous token
}
```

### Storage Considerations

- Token events are stored in a separate table for efficiency
- Optional: Aggregate token data and drop individual tokens after N days
- Configurable: Disable token storage if not needed (sampling)

## Benefits

1. **Better Debugging**: See exactly how responses unfold, identify bottlenecks
2. **Performance Insights**: Measure first-token latency and token generation rates
3. **Streaming Patterns**: Understand agent behavior with streaming (early stopping, interruption)
4. **Complete Trace**: Full visibility into streaming-based reasoning chains
5. **Observability**: Better understanding of LLM performance characteristics

## Affected Components

### Direct Changes
- `core-tracing/spec.md` - New `llm_token` event type, enhanced `llm_call`
- `api/spec.md` - New endpoints for streaming data
- `ui/spec.md` - Timeline and detail view enhancements
- `adapters/spec.md` - Adapter updates for streaming capture
- `storage/spec.md` - New token_events table

### Indirect Changes
- `data-processing/spec.md` - Token event compression optimization
- `configuration/spec.md` - New config for token storage settings

## Migration Path

### Phase 1: Backend Support (Week 1)
- Add `llm_token` event type to core tracing
- Update storage schema with token_events table
- Implement streaming token capture in LangChain adapter
- Add API endpoints for streaming data

### Phase 2: UI Enhancements (Week 2)
- Timeline visualization for streaming events
- Detail panel streaming timeline
- Token replay animation
- Performance metrics display

### Phase 3: Optimization (Week 3)
- Token aggregation and pruning
- Sampling strategies for token events
- Performance tuning for high-volume streaming
- Documentation and examples

## Risks and Mitigations

### Risk: Storage Bloat
Streaming generates many more events than discrete calls.

**Mitigation**: 
- Configurable token storage (disable if not needed)
- Automatic aggregation after retention period
- Sampling for high-volume scenarios

### Risk: Performance Impact
Capturing every token adds overhead.

**Mitigation**:
- Non-blocking queue for token events
- Batch processing for token writes
- Optional token capture (feature flag)
- Benchmark and optimize

### Risk: UI Complexity
Streaming visualization can become complex.

**Mitigation**:
- Start with simple timeline bar
- Progressive enhancement
- Keep individual token view optional
- Clear visual hierarchy

## Alternatives Considered

### Alternative 1: Aggregate Only
Store only aggregate statistics (total tokens, timing) but not individual tokens.

**Pros**: Minimal storage overhead, simpler implementation  
**Cons**: Loses detailed visibility, can't replay or analyze token-by-token

**Decision**: Rejected - defeats purpose of streaming observability

### Alternative 2: Separate Streaming System
Build a separate system for streaming traces.

**Pros**: Keeps core system simple  
**Cons**: Fragmented experience, harder to correlate events, duplicate infrastructure

**Decision**: Rejected - unified tracing is better UX

### Alternative 3: Client-Side Streaming Only
Stream data directly to UI, bypassing storage.

**Pros**: No storage overhead  
**Cons**: No historical analysis, only works for live runs, poor replay support

**Decision**: Rejected - historical analysis is critical for debugging

## Success Criteria

- ✅ Streaming LLM calls are captured with individual token events
- ✅ Timeline shows streaming visualization with token generation rate
- ✅ Detail panel includes streaming timeline and token replay
- ✅ LangChain adapter automatically captures streaming tokens
- ✅ Storage overhead is manageable (configurable)
- ✅ Performance impact on agent execution is negligible (<5ms overhead)
- ✅ Documentation includes examples for streaming debugging
- ✅ Backwards compatible with existing non-streaming traces

## Open Questions

1. Should we store all tokens or aggregate after a configurable period?
2. What's the default retention policy for token events?
3. Should we support sampling for token events (e.g., capture every 5th token)?
4. How do we handle very long streaming responses (10,000+ tokens)?

## Next Steps

1. Approve this proposal
2. Create detailed design document (`design.md`)
3. Break down into implementation tasks (`tasks.md`)
4. Update relevant spec files with new requirements
5. Begin Phase 1 implementation

---

**Affected Specs**: 5 (core-tracing, api, ui, adapters, storage)  
**Estimated Effort**: 3 weeks  
**Priority**: High (streaming is increasingly common)  
**Dependencies**: None (standalone feature)