"""
Local testing script for Sentinel Activity Maps function.
Tests components without requiring Azure resources.
"""
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_config_loader():
    """Test configuration loading from sources.yaml"""
    print("=" * 60)
    print("Testing Configuration Loader")
    print("=" * 60)
    
    try:
        from shared.config_loader import ConfigLoader
        
        config = ConfigLoader()
        all_sources = config.get_all_sources()
        enabled_sources = config.get_enabled_sources()
        
        print(f"✓ Loaded {len(all_sources)} total sources")
        print(f"✓ {len(enabled_sources)} sources are enabled\n")
        
        for src in all_sources:
            status = "ENABLED" if src.enabled else "DISABLED"
            print(f"  [{status}] {src.id}")
            print(f"    Name: {src.name}")
            print(f"    Refresh Interval: {src.refresh_interval_seconds}s")
            print(f"    Output File: {src.output_filename}")
            print(f"    Incremental: {src.incremental}")
            print(f"    Query Preview: {src.kql_query[:100]}...")
            print()
        
        # Test getting specific source
        first_source = enabled_sources[0]
        retrieved = config.get_source_by_id(first_source.id)
        assert retrieved.id == first_source.id
        print(f"✓ Successfully retrieved source by ID: {retrieved.id}\n")
        
        # Test query generation
        query = first_source.get_query()
        print(f"✓ Generated KQL query with default time window")
        print(f"  Query length: {len(query)} characters\n")
        
        return True
    except Exception as e:
        print(f"✗ Configuration loader test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_tsv_writer():
    """Test TSV formatting and parsing"""
    print("=" * 60)
    print("Testing TSV Writer")
    print("=" * 60)
    
    try:
        from shared.tsv_writer import TSVWriter
        from datetime import datetime
        
        # Test data
        test_data = [
            {
                'TimeGenerated': datetime(2026, 2, 7, 12, 30, 0),
                'UserPrincipalName': 'alice@contoso.com',
                'IPAddress': '192.168.1.100',
                'Country': 'United States',
                'ResultType': '50126'
            },
            {
                'TimeGenerated': datetime(2026, 2, 7, 12, 35, 0),
                'UserPrincipalName': 'bob@contoso.com',
                'IPAddress': '10.0.0.50',
                'Country': 'Canada',
                'ResultType': '50053'
            }
        ]
        
        # Test writing
        tsv_content = TSVWriter.write_tsv(test_data)
        print(f"✓ Generated TSV content ({len(tsv_content)} bytes)\n")
        print("Preview:")
        print("-" * 60)
        print(tsv_content[:400])
        print("-" * 60)
        print()
        
        # Test parsing
        parsed_data = TSVWriter.parse_tsv(tsv_content)
        print(f"✓ Parsed TSV back to {len(parsed_data)} rows")
        assert len(parsed_data) == len(test_data)
        print(f"✓ Row count matches original\n")
        
        # Test with custom columns
        custom_columns = ['UserPrincipalName', 'IPAddress', 'Country']
        tsv_custom = TSVWriter.write_tsv(test_data, custom_columns)
        print(f"✓ Generated TSV with custom column order")
        print(f"  Columns: {', '.join(custom_columns)}\n")
        
        # Test value formatting
        test_value = TSVWriter.format_value(None)
        assert test_value == ""
        print(f"✓ None values formatted correctly")
        
        test_value = TSVWriter.format_value("text\twith\ttabs")
        assert '\t' not in test_value
        print(f"✓ Tab characters escaped correctly\n")
        
        return True
    except Exception as e:
        print(f"✗ TSV writer test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_refresh_policy():
    """Test refresh policy (without actual blob storage)"""
    print("=" * 60)
    print("Testing Refresh Policy")
    print("=" * 60)
    
    try:
        from shared.refresh_policy import RefreshPolicy
        
        # Test query hash computation
        test_query = "SigninLogs | where TimeGenerated >= ago(24h)"
        hash1 = RefreshPolicy.compute_query_hash(test_query)
        hash2 = RefreshPolicy.compute_query_hash(test_query)
        
        print(f"✓ Query hash computed: {hash1}")
        assert hash1 == hash2
        print(f"✓ Hash is deterministic (same query = same hash)\n")
        
        # Test different query produces different hash
        different_query = "SigninLogs | where TimeGenerated >= ago(48h)"
        hash3 = RefreshPolicy.compute_query_hash(different_query)
        assert hash3 != hash1
        print(f"✓ Different queries produce different hashes")
        print(f"  Original: {hash1}")
        print(f"  Modified: {hash3}\n")
        
        return True
    except Exception as e:
        print(f"✗ Refresh policy test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_imports():
    """Test that all modules can be imported"""
    print("=" * 60)
    print("Testing Module Imports")
    print("=" * 60)
    
    modules = [
        'shared.config_loader',
        'shared.log_analytics_client',
        'shared.blob_storage',
        'shared.tsv_writer',
        'shared.refresh_policy'
    ]
    
    success = True
    for module in modules:
        try:
            __import__(module)
            print(f"✓ {module}")
        except Exception as e:
            print(f"✗ {module}: {e}")
            success = False
    
    print()
    return success


def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("SENTINEL ACTIVITY MAPS - LOCAL TEST SUITE")
    print("=" * 60)
    print()
    
    results = []
    
    # Test imports first
    results.append(("Module Imports", test_imports()))
    
    # Test individual components
    results.append(("Configuration Loader", test_config_loader()))
    results.append(("TSV Writer", test_tsv_writer()))
    results.append(("Refresh Policy", test_refresh_policy()))
    
    # Summary
    print("=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")
    
    print()
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✅ All tests passed! Your function is ready for local development.")
        print("\nNext steps:")
        print("1. Run 'func start' to start the function locally")
        print("2. Test with: curl http://localhost:7071/api/health")
        return 0
    else:
        print("\n❌ Some tests failed. Please review the errors above.")
        return 1


if __name__ == "__main__":
    exit(main())
