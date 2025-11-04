# Bubble to Supabase Data Synchronization

Automated Python script to sync data from Bubble.io database to Supabase PostgreSQL.

## Overview

This solution automates the process of:
1. Fetching data from Bubble.io REST API with pagination
2. Transforming data for PostgreSQL compatibility
3. Upserting records to Supabase (insert or update based on `_id`)
4. Handling errors and logging progress

## Features

✅ **Incremental Updates** - Uses Bubble's `_id` field for deduplication (upsert logic)
✅ **Pagination Handling** - Automatically fetches all records across multiple pages
✅ **Data Transformation** - Handles JSONB conversion, photo URLs, price fields
✅ **Error Recovery** - Retry logic for failed requests and records
✅ **Progress Tracking** - Detailed logging with timestamps and statistics
✅ **Configurable** - Sync specific tables or all 81 tables
✅ **Safe** - Validates data before insertion, uses transactions

## Prerequisites

1. **Python 3.8+** installed
2. **Bubble.io API Key** with read access
3. **Supabase Service Role Key** (from project dashboard)
4. Network access to both Bubble and Supabase APIs

## Installation

### Step 1: Install Python Dependencies

```bash
pip install -r requirements.txt
```

### Step 2: Configure Environment Variables

1. Copy the template:
   ```bash
   copy .env.template .env.production
   ```

2. Edit `.env.production` and add your Supabase Service Role Key:
   - Go to your Supabase dashboard: https://supabase.com/dashboard/project/qcfifybkaddcoimjroca
   - Navigate to: Settings > API
   - Copy the `service_role` key (NOT the `anon` key!)
   - Paste it into `.env.production` under `SUPABASE_SERVICE_KEY`

3. Verify all credentials:
   ```
   BUBBLE_API_KEY=677ca2fc4b13f1b4eb93b91132da0afe
   SUPABASE_URL=https://qcfifybkaddcoimjroca.supabase.co
   SUPABASE_SERVICE_KEY=eyJhbGc... (your actual key)
   ```

## Usage

### Sync All Tables

```bash
python bubble_to_supabase_sync.py
```

This will sync all 81 tables from Bubble to Supabase.

### Sync Specific Tables

```bash
python bubble_to_supabase_sync.py --tables user listing proposal bookings-stays
```

### Dry Run (Test Without Writing)

```bash
python bubble_to_supabase_sync.py --dry-run
```

This fetches data from Bubble but doesn't write to Supabase. Useful for testing.

### Use Custom Config File

```bash
python bubble_to_supabase_sync.py --config /path/to/custom/.env
```

## How It Works

### 1. Data Extraction from Bubble

The script uses Bubble's REST API:
```
GET https://upgradefromstr.bubbleapps.io/version-live/api/1.1/obj/{table_name}?cursor={cursor}&limit=100
```

- Fetches 100 records per request
- Uses cursor-based pagination
- Continues until `remaining = 0`
- Respects rate limits (500ms delay between calls)

### 2. Data Transformation

The script handles several data transformations:

**JSONB Conversion:**
```python
# Bubble arrays/objects → PostgreSQL JSONB
"Features - Photos": ["id1", "id2"] → JSONB column
```

**Photo URL Fixes:**
```python
# Protocol-relative URLs
"//s3.amazonaws.com/..." → "https://s3.amazonaws.com/..."
```

**Price Fields:**
```python
# Remove currency symbols and formatting
"$1,234.56" → 1234.56 (NUMERIC)
```

### 3. Upsert to Supabase

```python
# Uses _id as primary key for deduplication
supabase.table('user').upsert(records, on_conflict='_id')
```

**Upsert Behavior:**
- If `_id` exists: UPDATE the record with new data
- If `_id` doesn't exist: INSERT new record
- Result: No duplicates, always up-to-date data

### 4. Error Handling

- Failed batches are retried record-by-record
- Errors are logged with full context
- Script continues even if some records fail
- Final summary shows success/failure counts

## Output

### Console Output

```
2025-11-04 10:30:00 - INFO - Starting sync for table: user
2025-11-04 10:30:05 - INFO - user: Fetched 854 records, 0 remaining
2025-11-04 10:30:10 - INFO - user: Batch 1 - 100 records upserted successfully
...
2025-11-04 10:30:45 - INFO - Table sync summary for user:
  - Fetched from Bubble: 854
  - Inserted/Updated: 854
  - Failed: 0
  - Before count: 850
  - After count: 854
  - Net change: 4
  - Duration: 45.23s
```

### Log Files

Two types of logs are created:

1. **sync_YYYYMMDD_HHMMSS.log** - Detailed logs of entire sync process
2. **sync_summary_YYYYMMDD_HHMMSS.json** - JSON summary with statistics

### Summary JSON Example

```json
{
  "start_time": "2025-11-04T10:30:00",
  "end_time": "2025-11-04T11:15:30",
  "duration": 2730.5,
  "tables_synced": 81,
  "successful_tables": 79,
  "partial_tables": 2,
  "failed_tables": 0,
  "total_records_fetched": 71155,
  "total_records_inserted": 71150,
  "total_records_failed": 5,
  "table_results": [...]
}
```

## Scheduling Automated Syncs

### Option 1: Windows Task Scheduler

1. Open Task Scheduler
2. Create Basic Task
3. Name: "Bubble to Supabase Sync"
4. Trigger: Daily at 2:00 AM (or your preferred time)
5. Action: Start a program
   - Program: `python`
   - Arguments: `C:\path\to\bubble_to_supabase_sync.py`
   - Start in: `C:\path\to\supabase-imports`

### Option 2: Python Schedule Library

Install schedule:
```bash
pip install schedule
```

Create `scheduled_sync.py`:
```python
import schedule
import time
from bubble_to_supabase_sync import BubbleToSupabaseSync, SyncConfig

def run_sync():
    config = SyncConfig.from_env()
    sync = BubbleToSupabaseSync(config)
    sync.sync_all_tables()

# Run every day at 2:00 AM
schedule.every().day.at("02:00").do(run_sync)

while True:
    schedule.run_pending()
    time.sleep(60)
```

Run it:
```bash
python scheduled_sync.py
```

### Option 3: Cron (Linux/Mac)

Edit crontab:
```bash
crontab -e
```

Add line:
```
0 2 * * * cd /path/to/supabase-imports && python bubble_to_supabase_sync.py >> sync.log 2>&1
```

## Configuration Options

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `BUBBLE_API_KEY` | Bubble.io API authentication key | Required |
| `BUBBLE_APP_NAME` | Bubble app name | upgradefromstr |
| `BUBBLE_BASE_URL` | Base URL for Bubble API | https://... |
| `SUPABASE_URL` | Supabase project URL | Required |
| `SUPABASE_SERVICE_KEY` | Supabase service role key | Required |
| `BATCH_SIZE` | Records per batch | 100 |
| `RATE_LIMIT_DELAY` | Delay between API calls (seconds) | 0.5 |
| `MAX_RETRIES` | Max retry attempts for failed requests | 3 |

### Tables to Sync

By default, the script syncs all 81 tables:

**Core Business Tables:**
- user
- listing
- proposal
- bookings-stays
- bookings-leases
- account_host
- account_guest
- listing-photo
- paymentrecords
- _message

**Plus 71 more** (see `ALL_TABLES` in script)

To sync specific tables:
```bash
python bubble_to_supabase_sync.py --tables user listing proposal
```

Or set in environment:
```bash
TABLES_TO_SYNC=user,listing,proposal
```

## Monitoring & Maintenance

### Check Sync Status

1. Review log files for errors
2. Check Supabase table counts:
   ```sql
   SELECT COUNT(*) FROM user;
   SELECT COUNT(*) FROM listing;
   ```
3. Compare with Bubble record counts

### Common Issues & Solutions

#### Issue: "BUBBLE_API_KEY not set"
**Solution:** Verify `.env.production` exists and contains the API key

#### Issue: "SUPABASE_SERVICE_KEY not set"
**Solution:** Get the service role key from Supabase dashboard (Settings > API)

#### Issue: "Connection timeout"
**Solution:** Check network connectivity to Supabase. Use connection pooler (port 6543) instead of direct (port 5432)

#### Issue: "Rate limit exceeded"
**Solution:** Increase `RATE_LIMIT_DELAY` in environment (e.g., 1.0 seconds)

#### Issue: "Foreign key constraint violation"
**Solution:** Some tables have dependencies. Sync in order:
```bash
# Sync reference tables first
python bubble_to_supabase_sync.py --tables zat_geo_borough_toplevel zat_geo_hood_mediumlevel

# Then sync core tables
python bubble_to_supabase_sync.py --tables user account_host account_guest listing
```

#### Issue: "Permission denied" or RLS errors
**Solution:** The script uses the service role key which bypasses RLS. If you still get permission errors, verify:
1. You're using the `service_role` key (not `anon` key)
2. The key is correct and not expired

### Performance Optimization

For large datasets:

1. **Increase batch size:**
   ```bash
   BATCH_SIZE=500
   ```

2. **Reduce delay for faster sync:**
   ```bash
   RATE_LIMIT_DELAY=0.1
   ```

3. **Run in parallel** (advanced):
   - Split tables into groups
   - Run multiple sync processes
   - Monitor resource usage

## Data Validation

After sync completes, validate the data:

### 1. Check Record Counts

```sql
-- Supabase
SELECT
  table_name,
  (SELECT COUNT(*) FROM information_schema.tables t
   WHERE t.table_name = tables.table_name) as record_count
FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY record_count DESC;
```

Compare with Bubble API record counts from sync summary JSON.

### 2. Verify Key Relationships

```sql
-- Check user accounts
SELECT
  u._id,
  u."Name - Full",
  ah._id as host_account,
  ag._id as guest_account
FROM user u
LEFT JOIN account_host ah ON u."Account - Host / Landlord" = ah._id
LEFT JOIN account_guest ag ON u."Account - Guest" = ag._id
LIMIT 10;
```

### 3. Check for NULL values

```sql
-- Find records with missing critical fields
SELECT COUNT(*) FROM user WHERE "_id" IS NULL;
SELECT COUNT(*) FROM listing WHERE "Host / Landlord" IS NULL;
```

## Security Considerations

### Credentials Management

⚠️ **NEVER commit `.env.production` to version control!**

1. Add to `.gitignore`:
   ```
   .env.production
   .env
   *.log
   sync_summary_*.json
   ```

2. Store credentials securely:
   - Use environment variables in production
   - Use secret management tools (Azure Key Vault, AWS Secrets Manager)
   - Rotate keys regularly

### API Key Permissions

- **Bubble API Key:** Read-only access is sufficient
- **Supabase Service Key:** Full access - protect carefully

### Network Security

- Run sync from trusted networks
- Use HTTPS for all API calls (already configured)
- Consider VPN for sensitive data transfers

## Troubleshooting

### Enable Debug Logging

Modify script to show debug messages:
```python
logging.basicConfig(
    level=logging.DEBUG,  # Changed from INFO
    ...
)
```

### Test Individual Table

```bash
python bubble_to_supabase_sync.py --tables user
```

### Inspect Data

Add print statements to see transformed records:
```python
# In transform_record() method
print(f"Original: {record}")
print(f"Transformed: {transformed}")
```

### Verify API Connectivity

Test Bubble API:
```bash
curl -H "Authorization: Bearer 677ca2fc4b13f1b4eb93b91132da0afe" \
  "https://upgradefromstr.bubbleapps.io/version-live/api/1.1/obj/user?limit=1"
```

Test Supabase:
```python
from supabase import create_client
client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
print(client.table('user').select('_id').limit(1).execute())
```

## Advanced Usage

### Sync Only New/Updated Records

Modify the script to track last sync time:

```python
# Get records modified after last sync
last_sync = "2025-11-04T00:00:00Z"
params = {
    'cursor': cursor,
    'limit': limit,
    'constraints': [{'key': 'Modified Date', 'constraint_type': 'greater than', 'value': last_sync}]
}
```

### Custom Data Transformations

Add custom transformations in `transform_record()`:

```python
def transform_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
    transformed = super().transform_record(record)

    # Custom: Extract first name from full name
    if 'Name - Full' in transformed:
        transformed['first_name'] = transformed['Name - Full'].split()[0]

    return transformed
```

### Export to Multiple Destinations

Extend the sync to write to multiple targets:

```python
# After fetching from Bubble
records = self.bubble_client.get_all_table_data(table_name)

# Write to Supabase
self.supabase_sync.upsert_records(table_name, records)

# Also write to local JSON backup
with open(f'backup/{table_name}.json', 'w') as f:
    json.dump(records, f)
```

## Architecture

```
┌─────────────┐
│  Bubble.io  │
│  Database   │
└──────┬──────┘
       │ REST API
       │ (Paginated)
       ↓
┌──────────────────┐
│  Python Script   │
│  - Fetch data    │
│  - Transform     │
│  - Validate      │
└──────┬───────────┘
       │ Upsert
       │ (on conflict: _id)
       ↓
┌──────────────────┐
│   Supabase       │
│   PostgreSQL     │
│   (81 tables)    │
└──────────────────┘
```

## Performance Benchmarks

Based on the manual migration:

| Tables | Records | Duration | Rate |
|--------|---------|----------|------|
| 81 | 71,155 | ~45 min | ~26 records/sec |

Factors affecting performance:
- Network latency
- Batch size
- Rate limiting delay
- Record size (JSONB complexity)
- Supabase server load

## License

Internal tool for Split Lease team. Not licensed for external use.

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review log files for error details
3. Contact the development team

## Changelog

### v1.0.0 (2025-11-04)
- Initial release
- Supports all 81 Bubble tables
- Pagination handling
- Upsert logic with deduplication
- Error recovery and logging
- Configurable sync options

---

**Last Updated:** 2025-11-04
**Author:** Split Lease Team
**Python Version:** 3.8+
