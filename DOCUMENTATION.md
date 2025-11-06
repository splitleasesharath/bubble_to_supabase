# Bubble to Supabase Sync - Complete Documentation

**Version:** 2.0.0
**Last Updated:** 2025-11-06
**Maintained By:** Split Lease Team

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Directory Structure](#directory-structure)
3. [Quick Start](#quick-start)
4. [Installation & Setup](#installation--setup)
5. [Configuration](#configuration)
6. [Usage Guide](#usage-guide)
7. [Logging System](#logging-system)
8. [Data Flow & Architecture](#data-flow--architecture)
9. [Error Handling](#error-handling)
10. [Monitoring & Maintenance](#monitoring--maintenance)
11. [Troubleshooting](#troubleshooting)
12. [Development Guide](#development-guide)
13. [Security Best Practices](#security-best-practices)
14. [Performance Optimization](#performance-optimization)

---

## Project Overview

### Purpose

This project provides an automated data synchronization solution between Bubble.io and Supabase PostgreSQL. It handles the extraction, transformation, and loading (ETL) of data from 81 Bubble tables into Supabase, maintaining data integrity and providing comprehensive error logging.

### Key Features

- **Automated ETL Pipeline**: Fetches, transforms, and syncs data from Bubble to Supabase
- **Incremental Updates**: Uses upsert logic based on Bubble's `_id` field
- **Robust Error Handling**: Comprehensive error logging with detailed context
- **Batch Processing**: Efficient batch operations with configurable size
- **Pagination Support**: Handles large datasets with cursor-based pagination
- **Data Transformation**: Converts Bubble data types to PostgreSQL-compatible formats
- **Progress Tracking**: Real-time logging and summary reports
- **Flexible Configuration**: Sync all tables or specific subsets

### System Requirements

- Python 3.8 or higher
- Network access to Bubble.io API
- Network access to Supabase API
- 100MB+ free disk space for logs
- Valid API credentials for both services

---

## Directory Structure

```
supabase-imports/
├── bubble_to_supabase_sync.py    # Main synchronization script
├── requirements.txt               # Python dependencies
├── .env.template                  # Environment variable template
├── .env                          # Your environment configuration (git-ignored)
├── .gitignore                    # Git ignore rules
├── README.md                     # Quick reference guide
├── DOCUMENTATION.md              # This comprehensive documentation
│
├── logs/                         # All log files (git-ignored)
│   ├── sync_YYYYMMDD_HHMMSS.log          # Detailed sync logs
│   ├── sync_errors_YYYYMMDD_HHMMSS.json  # Error details in JSON
│   └── sync_summary_YYYYMMDD_HHMMSS.json # Sync summary statistics
│
└── dump/                         # Archived/outdated files (git-ignored)
    ├── *.md                      # Old documentation files
    ├── *.py                      # Deprecated utility scripts
    └── *.json                    # Old schema analysis files
```

### File Descriptions

| File/Directory | Purpose | Git Tracked |
|----------------|---------|-------------|
| `bubble_to_supabase_sync.py` | Main ETL script | Yes |
| `requirements.txt` | Python package dependencies | Yes |
| `.env.template` | Template for environment variables | Yes |
| `.env` | Actual credentials (NEVER commit!) | No |
| `logs/` | All runtime logs and error files | No |
| `dump/` | Archived old files | No |
| `README.md` | Quick reference documentation | Yes |
| `DOCUMENTATION.md` | Comprehensive documentation | Yes |

---

## Quick Start

### 1. First Time Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Copy environment template
copy .env.template .env

# Edit .env with your credentials
notepad .env
```

### 2. Run Your First Sync

```bash
# Test with dry run (no database writes)
python bubble_to_supabase_sync.py --dry-run

# Sync a single table for testing
python bubble_to_supabase_sync.py --tables user

# Sync all tables
python bubble_to_supabase_sync.py
```

### 3. Check Results

```bash
# View latest log file
dir logs\*.log /O-D | findstr /n "^" | findstr "^1:"
type logs\sync_YYYYMMDD_HHMMSS.log

# View summary
type logs\sync_summary_YYYYMMDD_HHMMSS.json
```

---

## Installation & Setup

### Step 1: Install Python Dependencies

```bash
pip install -r requirements.txt
```

**Required packages:**
- `supabase` - Supabase Python client
- `requests` - HTTP library for API calls
- `python-dotenv` - Environment variable management
- `urllib3` - HTTP connection pooling and retry logic

### Step 2: Configure Environment Variables

1. **Copy the template:**
   ```bash
   copy .env.template .env
   ```

2. **Get your Bubble API credentials:**
   - Log into your Bubble.io account
   - Go to Settings > API
   - Copy your API token
   - Note your app name from the URL

3. **Get your Supabase credentials:**
   - Log into Supabase dashboard
   - Go to Settings > API
   - Copy Project URL
   - Copy Service Role Key (NOT the anon key)

4. **Edit `.env` file:**
   ```env
   # Bubble.io Configuration
   BUBBLE_API_KEY=your_bubble_api_key_here
   BUBBLE_APP_NAME=your_app_name
   BUBBLE_BASE_URL=https://your-app.bubbleapps.io/api/1.1/obj

   # Supabase Configuration
   SUPABASE_URL=https://your-project.supabase.co
   SUPABASE_SERVICE_KEY=your_service_role_key_here

   # Sync Configuration (optional)
   BATCH_SIZE=100
   RATE_LIMIT_DELAY=0.5
   MAX_RETRIES=3
   ```

### Step 3: Verify Setup

```bash
# Test Bubble API connection
python -c "import os; from dotenv import load_dotenv; load_dotenv(); import requests; r = requests.get(os.getenv('BUBBLE_BASE_URL').replace('/obj', '/user?limit=1'), headers={'Authorization': f'Bearer {os.getenv(\"BUBBLE_API_KEY\")}'}); print(f'Bubble API: {r.status_code}')"

# Test Supabase connection
python -c "from dotenv import load_dotenv; import os; load_dotenv(); from supabase import create_client; client = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_KEY')); print('Supabase: Connected')"
```

---

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `BUBBLE_API_KEY` | Yes | - | Your Bubble.io API authentication token |
| `BUBBLE_APP_NAME` | Yes | - | Your Bubble app name |
| `BUBBLE_BASE_URL` | Yes | - | Base URL for Bubble API endpoints |
| `SUPABASE_URL` | Yes | - | Your Supabase project URL |
| `SUPABASE_SERVICE_KEY` | Yes | - | Supabase service role key (full access) |
| `BATCH_SIZE` | No | 100 | Number of records per batch upsert |
| `RATE_LIMIT_DELAY` | No | 0.5 | Delay in seconds between API calls |
| `MAX_RETRIES` | No | 3 | Maximum retry attempts for failed requests |

### Sync Options

The script supports various command-line options:

```bash
# Sync specific tables
python bubble_to_supabase_sync.py --tables user listing proposal

# Dry run (fetch but don't write)
python bubble_to_supabase_sync.py --dry-run

# Use custom environment file
python bubble_to_supabase_sync.py --config /path/to/custom.env

# Combine options
python bubble_to_supabase_sync.py --tables user --dry-run
```

### Tables Available for Sync

The script can sync 81 tables from Bubble. Key tables include:

**Core Business Tables:**
- `user` - User accounts
- `listing` - Property listings
- `proposal` - Rental proposals
- `bookings-stays` - Short-term bookings
- `bookings-leases` - Long-term leases
- `account_host` - Host/landlord accounts
- `account_guest` - Guest/tenant accounts
- `paymentrecords` - Payment history
- `_message` - Messages between users

**Supporting Tables:**
- `listing-photo` - Property photos
- `calendar_dateblocked` - Blocked dates
- `review_public` - Public reviews
- `zat_geo_*` - Geographic data tables
- And 68 more tables...

---

## Usage Guide

### Basic Usage

#### Sync All Tables
```bash
python bubble_to_supabase_sync.py
```
This syncs all 81 tables from Bubble to Supabase. Estimated time: 30-60 minutes depending on data volume.

#### Sync Specific Tables
```bash
python bubble_to_supabase_sync.py --tables user listing proposal
```
Only syncs the specified tables. Useful for targeted updates.

#### Dry Run Mode
```bash
python bubble_to_supabase_sync.py --dry-run
```
Fetches data from Bubble but doesn't write to Supabase. Use for testing transformations.

### Advanced Usage

#### Sync with Custom Configuration
```bash
python bubble_to_supabase_sync.py --config .env.production
```
Use a different environment file for production vs. development.

#### Programmatic Usage
```python
from bubble_to_supabase_sync import BubbleToSupabaseSync, SyncConfig

# Load configuration
config = SyncConfig.from_env('.env.production')

# Create sync instance
sync = BubbleToSupabaseSync(config)

# Sync all tables
summary = sync.sync_all_tables()

# Or sync specific tables
summary = sync.sync_tables(['user', 'listing'])
```

### Scheduling Automated Syncs

#### Windows Task Scheduler

1. Open Task Scheduler (`taskschd.msc`)
2. Create Basic Task
3. Configure:
   - **Name:** Bubble to Supabase Sync
   - **Trigger:** Daily at 2:00 AM
   - **Action:** Start a program
   - **Program:** `python`
   - **Arguments:** `C:\path\to\bubble_to_supabase_sync.py`
   - **Start in:** `C:\path\to\supabase-imports`

#### Linux/Mac Cron

```bash
# Edit crontab
crontab -e

# Add daily sync at 2 AM
0 2 * * * cd /path/to/supabase-imports && python bubble_to_supabase_sync.py >> logs/cron.log 2>&1
```

#### Python Schedule Library

```python
import schedule
import time
from bubble_to_supabase_sync import BubbleToSupabaseSync, SyncConfig

def run_sync():
    config = SyncConfig.from_env()
    sync = BubbleToSupabaseSync(config)
    sync.sync_all_tables()

# Run every day at 2 AM
schedule.every().day.at("02:00").do(run_sync)

while True:
    schedule.run_pending()
    time.sleep(60)
```

---

## Logging System

### Log File Types

The script generates three types of log files in the `logs/` directory:

#### 1. Detailed Sync Logs (`sync_YYYYMMDD_HHMMSS.log`)

**Format:** Plain text with timestamps
**Purpose:** Complete record of sync process
**Contains:**
- Start/end timestamps
- Progress for each table
- Batch processing status
- Warning and error messages
- Final summary statistics

**Example:**
```
2025-11-06 10:30:00 - INFO - Starting Bubble to Supabase sync
2025-11-06 10:30:01 - INFO - Syncing table: user
2025-11-06 10:30:05 - INFO - user: Fetched 854 records, 0 remaining
2025-11-06 10:30:10 - INFO - user: Batch 1 - 100 records upserted
2025-11-06 10:30:45 - INFO - user: Sync completed (854 records)
```

#### 2. Error Logs (`sync_errors_YYYYMMDD_HHMMSS.json`)

**Format:** JSON
**Purpose:** Detailed error information
**Contains:**
- Timestamp of each error
- Table name
- Error type (field_transform, upsert_batch, etc.)
- Record ID from Bubble
- Field name that caused error
- Original value and type from Bubble
- Expected Supabase type
- Full error message

**Example:**
```json
{
  "timestamp": "2025-11-06T10:30:15",
  "run_id": "20251106_103000",
  "table": "listing",
  "error_type": "field_transform",
  "error_message": "Cannot convert string to numeric",
  "record_id": "1234567890abcdef",
  "field_name": "Price per month",
  "bubble_value": "$1,234.56",
  "bubble_type": "str",
  "supabase_type": "numeric",
  "full_record": { ... }
}
```

#### 3. Summary Reports (`sync_summary_YYYYMMDD_HHMMSS.json`)

**Format:** JSON
**Purpose:** High-level statistics
**Contains:**
- Overall sync duration
- Table counts (successful, partial, failed)
- Record counts (fetched, inserted, failed)
- Per-table statistics
- Error summary

**Example:**
```json
{
  "start_time": "2025-11-06T10:30:00",
  "end_time": "2025-11-06T11:15:30",
  "duration_seconds": 2730.5,
  "tables_synced": 81,
  "successful_tables": 79,
  "partial_tables": 2,
  "failed_tables": 0,
  "total_records_fetched": 71155,
  "total_records_upserted": 71150,
  "total_records_failed": 5,
  "table_results": [
    {
      "table": "user",
      "fetched": 854,
      "upserted": 854,
      "failed": 0,
      "duration": 45.2
    }
  ]
}
```

### Log Retention

**Recommended retention policy:**
- Keep logs for last 30 days
- Archive monthly summaries for 1 year
- Delete error logs after resolution

**Clean up old logs:**
```bash
# Windows - Delete logs older than 30 days
forfiles /P logs /S /D -30 /C "cmd /c del @path"

# Linux/Mac - Delete logs older than 30 days
find logs/ -name "sync_*" -mtime +30 -delete
```

### Viewing Logs

**Latest sync log:**
```bash
# Windows
dir logs\sync_*.log /O-D /B | findstr /n "^" | findstr "^1:" > temp.txt && set /p latest=<temp.txt && type %latest:~2%

# Linux/Mac
tail -f logs/$(ls -t logs/sync_*.log | head -1)
```

**Search for errors:**
```bash
# Windows
findstr /i "error" logs\sync_*.log

# Linux/Mac
grep -i error logs/sync_*.log
```

---

## Data Flow & Architecture

### High-Level Architecture

```
┌─────────────────┐
│   Bubble.io     │
│   Database      │
│   (81 tables)   │
└────────┬────────┘
         │
         │ 1. Fetch via REST API
         │    (cursor-based pagination)
         ↓
┌─────────────────┐
│  Python Script  │
│  ─────────────  │
│  • Fetch data   │
│  • Transform    │
│  • Validate     │
│  • Log errors   │
└────────┬────────┘
         │
         │ 2. Upsert (batch)
         │    (on conflict: _id)
         ↓
┌─────────────────┐
│   Supabase      │
│   PostgreSQL    │
│   (81 tables)   │
└─────────────────┘
```

### Data Flow Steps

#### 1. Extraction (Bubble → Script)

```
For each table:
  ├─ Initialize cursor = 0
  ├─ Loop while has_more_records:
  │   ├─ GET /api/1.1/obj/{table}?cursor={cursor}&limit=100
  │   ├─ Parse JSON response
  │   ├─ Extract records from response
  │   ├─ Update cursor from response
  │   └─ Wait RATE_LIMIT_DELAY seconds
  └─ Return all records
```

**Bubble API Response Format:**
```json
{
  "response": {
    "results": [...],  // Array of records
    "count": 100,      // Records in this response
    "remaining": 754,  // Records left to fetch
    "cursor": 100      // Next cursor position
  }
}
```

#### 2. Transformation (Script Processing)

```python
For each record:
  ├─ Handle photo URLs (add https:// protocol)
  ├─ Convert arrays/objects to JSONB
  ├─ Parse price fields (remove $, commas)
  ├─ Convert dates to ISO format
  ├─ Handle boolean conversions
  ├─ Map field names (if needed)
  └─ Validate required fields
```

**Common Transformations:**

| Bubble Type | Transform | PostgreSQL Type |
|-------------|-----------|-----------------|
| `//s3.amazonaws...` | Add `https:` | `text` |
| `["id1", "id2"]` | Convert to JSONB | `jsonb` |
| `$1,234.56` | Parse to `1234.56` | `numeric` |
| `yes`/`no` | Convert to boolean | `boolean` |
| Date string | Parse to ISO | `timestamp` |

#### 3. Loading (Script → Supabase)

```
For each batch of 100 records:
  ├─ Try batch upsert to Supabase
  ├─ If batch fails:
  │   ├─ Log batch error
  │   └─ Retry each record individually:
  │       ├─ Try upsert single record
  │       ├─ If succeeds: increment success count
  │       └─ If fails: log detailed error
  └─ Wait for next batch
```

**Upsert Logic:**
```sql
INSERT INTO table_name (fields...)
VALUES (values...)
ON CONFLICT (_id)
DO UPDATE SET
  field1 = EXCLUDED.field1,
  field2 = EXCLUDED.field2,
  ...
```

### Performance Characteristics

| Metric | Typical Value | Notes |
|--------|---------------|-------|
| Records/second | 20-30 | Varies by record size |
| Batch size | 100 | Configurable |
| API delay | 0.5s | Prevents rate limiting |
| Total sync time | 30-60 min | For ~70k records |
| Network bandwidth | ~5 MB/min | Depends on JSONB data |

---

## Error Handling

### Error Types

#### 1. Connection Errors
- **Bubble API timeout**: Retried with exponential backoff
- **Supabase connection lost**: Retried up to MAX_RETRIES
- **DNS resolution failed**: Check network connectivity

#### 2. Authentication Errors
- **Invalid Bubble API key**: Verify BUBBLE_API_KEY in .env
- **Invalid Supabase key**: Verify SUPABASE_SERVICE_KEY

#### 3. Data Transformation Errors
- **Type conversion failed**: Logged with original value
- **Missing required field**: Skipped with warning
- **Invalid format**: Attempted best-effort conversion

#### 4. Database Errors
- **Constraint violation**: Logged with constraint details
- **Foreign key error**: May need to sync dependent tables first
- **RLS policy denied**: Service key should bypass this

### Error Recovery Strategy

```
1. Batch Operation Fails
   ├─ Log batch error with table and record count
   ├─ Split batch into individual records
   └─ Retry each record individually
       ├─ Success: Continue
       └─ Failure: Log detailed error, continue to next

2. Network Error (Transient)
   ├─ Wait 1 second
   ├─ Retry (attempt 2 of 3)
   ├─ If still fails, wait 2 seconds
   ├─ Retry (attempt 3 of 3)
   └─ If still fails, log error and continue

3. Data Transform Error
   ├─ Log error with full context
   ├─ Skip problematic field
   └─ Continue with rest of record
```

### Error Log Analysis

**Find most common errors:**
```python
import json
from collections import Counter

with open('logs/sync_errors_20251106_103000.json', 'r') as f:
    errors = json.load(f)

# Count by error type
error_types = Counter(e['error_type'] for e in errors)
print(error_types)

# Count by table
error_tables = Counter(e['table'] for e in errors)
print(error_tables)
```

---

## Monitoring & Maintenance

### Daily Monitoring Checklist

- [ ] Check latest sync log for errors
- [ ] Verify sync completed successfully
- [ ] Review error count (should be minimal)
- [ ] Check Supabase record counts match expected
- [ ] Monitor log directory size

### Weekly Maintenance

- [ ] Review error logs for patterns
- [ ] Clean up logs older than 30 days
- [ ] Verify disk space availability
- [ ] Test sync on staging environment
- [ ] Review and update documentation

### Monthly Maintenance

- [ ] Archive important logs
- [ ] Review and optimize sync performance
- [ ] Update dependencies (`pip install --upgrade`)
- [ ] Rotate API keys if policy requires
- [ ] Audit data quality in Supabase

### Monitoring Queries

**Check Supabase table counts:**
```sql
SELECT
  schemaname,
  tablename,
  n_tup_ins as inserts,
  n_tup_upd as updates,
  n_tup_del as deletes
FROM pg_stat_user_tables
WHERE schemaname = 'public'
ORDER BY tablename;
```

**Find tables with most changes:**
```sql
SELECT
  tablename,
  n_tup_upd + n_tup_ins as total_changes
FROM pg_stat_user_tables
WHERE schemaname = 'public'
ORDER BY total_changes DESC
LIMIT 10;
```

**Compare record counts with Bubble:**
```sql
-- In Supabase
SELECT 'user' as table, COUNT(*) as count FROM "user"
UNION ALL
SELECT 'listing', COUNT(*) FROM listing
UNION ALL
SELECT 'proposal', COUNT(*) FROM proposal;
```

### Alerting

**Set up alerts for:**
- Sync duration exceeds 2 hours
- Error rate exceeds 5%
- Sync fails to complete
- Disk space below 500MB
- API rate limit errors

**Example alert script:**
```python
import json
from datetime import datetime, timedelta

# Load latest summary
with open('logs/sync_summary_latest.json', 'r') as f:
    summary = json.load(f)

# Check duration
if summary['duration_seconds'] > 7200:  # 2 hours
    send_alert(f"Sync took {summary['duration_seconds']/3600:.1f} hours")

# Check error rate
error_rate = summary['total_records_failed'] / summary['total_records_fetched']
if error_rate > 0.05:  # 5%
    send_alert(f"Error rate: {error_rate:.1%}")
```

---

## Troubleshooting

### Common Issues

#### Issue: "BUBBLE_API_KEY not set"
**Symptoms:** Script fails immediately with environment variable error
**Solution:**
1. Verify `.env` file exists
2. Check variable name is exactly `BUBBLE_API_KEY`
3. Ensure no quotes around the value
4. Try loading manually: `python -c "from dotenv import load_dotenv; load_dotenv(); import os; print(os.getenv('BUBBLE_API_KEY'))"`

#### Issue: "Connection timeout to Bubble API"
**Symptoms:** Sync hangs or times out during fetch
**Solution:**
1. Check internet connectivity
2. Verify BUBBLE_BASE_URL is correct
3. Test API manually: `curl -H "Authorization: Bearer YOUR_KEY" YOUR_BASE_URL/user?limit=1`
4. Increase timeout in script if network is slow

#### Issue: "Upsert failed: constraint violation"
**Symptoms:** Records fail to insert with unique constraint errors
**Solution:**
1. Check which constraint is failing in error log
2. Verify `_id` field is unique in Bubble data
3. Check for null values in required fields
4. Sync dependent tables first

#### Issue: "Permission denied (RLS)"
**Symptoms:** Database operations fail despite valid credentials
**Solution:**
1. Verify using `service_role` key (not `anon` key)
2. Check RLS policies on affected tables
3. Temporarily disable RLS for debugging: `ALTER TABLE table_name DISABLE ROW LEVEL SECURITY;`
4. Re-enable after sync: `ALTER TABLE table_name ENABLE ROW LEVEL SECURITY;`

#### Issue: "High error rate for specific table"
**Symptoms:** One table has many errors in error log
**Solution:**
1. Check error log for pattern: `grep "table_name" logs/sync_errors_*.json`
2. Review data types in Bubble vs Supabase schema
3. Add custom transformation for problematic fields
4. Sync that table individually for testing: `--tables table_name`

### Diagnostic Commands

**Test Bubble API:**
```bash
curl -H "Authorization: Bearer YOUR_BUBBLE_API_KEY" \
  "YOUR_BUBBLE_BASE_URL/user?limit=1"
```

**Test Supabase:**
```python
from supabase import create_client
client = create_client("YOUR_URL", "YOUR_KEY")
result = client.table('user').select('_id').limit(1).execute()
print(result)
```

**Check Python environment:**
```bash
python --version
pip list | findstr supabase
pip list | findstr requests
```

**Enable debug logging:**
Edit `bubble_to_supabase_sync.py`:
```python
logging.basicConfig(
    level=logging.DEBUG,  # Changed from INFO
    ...
)
```

---

## Development Guide

### Project Structure

```python
bubble_to_supabase_sync.py
├── ErrorLogger class
│   ├── log_error()       # Log individual errors
│   └── _write_to_file()  # Persist errors to JSON
│
├── SyncConfig class
│   ├── from_env()        # Load from .env file
│   └── validate()        # Ensure all required fields set
│
├── BubbleClient class
│   ├── fetch_table_page()      # Fetch single page
│   ├── fetch_all_records()     # Fetch with pagination
│   └── _handle_rate_limit()    # Rate limiting logic
│
├── SupabaseSync class
│   ├── upsert_batch()          # Batch upsert
│   ├── upsert_single()         # Single record upsert
│   └── get_table_count()       # Get row count
│
└── BubbleToSupabaseSync class (Main)
    ├── sync_table()            # Sync single table
    ├── sync_all_tables()       # Sync all tables
    ├── transform_record()      # Data transformation
    └── print_summary()         # Print final summary
```

### Adding Custom Transformations

To add custom field transformations:

```python
# In BubbleToSupabaseSync class
def transform_record(self, record: Dict[str, Any], table_name: str) -> Dict[str, Any]:
    transformed = {}

    for key, value in record.items():
        # Your custom transformation here
        if table_name == 'listing' and key == 'Price per month':
            # Custom price parsing
            if isinstance(value, str):
                value = float(value.replace('$', '').replace(',', ''))

        transformed[key] = value

    return transformed
```

### Adding New Tables

To add new tables to sync:

```python
# Add to ALL_TABLES list in the script
ALL_TABLES = [
    'user',
    'listing',
    'your_new_table',  # Add here
    ...
]
```

### Testing

**Unit test example:**
```python
import unittest
from bubble_to_supabase_sync import BubbleToSupabaseSync

class TestTransformations(unittest.TestCase):
    def setUp(self):
        self.sync = BubbleToSupabaseSync(config)

    def test_price_transformation(self):
        record = {'Price': '$1,234.56'}
        result = self.sync.transform_record(record, 'listing')
        self.assertEqual(result['Price'], 1234.56)

    def test_photo_url_transformation(self):
        record = {'Photo': '//s3.amazonaws.com/image.jpg'}
        result = self.sync.transform_record(record, 'listing')
        self.assertTrue(result['Photo'].startswith('https://'))
```

**Run tests:**
```bash
python -m unittest test_sync.py
```

### Code Style

Follow PEP 8 guidelines:
- 4 spaces for indentation
- Max line length: 100 characters
- Use type hints where possible
- Add docstrings to all functions

**Example:**
```python
def sync_table(
    self,
    table_name: str,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Sync a single table from Bubble to Supabase.

    Args:
        table_name: Name of the Bubble table to sync
        dry_run: If True, fetch but don't write to database

    Returns:
        Dictionary with sync statistics

    Raises:
        ValueError: If table_name is invalid
        ConnectionError: If API request fails
    """
    ...
```

---

## Security Best Practices

### Credential Management

**DO:**
- Store credentials in `.env` file (git-ignored)
- Use environment variables in production
- Rotate keys regularly (quarterly)
- Use service role key for Supabase (bypasses RLS)
- Keep `.env` file readable only by owner: `chmod 600 .env`

**DON'T:**
- Commit `.env` files to version control
- Share credentials via email or chat
- Hardcode credentials in scripts
- Use personal API keys (use service accounts)
- Leave credentials in log files

### API Key Permissions

**Bubble API Key:**
- Read-only access is sufficient
- Create a separate key for this sync (easier to rotate)
- Monitor usage in Bubble dashboard

**Supabase Service Key:**
- Full database access (be careful!)
- Only use on secure servers
- Never expose in client-side code
- Consider IP whitelisting if available

### Network Security

**Recommended practices:**
- Run sync from trusted networks only
- Use VPN for sensitive data transfers
- Enable SSL/TLS for all connections (already configured)
- Monitor for unusual API activity
- Use firewall rules to restrict outbound connections

### Data Privacy

**Compliance considerations:**
- Ensure Bubble data export is authorized
- Check GDPR/privacy requirements before syncing PII
- Encrypt data at rest (Supabase does this by default)
- Implement data retention policies
- Audit who has access to sync logs

### Audit Trail

Keep records of:
- When syncs run (timestamps in logs)
- Who triggered manual syncs (user logs)
- What data was transferred (summary files)
- Any errors or security events
- Changes to configuration

---

## Performance Optimization

### Current Performance

**Baseline metrics** (as of v2.0.0):
- 71,155 records in ~45 minutes
- Average: ~26 records/second
- 81 tables processed sequentially

### Optimization Strategies

#### 1. Increase Batch Size

```env
# In .env file
BATCH_SIZE=500  # Increased from 100
```

**Pros:**
- Fewer API calls
- Better throughput

**Cons:**
- Larger memory usage
- Harder to pinpoint errors

**Recommended:** Start with 200, increase if stable

#### 2. Reduce Rate Limit Delay

```env
# In .env file
RATE_LIMIT_DELAY=0.1  # Reduced from 0.5
```

**Pros:**
- Faster sync completion

**Cons:**
- May hit rate limits
- Could stress APIs

**Recommended:** Test with small table first

#### 3. Parallel Table Processing

```python
from concurrent.futures import ThreadPoolExecutor

def sync_tables_parallel(tables, max_workers=4):
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(sync_table, table) for table in tables]
        results = [f.result() for f in futures]
    return results
```

**Pros:**
- Significant speedup (4x with 4 workers)
- Better resource utilization

**Cons:**
- More complex error handling
- Higher resource usage

**Recommended:** Use for large syncs with monitoring

#### 4. Database Connection Pooling

Already implemented in Supabase client, but ensure:
- Use persistent connections
- Reuse clients across tables
- Close connections properly

#### 5. Compression

For large JSONB fields:
```python
import gzip
import json

def compress_jsonb(data):
    json_str = json.dumps(data)
    compressed = gzip.compress(json_str.encode())
    return compressed
```

**Note:** PostgreSQL JSONB already has efficient storage

### Monitoring Performance

**Measure sync time:**
```python
import time

start = time.time()
sync.sync_all_tables()
duration = time.time() - start
print(f"Sync completed in {duration:.2f} seconds")
```

**Profile bottlenecks:**
```python
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()

sync.sync_all_tables()

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(20)  # Top 20 slowest functions
```

### Performance Benchmarks

Expected performance after optimizations:

| Configuration | Records/sec | Total Time (70k records) |
|---------------|-------------|--------------------------|
| Default (batch=100, delay=0.5s) | 26 | 45 min |
| Optimized (batch=200, delay=0.2s) | 55 | 21 min |
| Parallel (4 workers, batch=200) | 180 | 6.5 min |

---

## Appendix

### Changelog

**v2.0.0 (2025-11-06)**
- Reorganized project structure
- Moved logs to `logs/` directory
- Archived old files to `dump/` directory
- Updated .gitignore for new structure
- Created comprehensive documentation
- Added automatic logs directory creation

**v1.0.0 (2025-11-04)**
- Initial release
- Support for 81 Bubble tables
- Pagination handling
- Upsert logic with deduplication
- Error recovery and logging
- Configurable sync options

### Glossary

- **ETL**: Extract, Transform, Load - data pipeline process
- **Upsert**: Insert or update - SQL operation
- **RLS**: Row Level Security - Supabase security feature
- **JSONB**: JSON Binary - PostgreSQL data type
- **Cursor**: Pagination marker in Bubble API
- **Service Role Key**: Admin-level Supabase API key
- **Dry Run**: Test mode without database writes

### Support & Contact

For issues, questions, or contributions:
1. Check this documentation
2. Review troubleshooting section
3. Check log files for error details
4. Contact Split Lease development team

---

**End of Documentation**
