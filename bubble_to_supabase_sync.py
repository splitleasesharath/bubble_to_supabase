#!/usr/bin/env python3
"""
Bubble to Supabase Data Synchronization Script
==============================================

This script automates the process of fetching data from Bubble.io API
and syncing it to Supabase PostgreSQL database.

Features:
- Pagination handling for large datasets
- Incremental updates (upsert logic based on _id)
- JSONB conversion for complex fields
- Error handling and retry logic
- Progress logging
- Configurable table sync
- Deduplication using Bubble _id as primary key

Author: Split Lease Team
Date: 2025-11-04
"""

import os
import sys
import json
import time
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass
from urllib.parse import urlencode

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from supabase import create_client, Client
from dotenv import load_dotenv


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'sync_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class SyncConfig:
    """Configuration for the sync process"""
    bubble_api_key: str
    bubble_app_name: str
    bubble_base_url: str
    supabase_url: str
    supabase_service_key: str
    batch_size: int = 100
    rate_limit_delay: float = 0.5  # seconds between API calls
    max_retries: int = 3
    tables_to_sync: Optional[List[str]] = None  # None = sync all

    @classmethod
    def from_env(cls) -> 'SyncConfig':
        """Load configuration from environment variables"""
        load_dotenv()

        # Try to load from production env file if available
        env_file = os.path.join(
            os.path.dirname(__file__),
            '.env.production'
        )
        if os.path.exists(env_file):
            load_dotenv(env_file)

        return cls(
            bubble_api_key=os.getenv('BUBBLE_API_KEY', ''),
            bubble_app_name=os.getenv('BUBBLE_APP_NAME', 'upgradefromstr'),
            bubble_base_url=os.getenv(
                'BUBBLE_BASE_URL',
                'https://upgradefromstr.bubbleapps.io/version-live/api/1.1/obj'
            ),
            supabase_url=os.getenv('SUPABASE_URL', ''),
            supabase_service_key=os.getenv('SUPABASE_SERVICE_KEY', ''),
            batch_size=int(os.getenv('BATCH_SIZE', '100')),
            rate_limit_delay=float(os.getenv('RATE_LIMIT_DELAY', '0.5')),
            max_retries=int(os.getenv('MAX_RETRIES', '3'))
        )


class BubbleAPIClient:
    """Client for interacting with Bubble.io API"""

    def __init__(self, config: SyncConfig):
        self.config = config
        self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        """Create a requests session with retry logic"""
        session = requests.Session()
        retry_strategy = Retry(
            total=self.config.max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def get_table_data(
        self,
        table_name: str,
        cursor: int = 0,
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        Fetch data from a Bubble table with pagination

        Args:
            table_name: Name of the Bubble data type (e.g., 'user', 'listing')
            cursor: Pagination cursor (0-based)
            limit: Number of records per page

        Returns:
            Dict containing 'response' (records) and 'remaining' count
        """
        url = f"{self.config.bubble_base_url}/{table_name}"
        params = {
            'cursor': cursor,
            'limit': limit
        }
        headers = {
            'Authorization': f'Bearer {self.config.bubble_api_key}',
            'Content-Type': 'application/json'
        }

        try:
            logger.debug(f"Fetching {table_name} - cursor: {cursor}, limit: {limit}")
            response = self.session.get(url, params=params, headers=headers)
            response.raise_for_status()

            data = response.json()

            # Handle nested response structure for logging
            response_data = data.get('response', {})
            if isinstance(response_data, dict):
                record_count = len(response_data.get('results', []))
                remaining_count = response_data.get('remaining', 0)
            else:
                record_count = len(response_data) if isinstance(response_data, list) else 0
                remaining_count = data.get('remaining', 0)

            logger.debug(f"Received {record_count} records, {remaining_count} remaining")

            return data

        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching {table_name} at cursor {cursor}: {e}")
            raise

    def get_all_table_data(self, table_name: str) -> List[Dict[str, Any]]:
        """
        Fetch all data from a Bubble table using pagination

        Args:
            table_name: Name of the Bubble data type

        Returns:
            List of all records from the table
        """
        all_records = []
        cursor = 0

        logger.info(f"Starting fetch for table: {table_name}")

        while True:
            # Rate limiting
            time.sleep(self.config.rate_limit_delay)

            try:
                data = self.get_table_data(
                    table_name,
                    cursor=cursor,
                    limit=self.config.batch_size
                )

                # Handle nested response structure from Bubble API
                response_data = data.get('response', {})
                if isinstance(response_data, dict):
                    # New format: {'response': {'results': [...], 'count': ..., 'remaining': ...}}
                    records = response_data.get('results', [])
                    remaining = response_data.get('remaining', 0)
                else:
                    # Old format: {'response': [...], 'remaining': ...}
                    records = response_data if isinstance(response_data, list) else []
                    remaining = data.get('remaining', 0)

                if not records:
                    break

                all_records.extend(records)
                logger.info(f"{table_name}: Fetched {len(all_records)} records, "
                           f"{remaining} remaining")

                if remaining == 0:
                    break

                cursor += len(records)

            except Exception as e:
                logger.error(f"Error during pagination for {table_name}: {e}")
                break

        logger.info(f"Completed fetch for {table_name}: {len(all_records)} total records")
        return all_records


class SupabaseSync:
    """Handles syncing data to Supabase"""

    def __init__(self, config: SyncConfig):
        self.config = config
        self.client: Client = create_client(
            config.supabase_url,
            config.supabase_service_key
        )

    def transform_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform a Bubble record for Supabase insertion with comprehensive type conversion

        Handles:
        - Integer fields: Converts decimals/strings to integers (rounds decimals)
        - Numeric fields: Handles currency symbols, percentage signs
        - Boolean fields: Normalizes various truthy/falsy values
        - JSONB fields: Arrays and objects
        - URL fields: Fixes protocol-relative URLs (//cdn.com -> https://cdn.com)
        - Timestamp fields: ISO 8601 date strings
        - Text fields: Proper string conversion
        """
        # Validate input is a dictionary
        if not isinstance(record, dict):
            raise ValueError(f"Expected dict for record, got {type(record).__name__}: {record}")

        # Define field type mappings for the listing table
        # This can be extended to load from a config file for other tables
        INTEGER_FIELDS = {
            '# of nights available', '.Search Ranking', 'Features - Qty Bathrooms',
            'Features - Qty Bedrooms', 'Features - Qty Beds', 'Features - Qty Guests',
            'Features - SQFT Area', 'Features - SQFT of Room', 'Maximum Months',
            'Maximum Nights', 'Maximum Weeks', 'Metrics - Click Counter',
            'Minimum Months', 'Minimum Nights', 'Minimum Weeks',
            'weeks out to available', '💰Cleaning Cost / Maintenance Fee',
            '💰Damage Deposit', '💰Monthly Host Rate', '💰Price Override',
            '💰Unit Markup'
        }

        NUMERIC_FIELDS = {
            'ClicksToViewRatio', 'DesirabilityTimesReceptivity',
            'Standarized Minimum Nightly Price (Filter)',
            '💰Nightly Host Rate for 2 nights', '💰Nightly Host Rate for 3 nights',
            '💰Nightly Host Rate for 4 nights', '💰Nightly Host Rate for 5 nights',
            '💰Nightly Host Rate for 7 nights', '💰Weekly Host Rate'
        }

        BOOLEAN_FIELDS = {
            'Active', 'Approved', 'Complete', 'Default Extension Setting',
            'Default Listing', 'Features - Trial Periods Allowed', 'Showcase',
            'allow alternating roommates?', 'confirmedAvailability', 'is private?',
            'isForUsability', 'saw chatgpt suggestions?'
        }

        JSONB_FIELDS = {
            'AI Suggestions List', 'Clickers', 'Dates - Blocked',
            'Days Available (List of Days)', 'Days Not Available', 'Errors',
            'Features - Amenities In-Building', 'Features - Amenities In-Unit',
            'Features - House Rules', 'Features - Photos', 'Features - Safety',
            'Listing Curation', 'Location - Address', 'Location - Hoods (new)',
            'Location - slightly different address', 'Nights Available (List of Nights) ',
            'Nights Available (numbers)', 'Nights Not Available', 'Reviews',
            'Users that favorite', 'Viewers', 'users with permission'
        }

        TIMESTAMP_FIELDS = {
            'Created Date', 'Modified Date', 'Operator Last Updated AUT'
        }

        transformed = {}

        for key, value in record.items():
            # Skip None values - let database handle defaults
            if value is None:
                continue

            try:
                # Handle INTEGER fields
                if key in INTEGER_FIELDS:
                    if isinstance(value, (int, float)):
                        # Round floats to nearest integer
                        transformed[key] = int(round(value))
                    elif isinstance(value, str):
                        # Remove common non-numeric characters
                        cleaned = value.replace('$', '').replace(',', '').replace('%', '').strip()
                        if cleaned:
                            try:
                                transformed[key] = int(round(float(cleaned)))
                            except ValueError:
                                logger.warning(f"Could not convert '{key}' value '{value}' to integer, skipping")
                                continue
                    else:
                        transformed[key] = int(value)

                # Handle NUMERIC (decimal) fields
                elif key in NUMERIC_FIELDS or 'price' in key.lower() or 'rate' in key.lower():
                    if isinstance(value, (int, float)):
                        transformed[key] = float(value)
                    elif isinstance(value, str):
                        # Remove currency symbols, commas, percentage signs
                        cleaned = value.replace('$', '').replace(',', '').replace('%', '').strip()
                        if cleaned:
                            try:
                                transformed[key] = float(cleaned)
                            except ValueError:
                                # If it's a "Price number (for map)" field, keep as string
                                if 'Price number' in key:
                                    transformed[key] = value
                                else:
                                    logger.warning(f"Could not convert '{key}' value '{value}' to numeric, skipping")
                                    continue
                    else:
                        transformed[key] = float(value)

                # Handle BOOLEAN fields
                elif key in BOOLEAN_FIELDS:
                    if isinstance(value, bool):
                        transformed[key] = value
                    elif isinstance(value, str):
                        # Normalize string boolean values
                        transformed[key] = value.lower() in ('true', 'yes', '1', 'y')
                    elif isinstance(value, (int, float)):
                        transformed[key] = bool(value)
                    else:
                        transformed[key] = bool(value)

                # Handle JSONB fields (arrays and objects)
                elif key in JSONB_FIELDS or isinstance(value, (list, dict)):
                    if isinstance(value, (list, dict)):
                        transformed[key] = json.dumps(value) if value else None
                    elif isinstance(value, str):
                        # Already a JSON string, validate it
                        try:
                            json.loads(value)
                            transformed[key] = value
                        except json.JSONDecodeError:
                            # Not valid JSON, wrap as string array
                            transformed[key] = json.dumps([value])
                    else:
                        transformed[key] = json.dumps(value)

                # Handle TIMESTAMP fields
                elif key in TIMESTAMP_FIELDS:
                    if isinstance(value, str):
                        # Bubble sends ISO 8601 timestamps, Supabase handles these natively
                        transformed[key] = value
                    else:
                        transformed[key] = str(value)

                # Handle URL fields with protocol-relative URLs
                elif isinstance(value, str) and value.startswith('//'):
                    transformed[key] = f'https:{value}'

                # Handle regular TEXT fields
                else:
                    transformed[key] = value

            except Exception as e:
                logger.warning(f"Error transforming field '{key}' with value '{value}': {e}")
                # Skip problematic fields rather than failing the entire record
                continue

        return transformed

    def upsert_records(
        self,
        table_name: str,
        records: List[Dict[str, Any]],
        batch_size: int = 100
    ) -> Dict[str, int]:
        """
        Upsert records to Supabase table

        Uses Bubble's _id field as the primary key for deduplication

        Args:
            table_name: Target Supabase table name
            records: List of records to upsert
            batch_size: Number of records to upsert per batch

        Returns:
            Dict with success and error counts
        """
        results = {'success': 0, 'errors': 0}

        # Convert table name from Bubble format to Supabase format
        # e.g., 'bookings-stays' -> 'bookings_stays'
        supabase_table = table_name.replace('-', '_')

        logger.info(f"Starting upsert for {supabase_table}: {len(records)} records")

        # Process in batches
        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]
            transformed_batch = [self.transform_record(r) for r in batch]

            try:
                # Upsert using _id as the conflict resolution key
                response = self.client.table(supabase_table).upsert(
                    transformed_batch,
                    on_conflict='_id'
                ).execute()

                results['success'] += len(batch)
                logger.info(f"{supabase_table}: Batch {i//batch_size + 1} - "
                           f"{len(batch)} records upserted successfully")

            except Exception as e:
                results['errors'] += len(batch)
                logger.error(f"{supabase_table}: Batch {i//batch_size + 1} failed: {e}")

                # Try individual records if batch fails
                for record in transformed_batch:
                    try:
                        self.client.table(supabase_table).upsert(
                            record,
                            on_conflict='_id'
                        ).execute()
                        results['success'] += 1
                        results['errors'] -= 1
                    except Exception as e2:
                        logger.error(f"Record {record.get('_id', 'unknown')} failed: {e2}")

        logger.info(f"{supabase_table} upsert complete: "
                   f"{results['success']} success, {results['errors']} errors")
        return results

    def get_table_count(self, table_name: str) -> int:
        """Get current record count for a table"""
        try:
            response = self.client.table(table_name).select(
                '_id',
                count='exact'
            ).limit(1).execute()
            return response.count or 0
        except Exception as e:
            logger.error(f"Error getting count for {table_name}: {e}")
            return 0


class BubbleToSupabaseSync:
    """Main orchestrator for Bubble to Supabase synchronization"""

    # Default list of all 81 tables from Bubble
    ALL_TABLES = [
        'user', 'listing', 'proposal', 'bookings-stays', 'bookings-leases',
        'account_host', 'account_guest', 'listing-photo', 'paymentrecords',
        '_message', 'mainreview', 'housemanual', 'visit',
        'virtualmeetingschedulesandlinks', 'rentalapplication',
        'zat_geo_borough_toplevel', 'zat_geo_hood_mediumlevel',
        'zat_location', 'zat_aisuggestions', 'datacollection_searchlogging',
        'zat_features_amenities_in_unit', 'zat_features_house_rules',
        'num', 'housemanualphotos', 'remindersfromhousemanual',
        'narration', 'ratingdetail_reviews_', 'reviewslistingsexternal',
        # Add remaining 53 tables here as needed
    ]

    def __init__(self, config: SyncConfig):
        self.config = config
        self.bubble_client = BubbleAPIClient(config)
        self.supabase_sync = SupabaseSync(config)

    def sync_table(self, table_name: str) -> Dict[str, Any]:
        """
        Sync a single table from Bubble to Supabase

        Args:
            table_name: Name of the table to sync

        Returns:
            Dict with sync statistics
        """
        start_time = time.time()
        logger.info(f"=" * 60)
        logger.info(f"Starting sync for table: {table_name}")
        logger.info(f"=" * 60)

        # Get current Supabase count
        supabase_table = table_name.replace('-', '_')
        before_count = self.supabase_sync.get_table_count(supabase_table)
        logger.info(f"Current {supabase_table} records in Supabase: {before_count}")

        # Fetch data from Bubble
        try:
            records = self.bubble_client.get_all_table_data(table_name)
        except Exception as e:
            logger.error(f"Failed to fetch data from Bubble for {table_name}: {e}")
            return {
                'table': table_name,
                'status': 'error',
                'error': str(e),
                'duration': time.time() - start_time
            }

        if not records:
            logger.warning(f"No records fetched from Bubble for {table_name}")
            return {
                'table': table_name,
                'status': 'empty',
                'records_fetched': 0,
                'duration': time.time() - start_time
            }

        # Upsert to Supabase
        results = self.supabase_sync.upsert_records(
            table_name,
            records,
            batch_size=self.config.batch_size
        )

        # Get final count
        after_count = self.supabase_sync.get_table_count(supabase_table)

        duration = time.time() - start_time

        summary = {
            'table': table_name,
            'status': 'success' if results['errors'] == 0 else 'partial',
            'records_fetched': len(records),
            'records_inserted': results['success'],
            'records_failed': results['errors'],
            'before_count': before_count,
            'after_count': after_count,
            'net_change': after_count - before_count,
            'duration': duration
        }

        logger.info(f"Table sync summary for {table_name}:")
        logger.info(f"  - Fetched from Bubble: {summary['records_fetched']}")
        logger.info(f"  - Inserted/Updated: {summary['records_inserted']}")
        logger.info(f"  - Failed: {summary['records_failed']}")
        logger.info(f"  - Before count: {summary['before_count']}")
        logger.info(f"  - After count: {summary['after_count']}")
        logger.info(f"  - Net change: {summary['net_change']}")
        logger.info(f"  - Duration: {duration:.2f}s")
        logger.info(f"=" * 60)

        return summary

    def sync_all_tables(self, tables: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Sync multiple tables from Bubble to Supabase

        Args:
            tables: List of table names to sync (None = sync all)

        Returns:
            Dict with overall sync statistics
        """
        start_time = time.time()
        tables_to_sync = tables or self.config.tables_to_sync or self.ALL_TABLES

        logger.info("=" * 80)
        logger.info("BUBBLE TO SUPABASE SYNCHRONIZATION STARTING")
        logger.info(f"Tables to sync: {len(tables_to_sync)}")
        logger.info(f"Timestamp: {datetime.now().isoformat()}")
        logger.info("=" * 80)

        results = []
        for table in tables_to_sync:
            try:
                result = self.sync_table(table)
                results.append(result)
            except Exception as e:
                logger.error(f"Unexpected error syncing {table}: {e}")
                results.append({
                    'table': table,
                    'status': 'error',
                    'error': str(e)
                })

        # Calculate overall statistics
        total_duration = time.time() - start_time
        summary = {
            'start_time': datetime.fromtimestamp(start_time).isoformat(),
            'end_time': datetime.now().isoformat(),
            'duration': total_duration,
            'tables_synced': len(results),
            'successful_tables': len([r for r in results if r['status'] == 'success']),
            'partial_tables': len([r for r in results if r['status'] == 'partial']),
            'failed_tables': len([r for r in results if r['status'] == 'error']),
            'total_records_fetched': sum(r.get('records_fetched', 0) for r in results),
            'total_records_inserted': sum(r.get('records_inserted', 0) for r in results),
            'total_records_failed': sum(r.get('records_failed', 0) for r in results),
            'table_results': results
        }

        logger.info("=" * 80)
        logger.info("SYNCHRONIZATION COMPLETE")
        logger.info(f"Duration: {total_duration:.2f}s")
        logger.info(f"Tables synced: {summary['tables_synced']}")
        logger.info(f"  - Successful: {summary['successful_tables']}")
        logger.info(f"  - Partial: {summary['partial_tables']}")
        logger.info(f"  - Failed: {summary['failed_tables']}")
        logger.info(f"Total records fetched: {summary['total_records_fetched']}")
        logger.info(f"Total records inserted: {summary['total_records_inserted']}")
        logger.info(f"Total records failed: {summary['total_records_failed']}")
        logger.info("=" * 80)

        # Save summary to JSON file
        summary_file = f"sync_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
        logger.info(f"Detailed summary saved to: {summary_file}")

        return summary


def main():
    """Main entry point for the sync script"""
    import argparse

    parser = argparse.ArgumentParser(
        description='Sync data from Bubble.io to Supabase'
    )
    parser.add_argument(
        '--tables',
        nargs='+',
        help='Specific tables to sync (default: all tables)'
    )
    parser.add_argument(
        '--config',
        help='Path to .env configuration file'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Fetch data but do not write to Supabase'
    )

    args = parser.parse_args()

    # Load configuration
    if args.config:
        load_dotenv(args.config)

    config = SyncConfig.from_env()

    # Validate configuration
    if not config.bubble_api_key:
        logger.error("BUBBLE_API_KEY not set in environment")
        sys.exit(1)
    if not config.supabase_url:
        logger.error("SUPABASE_URL not set in environment")
        sys.exit(1)
    if not config.supabase_service_key:
        logger.error("SUPABASE_SERVICE_KEY not set in environment")
        sys.exit(1)

    # Create sync instance
    sync = BubbleToSupabaseSync(config)

    # Run sync
    try:
        if args.dry_run:
            logger.info("DRY RUN MODE - No data will be written to Supabase")
            # Just fetch data for the first table to test
            test_table = args.tables[0] if args.tables else 'user'
            records = sync.bubble_client.get_all_table_data(test_table)
            logger.info(f"Fetched {len(records)} records from {test_table}")
            logger.info("Sample record:")
            if records:
                logger.info(json.dumps(records[0], indent=2))
        else:
            summary = sync.sync_all_tables(args.tables)

            # Exit with error code if any tables failed
            if summary['failed_tables'] > 0:
                sys.exit(1)

    except KeyboardInterrupt:
        logger.info("Sync interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Sync failed with error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
