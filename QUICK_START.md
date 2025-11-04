# Quick Start Guide

Get your Bubble to Supabase sync running in 5 minutes!

## Step 1: Install Dependencies (1 minute)

```bash
pip install -r requirements.txt
```

## Step 2: Configure Credentials (2 minutes)

1. Copy the template:
   ```bash
   copy .env.template .env.production
   ```

2. Get your Supabase Service Role Key:
   - Visit: https://supabase.com/dashboard/project/qcfifybkaddcoimjroca
   - Go to: Settings > API
   - Copy the **service_role** key (NOT the anon key!)

3. Edit `.env.production` and paste your key:
   ```bash
   SUPABASE_SERVICE_KEY=eyJhbGc...your-actual-key-here
   ```

   The other values should already be correct:
   - BUBBLE_API_KEY=677ca2fc4b13f1b4eb93b91132da0afe ✓
   - BUBBLE_APP_NAME=upgradefromstr ✓
   - SUPABASE_URL=https://qcfifybkaddcoimjroca.supabase.co ✓

## Step 3: Validate Setup (1 minute)

```bash
python setup.py
```

This will:
- ✓ Check your configuration
- ✓ Test Bubble API connection
- ✓ Test Supabase connection
- ✓ Run a test sync (dry run)

If all tests pass, you're ready to go! ✅

## Step 4: Run Your First Sync (1 minute)

Start with a small table:

```bash
python bubble_to_supabase_sync.py --tables account_guest
```

Expected output:
```
2025-11-04 10:30:00 - INFO - Starting sync for table: account_guest
2025-11-04 10:30:05 - INFO - account_guest: Fetched 652 records, 0 remaining
2025-11-04 10:30:10 - INFO - account_guest: Batch 1 - 100 records upserted successfully
...
2025-11-04 10:30:15 - INFO - Table sync summary for account_guest:
  - Fetched from Bubble: 652
  - Inserted/Updated: 652
  - Failed: 0
  ✓ Success!
```

## Step 5: Sync All Tables (30-45 minutes)

Once you're confident:

```bash
python bubble_to_supabase_sync.py
```

This will sync all 81 tables (~71,000 records) from Bubble to Supabase.

---

## Troubleshooting

### "SUPABASE_SERVICE_KEY not set"
➜ You didn't edit `.env.production` with your service role key
➜ Make sure you copied `.env.template` to `.env.production`
➜ Get the key from: https://supabase.com/dashboard/project/qcfifybkaddcoimjroca (Settings > API)

### "Authentication failed"
➜ You're using the ANON key instead of SERVICE ROLE key
➜ The service role key starts with `eyJhbGc...` and is much longer than the anon key

### "Connection timeout"
➜ Check your internet connection
➜ Make sure you can access: https://qcfifybkaddcoimjroca.supabase.co

### "Table not found"
➜ Make sure your Supabase database has all tables created
➜ Run the migration: `20251002110758_create_all_bubble_tables.sql`

---

## What's Next?

### Schedule Automatic Syncs

**Windows Task Scheduler:**
- Create a task that runs daily at 2 AM
- Program: `python`
- Arguments: `C:\path\to\bubble_to_supabase_sync.py`

**Or use Python scheduling:**
```bash
pip install schedule
```

Create `run_daily.py`:
```python
import schedule
import time
import os

def run_sync():
    os.system('python bubble_to_supabase_sync.py')

schedule.every().day.at("02:00").do(run_sync)

while True:
    schedule.run_pending()
    time.sleep(60)
```

Run it: `python run_daily.py`

### Monitor Your Syncs

Check the generated files:
- `sync_YYYYMMDD_HHMMSS.log` - Detailed logs
- `sync_summary_YYYYMMDD_HHMMSS.json` - Statistics

### Validate Your Data

```sql
-- Check record counts
SELECT COUNT(*) FROM user;
SELECT COUNT(*) FROM listing;
SELECT COUNT(*) FROM bookings_stays;

-- Verify data integrity
SELECT * FROM user LIMIT 10;
```

---

## Need Help?

1. Check `README.md` for detailed documentation
2. Review log files for error details
3. Run `python setup.py` to re-validate your setup
4. Contact the development team

---

**Estimated time for full setup: ~5 minutes**
**Estimated time for full sync: ~30-45 minutes (71,000 records)**
