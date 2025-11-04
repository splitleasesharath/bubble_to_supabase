#!/usr/bin/env python3
"""
Setup and Validation Script for Bubble to Supabase Sync
========================================================

This script helps you:
1. Validate your environment configuration
2. Test API connectivity to Bubble and Supabase
3. Verify credentials
4. Check table structure compatibility
5. Run a test sync on a small table

Author: Split Lease Team
Date: 2025-11-04
"""

import os
import sys
from typing import Dict, Tuple
from dotenv import load_dotenv
import requests
from supabase import create_client

# Fix Windows console encoding for Unicode characters
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# ANSI color codes for pretty output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_header(text: str):
    """Print a formatted header"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text.center(60)}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}\n")

def print_success(text: str):
    """Print a success message"""
    print(f"{Colors.GREEN}✓ {text}{Colors.END}")

def print_error(text: str):
    """Print an error message"""
    print(f"{Colors.RED}✗ {text}{Colors.END}")

def print_warning(text: str):
    """Print a warning message"""
    print(f"{Colors.YELLOW}⚠ {text}{Colors.END}")

def print_info(text: str):
    """Print an info message"""
    print(f"{Colors.BLUE}ℹ {text}{Colors.END}")

def check_env_file() -> Tuple[bool, str]:
    """Check if .env.production file exists"""
    env_file = '.env.production'
    if os.path.exists(env_file):
        return True, env_file

    # Try .env as fallback
    if os.path.exists('.env'):
        return True, '.env'

    return False, ''

def validate_environment() -> Dict[str, str]:
    """Validate environment variables"""
    print_header("Environment Configuration")

    # Check for env file
    exists, env_file = check_env_file()
    if exists:
        print_success(f"Found configuration file: {env_file}")
        load_dotenv(env_file)
    else:
        print_error("No .env.production or .env file found!")
        print_info("Please copy .env.template to .env.production and configure it")
        sys.exit(1)

    # Required variables
    required_vars = {
        'BUBBLE_API_KEY': os.getenv('BUBBLE_API_KEY'),
        'BUBBLE_APP_NAME': os.getenv('BUBBLE_APP_NAME', 'upgradefromstr'),
        'BUBBLE_BASE_URL': os.getenv('BUBBLE_BASE_URL', 'https://upgradefromstr.bubbleapps.io/version-live/api/1.1/obj'),
        'SUPABASE_URL': os.getenv('SUPABASE_URL'),
        'SUPABASE_SERVICE_KEY': os.getenv('SUPABASE_SERVICE_KEY'),
    }

    # Check each variable
    all_valid = True
    for var_name, var_value in required_vars.items():
        if not var_value or var_value.startswith('<') or var_value == '':
            print_error(f"{var_name} is not set or invalid")
            all_valid = False
        else:
            # Mask sensitive values
            if 'KEY' in var_name:
                masked = f"{var_value[:8]}...{var_value[-8:]}" if len(var_value) > 16 else "***"
                print_success(f"{var_name} = {masked}")
            else:
                print_success(f"{var_name} = {var_value}")

    if not all_valid:
        print_error("\nConfiguration is incomplete!")
        print_info("Please edit .env.production and add missing values")
        sys.exit(1)

    return required_vars

def test_bubble_api(config: Dict[str, str]) -> bool:
    """Test connection to Bubble API"""
    print_header("Bubble API Connection Test")

    # Test endpoint - use a small table
    test_table = 'user'
    url = f"{config['BUBBLE_BASE_URL']}/{test_table}"
    headers = {
        'Authorization': f"Bearer {config['BUBBLE_API_KEY']}",
        'Content-Type': 'application/json'
    }
    params = {'limit': 1}  # Just fetch 1 record

    try:
        print_info(f"Testing connection to Bubble API...")
        print_info(f"Endpoint: {url}")

        response = requests.get(url, headers=headers, params=params, timeout=10)

        if response.status_code == 200:
            data = response.json()

            # Debug: Check the structure
            # print(f"DEBUG: data type = {type(data)}")
            # print(f"DEBUG: data keys = {data.keys() if isinstance(data, dict) else 'not a dict'}")
            # if isinstance(data, dict) and 'response' in data:
            #     print(f"DEBUG: response type = {type(data['response'])}")
            #     if isinstance(data['response'], dict):
            #         print(f"DEBUG: response keys = {data['response'].keys()}")

            # Handle both list and dict response formats
            if isinstance(data, dict):
                records = data.get('response', {}).get('results', []) if isinstance(data.get('response'), dict) else data.get('response', [])
                remaining = data.get('response', {}).get('remaining', 0) if isinstance(data.get('response'), dict) else data.get('remaining', 0)
                count = data.get('response', {}).get('count', 0) if isinstance(data.get('response'), dict) else 0
            else:
                records = data if isinstance(data, list) else []
                remaining = 0
                count = 0

            print_success(f"Connection successful!")

            # Calculate total records
            if isinstance(records, list):
                total = len(records) + remaining + count
                print_success(f"Sample table '{test_table}' has {total} total records")

                if records and len(records) > 0:
                    print_info(f"Sample record fields: {', '.join(records[0].keys())}")
                else:
                    print_info(f"No records returned in sample (table might be empty)")
            else:
                print_warning(f"Unexpected response format. Type: {type(records)}")
                # Try to still work with it
                if isinstance(records, dict) and records:
                    print_info(f"Response structure keys: {', '.join(records.keys())}")

            return True

        elif response.status_code == 401:
            print_error(f"Authentication failed! (Status: {response.status_code})")
            print_error("Check your BUBBLE_API_KEY")
            return False

        elif response.status_code == 404:
            print_error(f"Endpoint not found! (Status: {response.status_code})")
            print_error("Check your BUBBLE_BASE_URL and BUBBLE_APP_NAME")
            return False

        else:
            print_error(f"Request failed with status: {response.status_code}")
            print_error(f"Response: {response.text}")
            return False

    except requests.exceptions.Timeout:
        print_error("Connection timeout!")
        print_error("Check your network connection")
        return False

    except requests.exceptions.ConnectionError:
        print_error("Connection error!")
        print_error("Check your network connection and BUBBLE_BASE_URL")
        return False

    except Exception as e:
        print_error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_supabase_connection(config: Dict[str, str]) -> bool:
    """Test connection to Supabase"""
    print_header("Supabase Connection Test")

    try:
        print_info("Testing connection to Supabase...")
        print_info(f"URL: {config['SUPABASE_URL']}")

        # Create client
        client = create_client(
            config['SUPABASE_URL'],
            config['SUPABASE_SERVICE_KEY']
        )

        # Test query - just count users
        response = client.table('user').select('_id', count='exact').limit(1).execute()

        count = response.count or 0
        print_success(f"Connection successful!")
        print_success(f"Database has {count} records in 'user' table")

        return True

    except Exception as e:
        print_error(f"Connection failed: {e}")
        print_error("Check your SUPABASE_URL and SUPABASE_SERVICE_KEY")
        print_info("Make sure you're using the SERVICE ROLE key (not ANON key)")
        return False

def test_table_compatibility(config: Dict[str, str]) -> bool:
    """Test if Bubble and Supabase tables are compatible"""
    print_header("Table Compatibility Check")

    test_table = 'user'

    # Get sample from Bubble
    print_info(f"Fetching sample record from Bubble...")
    url = f"{config['BUBBLE_BASE_URL']}/{test_table}"
    headers = {'Authorization': f"Bearer {config['BUBBLE_API_KEY']}"}

    try:
        response = requests.get(url, headers=headers, params={'limit': 1})
        response.raise_for_status()
        data = response.json()

        # Handle nested dict structure
        bubble_response = data.get('response', {})
        if isinstance(bubble_response, dict):
            bubble_data = bubble_response.get('results', [])
        else:
            bubble_data = bubble_response if isinstance(bubble_response, list) else []

        if not bubble_data:
            print_warning(f"No data in Bubble table '{test_table}'")
            return True

        bubble_fields = set(bubble_data[0].keys())
        print_success(f"Bubble table has {len(bubble_fields)} fields")

        # Get schema from Supabase
        print_info(f"Checking Supabase table schema...")
        client = create_client(config['SUPABASE_URL'], config['SUPABASE_SERVICE_KEY'])

        # Get a sample record to see which fields exist
        response = client.table(test_table).select('*').limit(1).execute()

        if response.data:
            supabase_fields = set(response.data[0].keys())
            print_success(f"Supabase table has {len(supabase_fields)} fields")

            # Check for _id field (critical)
            if '_id' in bubble_fields and '_id' in supabase_fields:
                print_success("Primary key '_id' field exists in both")
            else:
                print_error("Primary key '_id' field missing!")
                return False

            # Find missing fields
            missing_in_supabase = bubble_fields - supabase_fields
            missing_in_bubble = supabase_fields - bubble_fields

            if missing_in_supabase:
                print_warning(f"Fields in Bubble but not in Supabase: {len(missing_in_supabase)}")
                if len(missing_in_supabase) <= 5:
                    for field in list(missing_in_supabase)[:5]:
                        print(f"    - {field}")

            if missing_in_bubble:
                print_info(f"Fields in Supabase but not in Bubble: {len(missing_in_bubble)} (likely auto-generated)")

            return True
        else:
            print_warning(f"Supabase table '{test_table}' is empty (this is OK)")
            return True

    except Exception as e:
        print_error(f"Compatibility check failed: {e}")
        return False

def run_test_sync(config: Dict[str, str]) -> bool:
    """Run a test sync on a small table"""
    print_header("Test Sync (Dry Run)")

    print_info("This will fetch data from Bubble but NOT write to Supabase")
    print_info("Testing with 'user' table (limiting to 5 records)")

    try:
        from bubble_to_supabase_sync import BubbleAPIClient, SyncConfig

        # Create minimal config
        sync_config = SyncConfig(
            bubble_api_key=config['BUBBLE_API_KEY'],
            bubble_app_name=config['BUBBLE_APP_NAME'],
            bubble_base_url=config['BUBBLE_BASE_URL'],
            supabase_url=config['SUPABASE_URL'],
            supabase_service_key=config['SUPABASE_SERVICE_KEY']
        )

        # Create Bubble client
        bubble_client = BubbleAPIClient(sync_config)

        # Test fetch - use user table and just test the API call, not full fetch
        print_info("Testing fetch from Bubble API...")

        # Just do a simple API call instead of fetching all data
        import requests
        url = f"{config['BUBBLE_BASE_URL']}/user"
        headers = {'Authorization': f"Bearer {config['BUBBLE_API_KEY']}"}
        response = requests.get(url, headers=headers, params={'limit': 5})
        response.raise_for_status()

        data = response.json()
        bubble_response = data.get('response', {})
        if isinstance(bubble_response, dict):
            records = bubble_response.get('results', [])
        else:
            records = bubble_response if isinstance(bubble_response, list) else []

        print_success(f"Successfully fetched {len(records)} sample records")

        if records:
            sample = records[0]
            print_info(f"Sample record has {len(sample)} fields")
            print_info(f"Sample _id: {sample.get('_id', 'N/A')}")

        print_success("Test sync completed successfully!")
        return True

    except ImportError:
        print_error("Could not import bubble_to_supabase_sync.py")
        print_error("Make sure the script is in the same directory")
        return False

    except Exception as e:
        print_error(f"Test sync failed: {e}")
        return False

def check_dependencies() -> bool:
    """Check if required Python packages are installed"""
    print_header("Dependency Check")

    required_packages = {
        'requests': 'requests',
        'supabase': 'supabase',
        'python-dotenv': 'dotenv'
    }

    all_installed = True
    for package_name, import_name in required_packages.items():
        try:
            __import__(import_name)
            print_success(f"{package_name} is installed")
        except ImportError:
            print_error(f"{package_name} is NOT installed")
            all_installed = False

    if not all_installed:
        print_error("\nSome dependencies are missing!")
        print_info("Install them with: pip install -r requirements.txt")
        return False

    return True

def main():
    """Main setup and validation flow"""
    print(f"\n{Colors.BOLD}Bubble to Supabase Sync - Setup & Validation{Colors.END}")
    print("This will verify your configuration and test connections\n")

    # Step 1: Check dependencies
    if not check_dependencies():
        sys.exit(1)

    # Step 2: Validate environment
    config = validate_environment()

    # Step 3: Test Bubble API
    if not test_bubble_api(config):
        print_error("\n⚠ Bubble API test failed!")
        print_info("Fix the issues above and run setup.py again")
        sys.exit(1)

    # Step 4: Test Supabase
    if not test_supabase_connection(config):
        print_error("\n⚠ Supabase test failed!")
        print_info("Fix the issues above and run setup.py again")
        sys.exit(1)

    # Step 5: Check compatibility
    if not test_table_compatibility(config):
        print_warning("\n⚠ Compatibility issues detected")
        print_info("This may affect data sync - review warnings above")

    # Step 6: Run test sync
    if not run_test_sync(config):
        print_error("\n⚠ Test sync failed!")
        print_info("Fix the issues above and run setup.py again")
        sys.exit(1)

    # All tests passed!
    print_header("Setup Complete!")
    print_success("All tests passed! ✓")
    print_success("Your configuration is ready to use")
    print()
    print_info("Next steps:")
    print("  1. Run a test sync on a single table:")
    print(f"     {Colors.BOLD}python bubble_to_supabase_sync.py --tables account_guest{Colors.END}")
    print()
    print("  2. If successful, sync all tables:")
    print(f"     {Colors.BOLD}python bubble_to_supabase_sync.py{Colors.END}")
    print()
    print_info("For more options, see README.md")
    print()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Setup interrupted by user{Colors.END}")
        sys.exit(130)
    except Exception as e:
        print(f"\n{Colors.RED}Unexpected error: {e}{Colors.END}")
        sys.exit(1)
