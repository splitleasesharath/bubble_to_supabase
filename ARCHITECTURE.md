# Bubble to Supabase Sync - Architecture

## Overview

This document describes the architecture and design decisions for the automated data synchronization between Bubble.io and Supabase.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    BUBBLE.IO (Source of Truth)                   │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐                │
│  │   user     │  │  listing   │  │  bookings  │  ... (81 tables)│
│  └────────────┘  └────────────┘  └────────────┘                │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           │ REST API (HTTPS)
                           │ GET /api/1.1/obj/{table}
                           │ Pagination: cursor-based
                           │ Auth: Bearer token
                           │
                           ↓
┌─────────────────────────────────────────────────────────────────┐
│              PYTHON SYNC SCRIPT (Orchestrator)                   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  BubbleAPIClient                                          │  │
│  │  - Fetch data with pagination                            │  │
│  │  - Handle rate limiting (500ms delay)                    │  │
│  │  - Retry failed requests (3 attempts)                    │  │
│  │  - Build complete dataset from pages                     │  │
│  └──────────────────────────────────────────────────────────┘  │
│                           │                                      │
│                           ↓                                      │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Data Transformer                                         │  │
│  │  - Convert arrays/objects → JSONB                        │  │
│  │  - Fix photo URLs (// → https://)                        │  │
│  │  - Parse price fields ($1,234.56 → 1234.56)             │  │
│  │  - Preserve Bubble _id for deduplication                 │  │
│  └──────────────────────────────────────────────────────────┘  │
│                           │                                      │
│                           ↓                                      │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  SupabaseSync                                             │  │
│  │  - Batch upsert (100 records/batch)                      │  │
│  │  - ON CONFLICT(_id) DO UPDATE                            │  │
│  │  - Error recovery (retry individual records)             │  │
│  │  - Progress tracking & logging                           │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           │ Supabase Client SDK
                           │ UPSERT operations
                           │ Auth: Service role key
                           │
                           ↓
┌─────────────────────────────────────────────────────────────────┐
│                 SUPABASE (PostgreSQL Database)                   │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐                │
│  │   user     │  │  listing   │  │ bookings_  │  ... (81 tables)│
│  │            │  │            │  │   stays    │                 │
│  └────────────┘  └────────────┘  └────────────┘                │
│                                                                  │
│  Features:                                                       │
│  - Primary key: _id (text) - Bubble's unique IDs               │
│  - Deduplication via UPSERT                                     │
│  - JSONB columns for complex data                              │
│  - Row Level Security (needs configuration)                    │
│  - Connection pooling (port 6543)                              │
└─────────────────────────────────────────────────────────────────┘
```

## Data Flow

### 1. Fetch Phase

```
FOR each table in [user, listing, bookings-stays, ...]:
    cursor = 0
    all_records = []

    WHILE True:
        response = GET /api/1.1/obj/{table}?cursor={cursor}&limit=100
        records = response['response']
        remaining = response['remaining']

        all_records.extend(records)

        IF remaining == 0:
            BREAK

        cursor += len(records)
        SLEEP 500ms  # Rate limiting

    RETURN all_records
```

### 2. Transform Phase

```
FOR each record in all_records:
    transformed = {}

    FOR key, value in record:
        IF value is list or dict:
            # Convert to JSONB
            transformed[key] = json.dumps(value)

        ELSE IF key contains "price" AND value like "$1,234.56":
            # Parse price
            transformed[key] = float(value.replace('$', '').replace(',', ''))

        ELSE IF key == "Photo" AND value starts with "//":
            # Fix protocol-relative URLs
            transformed[key] = "https:" + value

        ELSE:
            transformed[key] = value

    RETURN transformed
```

### 3. Upsert Phase

```
FOR each batch of 100 records:
    TRY:
        supabase.table(table_name).upsert(
            batch,
            on_conflict='_id'
        ).execute()

        success_count += len(batch)

    CATCH error:
        # Batch failed, try individual records
        FOR each record in batch:
            TRY:
                supabase.table(table_name).upsert(
                    record,
                    on_conflict='_id'
                ).execute()

                success_count += 1

            CATCH error:
                error_count += 1
                LOG error details
```

## Component Details

### BubbleAPIClient

**Purpose:** Handles all interactions with Bubble.io REST API

**Key Methods:**
- `get_table_data(table, cursor, limit)` - Fetch single page
- `get_all_table_data(table)` - Fetch all pages (automated pagination)

**Features:**
- Automatic retry with exponential backoff
- Rate limiting (configurable delay)
- Session management with connection pooling
- Detailed error logging

**Configuration:**
```python
rate_limit_delay: 0.5 seconds  # Prevent API throttling
max_retries: 3                 # Retry failed requests
batch_size: 100                # Records per page
```

### Data Transformer

**Purpose:** Convert Bubble data format to Supabase-compatible format

**Transformations:**

| Source Type | Target Type | Example |
|-------------|-------------|---------|
| Array | JSONB | `["id1", "id2"]` → `'["id1","id2"]'::jsonb` |
| Object | JSONB | `{key: val}` → `'{"key":"val"}'::jsonb` |
| Price string | NUMERIC | `"$1,234.56"` → `1234.56` |
| Protocol-relative URL | HTTPS URL | `"//cdn.com/img.jpg"` → `"https://cdn.com/img.jpg"` |
| Bubble _id | TEXT | `"1637349440736x622780446630946800"` (preserved) |

**Special Handling:**
- NULL values: Skip (let database use defaults)
- Empty strings: Convert to NULL where appropriate
- Date/time: Preserve ISO 8601 format
- Boolean: Convert string "true"/"false" to boolean

### SupabaseSync

**Purpose:** Manages data insertion into Supabase PostgreSQL

**Key Methods:**
- `upsert_records(table, records, batch_size)` - Batch insert/update
- `get_table_count(table)` - Current record count
- `transform_record(record)` - Apply transformations

**Upsert Strategy:**
```sql
-- PostgreSQL UPSERT operation
INSERT INTO table_name (_id, field1, field2, ...)
VALUES ('id1', 'val1', 'val2', ...)
ON CONFLICT (_id) DO UPDATE SET
    field1 = EXCLUDED.field1,
    field2 = EXCLUDED.field2,
    ...
```

**Benefits:**
- No duplicate records (enforced by _id primary key)
- Updates existing records with new data
- Handles incremental sync efficiently

## Design Decisions

### Why Python?

1. **Mature Supabase SDK** - Official `supabase-py` library
2. **Rich ecosystem** - requests, pandas, schedule, etc.
3. **Easy deployment** - Cross-platform, minimal dependencies
4. **Excellent error handling** - try/except, logging
5. **Team familiarity** - Easier to maintain

### Why Upsert vs Insert?

**Upsert (chosen):**
- ✓ Handles updates from Bubble
- ✓ Idempotent (can re-run safely)
- ✓ No duplicate key errors
- ✓ Supports incremental sync

**Insert only:**
- ✗ Fails on duplicate _id
- ✗ Can't update existing records
- ✗ Requires delete before re-sync

### Why Batch Processing?

**Benefits:**
- Reduces network round-trips (1 request for 100 records vs 100 requests)
- Faster overall sync time
- Lower load on Supabase
- Maintains transaction boundaries

**Trade-offs:**
- If batch fails, need to retry individually
- Memory usage for large batches
- Less granular progress tracking

**Optimal batch size: 100 records**
- Based on Bubble's API limit (100 records/page)
- Balances speed vs memory
- Matches database connection limits

### Why Service Role Key?

**Service Role Key (chosen):**
- ✓ Bypasses Row Level Security (RLS)
- ✓ Full database access
- ✓ Can write to any table
- ✓ Suitable for backend operations

**Anon Key:**
- ✗ Subject to RLS policies
- ✗ Limited permissions
- ✗ May fail on protected tables
- ✗ Intended for frontend use

**Security:** Service key should only be used server-side, never exposed to clients

### Why Preserve Bubble _id?

**Benefits:**
- Maintains data lineage (can trace records back to Bubble)
- Enables bidirectional sync (future: Supabase → Bubble)
- Natural primary key (unique, immutable)
- Preserves relationships (foreign keys use _id)

**Alternative (UUID mapping):**
- ✗ Requires mapping table
- ✗ More complex queries
- ✗ Loses traceability
- ✗ Can't sync back to Bubble

## Scalability Considerations

### Current Scale
- 81 tables
- ~71,000 records
- ~45 minutes sync time
- Rate: ~26 records/second

### Scaling Strategies

**For larger datasets (100K+ records):**

1. **Parallel processing**
   ```python
   # Process multiple tables concurrently
   from concurrent.futures import ThreadPoolExecutor

   with ThreadPoolExecutor(max_workers=4) as executor:
       futures = [executor.submit(sync_table, t) for t in tables]
   ```

2. **Incremental sync** (only new/updated)
   ```python
   # Filter by Modified Date
   params = {
       'constraints': [{
           'key': 'Modified Date',
           'constraint_type': 'greater than',
           'value': last_sync_time
       }]
   }
   ```

3. **Database optimizations**
   ```sql
   -- Add indexes on foreign keys
   CREATE INDEX idx_listing_host ON listing("Host / Landlord");
   CREATE INDEX idx_bookings_guest ON bookings_stays("Guest");

   -- Use connection pooler
   -- Already configured (port 6543)
   ```

4. **Streaming inserts** (for very large tables)
   ```python
   # Instead of loading all records into memory
   for batch in fetch_batches(table):
       upsert_batch(batch)
       # Free memory after each batch
   ```

## Error Handling

### Retry Strategy

```
Level 1: HTTP Request Retry (urllib3)
├─ Max retries: 3
├─ Backoff: Exponential (1s, 2s, 4s)
└─ Retry on: 429, 500, 502, 503, 504

Level 2: Batch Retry
├─ If batch fails: Retry individual records
└─ Log failed record IDs

Level 3: Manual Recovery
├─ Review logs
├─ Identify failed records
└─ Re-run sync for specific table
```

### Error Categories

**Network Errors:**
- Timeout → Retry with exponential backoff
- Connection refused → Check network, log error
- DNS failure → Check URL configuration

**API Errors:**
- 401 Unauthorized → Invalid API key
- 404 Not Found → Table doesn't exist
- 429 Rate Limit → Increase delay between requests
- 500 Server Error → Retry (may be transient)

**Database Errors:**
- Constraint violation → Check data integrity
- Type mismatch → Review transformation logic
- RLS denied → Verify using service role key
- Connection timeout → Use pooler (port 6543)

## Monitoring & Logging

### Log Levels

```
DEBUG: Detailed request/response data
INFO:  Progress updates, summaries
WARN:  Recoverable issues (partial failures)
ERROR: Failed operations requiring attention
```

### Key Metrics

```json
{
  "table": "user",
  "records_fetched": 854,
  "records_inserted": 850,
  "records_failed": 4,
  "duration": 45.23,
  "success_rate": 0.995
}
```

### Log Files

1. **sync_YYYYMMDD_HHMMSS.log**
   - Detailed operation log
   - All API calls and responses
   - Error stack traces
   - Timing information

2. **sync_summary_YYYYMMDD_HHMMSS.json**
   - High-level statistics
   - Per-table results
   - Overall success/failure counts
   - Timestamp and duration

## Security

### Credentials Storage

```bash
# .env.production (NOT in version control)
BUBBLE_API_KEY=secret123
SUPABASE_SERVICE_KEY=secret456

# .gitignore
.env
.env.production
.env.*
*.log
sync_summary_*.json
```

### Access Control

```
Bubble API Key:
├─ Read-only access to data types
├─ No write/delete permissions
└─ Can be rotated without code changes

Supabase Service Key:
├─ Full database access
├─ Bypasses RLS
├─ Should only run server-side
└─ Rotate regularly
```

### Data Privacy

```
Sensitive fields to consider:
- Email addresses
- Phone numbers
- Payment information
- Personal identification

Options:
1. Exclude from sync (filter out fields)
2. Hash/encrypt before storage
3. Use RLS to restrict access
4. Audit access logs
```

## Future Enhancements

### 1. Bidirectional Sync
- Supabase changes → Bubble
- Conflict resolution strategy
- Change tracking (Modified Date)

### 2. Real-time Sync
- Bubble webhooks → Trigger sync
- Near real-time updates (< 5 minutes)
- Event-driven architecture

### 3. Selective Field Sync
- Sync only specific fields
- Reduce bandwidth
- Filter sensitive data

### 4. Change Detection
- Track deltas (only changed records)
- Reduce processing time
- Efficient incremental updates

### 5. Monitoring Dashboard
- Web UI for sync status
- Real-time progress tracking
- Historical sync analytics
- Error notifications

### 6. Automated Recovery
- Detect failed syncs
- Automatically retry
- Alert on persistent failures

---

## References

- **Bubble API Docs:** https://manual.bubble.io/core-resources/api
- **Supabase Python SDK:** https://supabase.com/docs/reference/python
- **PostgreSQL UPSERT:** https://www.postgresql.org/docs/current/sql-insert.html

---

**Document Version:** 1.0
**Last Updated:** 2025-11-04
**Maintained by:** Split Lease Team
