"""
Azure Functions app for Sentinel Activity Maps.
HTTP-triggered function to refresh threat intelligence datasets.
Updated: February 2026 - Optimized for large datasets with 10-minute timeouts.
"""
import os
import logging
import json
import azure.functions as func
from datetime import datetime, timedelta
from shared.config_loader import ConfigLoader
from shared.log_analytics_client import LogAnalyticsClient
from shared.blob_storage import BlobStorageClient
from shared.tsv_writer import TSVWriter
from shared.refresh_policy import RefreshPolicy
from shared.geo_enrichment import GeoEnrichmentClient
from shared.file_age_checker import check_file_age, get_file_stats
from shared.key_vault_client import KeyVaultClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Azure Functions app
app = func.FunctionApp()


@app.route(route="refresh", methods=["GET", "POST"], auth_level=func.AuthLevel.ANONYMOUS)
def refresh(req: func.HttpRequest) -> func.HttpResponse:
    """
    HTTP-triggered function to refresh threat intelligence datasets.
    Event-driven with file-age-based caching - runs once per request.
    
    Query parameters:
        - source_id: Optional specific source to refresh (default: all enabled)
        - force: Optional flag to bypass file age check (default: false)
        - correlation_id: Optional correlation ID for logging
    
    Returns:
        200: Successfully refreshed or returned cached data
        500: Internal error
    """
    correlation_id = req.params.get('correlation_id', req.headers.get('X-Correlation-ID', 'none'))
    logger.info(f"[{correlation_id}] Refresh request received")
    
    # Parse parameters
    source_id = req.params.get('source_id')
    force = req.params.get('force', 'false').lower() == 'true'
    
    try:
        # Initialize clients
        config_loader = ConfigLoader()
        log_analytics = LogAnalyticsClient()
        blob_storage = BlobStorageClient()
        refresh_policy = RefreshPolicy(blob_storage)
        
        # Initialize Key Vault client if configured
        kv_client = None
        if config_loader.key_vault_name:
            try:
                kv_client = KeyVaultClient(config_loader.key_vault_name)
                logger.info(f"[{correlation_id}] Key Vault client initialized: {config_loader.key_vault_name}")
            except Exception as e:
                logger.warning(f"[{correlation_id}] Key Vault init failed, using env vars: {e}")
        
        # Determine which sources to refresh
        if source_id:
            sources = [config_loader.get_source_by_id(source_id)]
            logger.info(f"[{correlation_id}] Processing specific source: {source_id}")
        else:
            sources = config_loader.get_enabled_sources()
            logger.info(f"[{correlation_id}] Processing {len(sources)} enabled sources")
        
        if not sources:
            return func.HttpResponse(
                json.dumps({"message": "No sources configured", "status": "no_sources"}),
                status_code=200,
                mimetype="application/json"
            )
        
        # Track results
        results = []
        refreshed_count = 0
        cached_count = 0
        
        for source in sources:
            try:
                result = _refresh_source_with_cache(
                    source=source,
                    log_analytics=log_analytics,
                    blob_storage=blob_storage,
                    refresh_policy=refresh_policy,
                    kv_client=kv_client,
                    force=force,
                    correlation_id=correlation_id
                )
                results.append(result)
                
                if result['status'] == 'refreshed' or result['status'] == 'initial_load':
                    refreshed_count += 1
                elif result['status'] == 'cached':
                    cached_count += 1
            
            except Exception as e:
                logger.error(f"[{correlation_id}] Failed to process {source.id}: {e}", exc_info=True)
                results.append({
                    'source_id': source.id,
                    'status': 'error',
                    'message': str(e)
                })
        
        # Build response
        response_data = {
            'message': f"Processed {len(sources)} sources: {refreshed_count} refreshed, {cached_count} cached",
            'refreshed_count': refreshed_count,
            'cached_count': cached_count,
            'total_sources': len(sources),
            'results': results,
            'correlation_id': correlation_id
        }
        
        logger.info(f"[{correlation_id}] Request completed: {refreshed_count} refreshed, {cached_count} cached")
        
        return func.HttpResponse(
            json.dumps(response_data, default=str),
            status_code=200,
            mimetype="application/json",
            headers={
                'X-Correlation-ID': correlation_id,
                'X-Refreshed-Count': str(refreshed_count),
                'X-Cached-Count': str(cached_count)
            }
        )
    
    except Exception as e:
        logger.error(f"[{correlation_id}] Unhandled error: {e}", exc_info=True)
        return func.HttpResponse(
            json.dumps({
                'message': 'Internal server error',
                'error': str(e),
                'correlation_id': correlation_id
            }),
            status_code=500,
            mimetype="application/json"
        )


def _refresh_source_with_cache(source, log_analytics, blob_storage, refresh_policy, kv_client, force, correlation_id):
    """
    Refresh a single data source with file-age-based caching.
    
    Logic:
    - If file doesn't exist: Initial 15-day pull
    - If file exists and age < threshold: Return cached (skip refresh)
    - If file exists and age >= threshold: Incremental refresh
    - If force=true: Always refresh regardless of age
    
    Returns:
        Dictionary with refresh result including cache status
    """
    source_id = source.id
    logger.info(f"[{correlation_id}] Processing source: {source_id}")
    
    # Get blob client for TSV file
    tsv_blob_client = blob_storage.blob_service_client.get_blob_client(
        container="datasets",
        blob=source.output_filename
    )
    
    # Check file age
    needs_refresh, last_modified = check_file_age(
        tsv_blob_client,
        source.refresh_threshold_hours
    )
    
    file_stats = get_file_stats(tsv_blob_client)
    
    # Determine action
    if not file_stats['exists']:
        # Initial load - file doesn't exist
        logger.info(f"[{correlation_id}] Initial load for {source_id} (file doesn't exist)")
        action = 'initial_load'
    elif force:
        # Forced refresh
        logger.info(f"[{correlation_id}] Forced refresh for {source_id}")
        action = 'refresh'
    elif needs_refresh:
        # File is stale
        logger.info(f"[{correlation_id}] File aged out for {source_id} (age: {file_stats['age_hours']:.1f}h, threshold: {source.refresh_threshold_hours}h)")
        action = 'refresh'
    else:
        # File is fresh - return cached
        logger.info(f"[{correlation_id}] Using cached data for {source_id} (age: {file_stats['age_hours']:.1f}h, threshold: {source.refresh_threshold_hours}h)")
        return {
            'source_id': source_id,
            'status': 'cached',
            'message': 'Using cached data',
            'file_age_hours': round(file_stats['age_hours'], 2),
            'refresh_threshold_hours': source.refresh_threshold_hours,
            'last_modified': file_stats['last_modified'],
            'file_size_bytes': file_stats['size_bytes']
        }
    
    # Perform refresh (initial or incremental)
    try:
        # Calculate query timespan
        timespan, watermark = refresh_policy.get_query_timespan(
            source_id,
            source.query_time_window_hours,
            source.incremental_overlap_minutes,
            source.incremental and action != 'initial_load'  # Don't use incremental for initial load
        )
        
        # Execute query
        kql_query = source.get_query(int(timespan.total_seconds() / 3600))
        query_hash = refresh_policy.compute_query_hash(kql_query)
        
        logger.info(f"[{correlation_id}] Executing query for {source_id} ({action})")
        rows = log_analytics.execute_query(kql_query, timespan)
        
        # Write to temp file first (atomic replacement)
        temp_filename = f"{source.output_filename}.tmp"
        tsv_content = TSVWriter.write_tsv(rows, source.columns)
        blob_storage.write_tsv(temp_filename, tsv_content)
        
        logger.info(f"[{correlation_id}] Successfully queried {source_id}: {len(rows)} rows")
        
        result = {
            'source_id': source_id,
            'status': action,
            'row_count': len(rows),
            'output_file': source.output_filename,
            'refresh_threshold_hours': source.refresh_threshold_hours
        }
        
        # Auto-enrichment if enabled
        if source.auto_enrich_geo:
            try:
                logger.info(f"[{correlation_id}] Auto-enriching geo data for {source_id}")
                config_loader = ConfigLoader()
                
                # Initialize geo client with Key Vault support
                geo_client = GeoEnrichmentClient(
                    provider=config_loader.geo_provider,
                    key_vault_client=kv_client
                )
                
                # Read TSV from temp file
                tsv_content = blob_storage.read_tsv(temp_filename)
                headers, rows_data = geo_client.parse_tsv_with_geo(tsv_content)
                
                # Find IPs needing lookup
                ips_to_lookup = [row.get('ObservableValue', '') for row in rows_data 
                               if geo_client.needs_geo_lookup(row) and row.get('ObservableValue')]
                
                if ips_to_lookup:
                    # Batch lookup
                    geo_results = geo_client.batch_lookup(ips_to_lookup, max_workers=10)
                    
                    # Update rows with geo data
                    enriched_count = 0
                    full_geo_count = 0  # IPs with coordinates
                    country_only_count = 0  # IPs with country but no coordinates
                    
                    for row in rows_data:
                        ip = row.get('ObservableValue', '')
                        if ip in geo_results:
                            geo_data = geo_results[ip]
                            # Store geo data (lat/lon will be empty string if None)
                            row['Latitude'] = str(geo_data['latitude']) if geo_data.get('latitude') else ''
                            row['Longitude'] = str(geo_data['longitude']) if geo_data.get('longitude') else ''
                            row['Country'] = geo_data.get('country', '')
                            row['City'] = geo_data.get('city', '')
                            enriched_count += 1
                            
                            # Track detail level
                            if geo_data.get('latitude') and geo_data.get('longitude'):
                                full_geo_count += 1
                            else:
                                country_only_count += 1
                    
                    # Ensure geo columns in headers
                    for col in ['Latitude', 'Longitude', 'Country', 'City']:
                        if col not in headers:
                            headers.append(col)
                    
                    # Rebuild and save TSV to temp file
                    tsv_lines = ['\t'.join(headers)]
                    for row in rows_data:
                        values = [str(row.get(h, '')) for h in headers]
                        tsv_lines.append('\t'.join(values))
                    
                    updated_tsv = '\n'.join(tsv_lines)
                    blob_storage.write_tsv(temp_filename, updated_tsv)
                    
                    result['geo_enriched'] = enriched_count
                    result['geo_full'] = full_geo_count
                    result['geo_country_only'] = country_only_count
                    result['geo_no_match'] = len(ips_to_lookup) - len(geo_results)
                    logger.info(f"[{correlation_id}] Geo enrichment: {enriched_count} total ({full_geo_count} with coordinates, {country_only_count} country-only, {len(ips_to_lookup) - len(geo_results)} no match)")
                else:
                    result['geo_enriched'] = 0
                    result['geo_full'] = 0
                    result['geo_country_only'] = 0
                    result['geo_no_match'] = 0
                    logger.info(f"[{correlation_id}] No IPs need geo enrichment")
                
                # Auto-generate GeoJSON if enabled (only if we have some enriched data)
                if source.auto_generate_geojson and result.get('geo_enriched', 0) > 0:
                    try:
                        logger.info(f"[{correlation_id}] Auto-generating GeoJSON for {source_id}")
                        
                        # Create GeoJSON features (only for rows with coordinates)
                        features = []
                        skipped = 0
                        for row in rows_data:
                            feature = geo_client.create_geojson_feature(row)
                            if feature:
                                features.append(feature)
                            elif row.get('Latitude') or row.get('Longitude'):  # Had geo attempt but no coordinates
                                skipped += 1
                        
                        # Create and save GeoJSON to temp file
                        geojson = geo_client.create_geojson_collection(features)
                        geojson_filename = source.output_filename.replace('.tsv', '.geojson')
                        temp_geojson_filename = f"{geojson_filename}.tmp"
                        
                        blob_client = blob_storage.blob_service_client.get_blob_client(
                            container="datasets",
                            blob=temp_geojson_filename
                        )
                        
                        from azure.storage.blob import ContentSettings
                        content_settings = ContentSettings(content_type='application/geo+json')
                        
                        blob_client.upload_blob(
                            json.dumps(geojson, indent=2),
                            overwrite=True,
                            content_settings=content_settings
                        )
                        
                        result['geojson_file'] = geojson_filename
                        result['geojson_features'] = len(features)
                        result['geojson_skipped'] = skipped
                        logger.info(f"[{correlation_id}] GeoJSON generated: {len(features)} features ({skipped} skipped - no coordinates)")
                        
                        # Atomic rename: .tmp.geojson → .geojson
                        source_blob = blob_storage.blob_service_client.get_blob_client(
                            container="datasets",
                            blob=temp_geojson_filename
                        )
                        target_blob = blob_storage.blob_service_client.get_blob_client(
                            container="datasets",
                            blob=geojson_filename
                        )
                        target_blob.start_copy_from_url(source_blob.url)
                        source_blob.delete_blob()
                    
                    except Exception as geo_json_error:
                        logger.error(f"[{correlation_id}] GeoJSON generation failed: {geo_json_error}")
                        result['geojson_error'] = str(geo_json_error)
            
            except Exception as geo_error:
                logger.error(f"[{correlation_id}] Geo enrichment failed: {geo_error}")
                result['geo_error'] = str(geo_error)
        
        # Atomic rename: .tmp → production file
        logger.info(f"[{correlation_id}] Atomic file replacement for {source_id}")
        source_blob = blob_storage.blob_service_client.get_blob_client(
            container="datasets",
            blob=temp_filename
        )
        target_blob = blob_storage.blob_service_client.get_blob_client(
            container="datasets",
            blob=source.output_filename
        )
        
        # Copy and delete (blob storage doesn't support true atomic rename)
        target_blob.start_copy_from_url(source_blob.url)
        source_blob.delete_blob()
        
        # Update metadata
        refresh_policy.update_metadata(
            source_id,
            len(rows),
            query_hash,
            watermark=datetime.utcnow()
        )
        
        logger.info(f"[{correlation_id}] Successfully completed {action} for {source_id}")
        
        return result
    
    except Exception as e:
        logger.error(f"[{correlation_id}] Error during refresh: {e}", exc_info=True)
        # Clean up temp files on error
        try:
            temp_blob = blob_storage.blob_service_client.get_blob_client(
                container="datasets",
                blob=temp_filename
            )
            temp_blob.delete_blob()
        except:
            pass
        raise


@app.route(route="health", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def health(req: func.HttpRequest) -> func.HttpResponse:
    """
    Health check endpoint.
    
    Returns:
        200: Service is healthy
        503: Service is unhealthy
    """
    try:
        # Basic health check - verify configuration loads
        config_loader = ConfigLoader()
        sources = config_loader.get_all_sources()
        
        health_data = {
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'sources_configured': len(sources)
        }
        
        return func.HttpResponse(
            json.dumps(health_data),
            status_code=200,
            mimetype="application/json"
        )
    
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return func.HttpResponse(
            json.dumps({
                'status': 'unhealthy',
                'error': str(e)
            }),
            status_code=503,
            mimetype="application/json"
        )


@app.route(route="enrich-geo", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def enrich_geo(req: func.HttpRequest) -> func.HttpResponse:
    """
    Enrich TSV data with geolocation for IPs missing coordinates.
    
    Query parameters:
        - source_id: Data source to enrich (default: threat_intel_indicators)
        - force_all: Force re-lookup all IPs (default: false)
        - correlation_id: Optional correlation ID for logging
    
    Returns:
        200: Successfully enriched with geo data
        404: Source not found
        500: Internal error
    """
    correlation_id = req.params.get('correlation_id', req.headers.get('X-Correlation-ID', 'none'))
    logger.info(f"[{correlation_id}] Geo enrichment request received")
    
    source_id = req.params.get('source_id', 'threat_intel_indicators')
    force_all = req.params.get('force_all', 'false').lower() == 'true'
    
    try:
        # Initialize clients
        blob_storage = BlobStorageClient()
        geo_client = GeoEnrichmentClient()
        config_loader = ConfigLoader()
        
        # Get source configuration
        source = config_loader.get_source(source_id)
        if not source:
            return func.HttpResponse(
                json.dumps({'error': f'Source {source_id} not found'}),
                status_code=404,
                mimetype="application/json"
            )
        
        # Read existing TSV
        tsv_content = blob_storage.read_tsv(source.output_filename)
        if not tsv_content:
            return func.HttpResponse(
                json.dumps({'error': 'No TSV data found for source'}),
                status_code=404,
                mimetype="application/json"
            )
        
        # Parse TSV
        headers, rows = geo_client.parse_tsv_with_geo(tsv_content)
        
        # Find IPs needing lookup
        if force_all:
            ips_to_lookup = [row.get('ObservableValue', '') for row in rows if row.get('ObservableValue')]
            logger.info(f"Force mode: looking up all {len(ips_to_lookup)} IPs")
        else:
            ips_to_lookup = [row.get('ObservableValue', '') for row in rows 
                           if geo_client.needs_geo_lookup(row) and row.get('ObservableValue')]
            logger.info(f"Looking up {len(ips_to_lookup)} IPs missing coordinates")
        
        if not ips_to_lookup:
            return func.HttpResponse(
                json.dumps({
                    'message': 'No IPs need geo enrichment',
                    'total_rows': len(rows),
                    'enriched_count': 0
                }),
                status_code=200,
                mimetype="application/json"
            )
        
        # Batch lookup
        geo_results = geo_client.batch_lookup(ips_to_lookup, max_workers=10)
        
        # Update rows with geo data
        enriched_count = 0
        full_geo_count = 0
        country_only_count = 0
        
        for row in rows:
            ip = row.get('ObservableValue', '')
            if ip in geo_results:
                geo_data = geo_results[ip]
                row['Latitude'] = str(geo_data['latitude']) if geo_data.get('latitude') else ''
                row['Longitude'] = str(geo_data['longitude']) if geo_data.get('longitude') else ''
                row['Country'] = geo_data.get('country', '')
                row['City'] = geo_data.get('city', '')
                enriched_count += 1
                
                if geo_data.get('latitude') and geo_data.get('longitude'):
                    full_geo_count += 1
                else:
                    country_only_count += 1
        
        # Ensure geo columns exist in headers
        if 'Latitude' not in headers:
            headers.extend(['Latitude', 'Longitude', 'Country', 'City'])
        
        # Rebuild TSV
        tsv_lines = ['\t'.join(headers)]
        for row in rows:
            values = [str(row.get(h, '')) for h in headers]
            tsv_lines.append('\t'.join(values))
        
        updated_tsv = '\n'.join(tsv_lines)
        
        # Write back to blob storage
        blob_storage.write_tsv(source.output_filename, updated_tsv)
        
        logger.info(f"[{correlation_id}] Geo enrichment complete: {enriched_count}/{len(rows)} rows ({full_geo_count} with coordinates, {country_only_count} country-only)")
        
        return func.HttpResponse(
            json.dumps({
                'message': f'Enriched {enriched_count}/{len(rows)} rows with geolocation',
                'total_rows': len(rows),
                'enriched_count': enriched_count,
                'full_geo_count': full_geo_count,
                'country_only_count': country_only_count,
                'no_match_count': len(ips_to_lookup) - len(geo_results),
                'lookup_count': len(ips_to_lookup),
                'successful_lookups': len(geo_results),
                'correlation_id': correlation_id
            }),
            status_code=200,
            mimetype="application/json"
        )
    
    except Exception as e:
        logger.error(f"[{correlation_id}] Geo enrichment failed: {e}", exc_info=True)
        return func.HttpResponse(
            json.dumps({
                'error': str(e),
                'correlation_id': correlation_id
            }),
            status_code=500,
            mimetype="application/json"
        )

@app.route(route="test-geo-lookup", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def test_geo_lookup(req: func.HttpRequest) -> func.HttpResponse:
    """
    Test endpoint to lookup a specific IP using configured geo provider.
    
    Query parameters:
        - ip: IP address to lookup (required)
    
    Returns:
        200: Parsed geolocation data
        400: Missing IP parameter
        500: Lookup error
    """
    try:
        ip_address = req.params.get('ip')
        if not ip_address:
            return func.HttpResponse(
                json.dumps({'error': 'Missing required parameter: ip'}),
                status_code=400,
                mimetype="application/json"
            )
        
        config_loader = ConfigLoader()
        geo_client = GeoEnrichmentClient(provider=config_loader.geo_provider)
        
        # Do the lookup
        result = geo_client.lookup_ip_location(ip_address)
        
        return func.HttpResponse(
            json.dumps({
                'ip': ip_address,
                'provider': config_loader.geo_provider,
                'parsed_result': result
            }, indent=2),
            status_code=200,
            mimetype="application/json"
        )
    
    except Exception as e:
        logger.error(f"Test lookup failed: {e}")
        return func.HttpResponse(
            json.dumps({'error': str(e)}),
            status_code=500,
            mimetype="application/json"
        )

@app.route(route="generate-geojson", methods=["POST", "GET"], auth_level=func.AuthLevel.ANONYMOUS)
def generate_geojson(req: func.HttpRequest) -> func.HttpResponse:
    """
    Generate GeoJSON from TSV data with coordinates.
    
    Query parameters:
        - source_id: Data source to convert (default: threat_intel_indicators)
        - output_filename: Output GeoJSON filename (default: threat-intel-indicators.geojson)
        - correlation_id: Optional correlation ID for logging
    
    Returns:
        200: Successfully generated GeoJSON
        404: Source not found
        500: Internal error
    """
    correlation_id = req.params.get('correlation_id', req.headers.get('X-Correlation-ID', 'none'))
    logger.info(f"[{correlation_id}] GeoJSON generation request received")
    
    source_id = req.params.get('source_id', 'threat_intel_indicators')
    output_filename = req.params.get('output_filename', 'threat-intel-indicators.geojson')
    
    try:
        # Initialize clients
        blob_storage = BlobStorageClient()
        geo_client = GeoEnrichmentClient()
        config_loader = ConfigLoader()
        
        # Get source configuration
        source = config_loader.get_source(source_id)
        if not source:
            return func.HttpResponse(
                json.dumps({'error': f'Source {source_id} not found'}),
                status_code=404,
                mimetype="application/json"
            )
        
        # Read TSV
        tsv_content = blob_storage.read_tsv(source.output_filename)
        if not tsv_content:
            return func.HttpResponse(
                json.dumps({'error': 'No TSV data found for source'}),
                status_code=404,
                mimetype="application/json"
            )
        
        # Parse TSV
        headers, rows = geo_client.parse_tsv_with_geo(tsv_content)
        
        # Create GeoJSON features (only for rows with coordinates)
        features = []
        missing_coords = 0
        
        for row in rows:
            feature = geo_client.create_geojson_feature(row)
            if feature:
                features.append(feature)
            else:
                missing_coords += 1
        
        # Create GeoJSON collection
        geojson = geo_client.create_geojson_collection(features)
        geojson_content = json.dumps(geojson, indent=2)
        
        # Write to blob storage
        blob_client = blob_storage.service_client.get_blob_client(
            container=blob_storage.datasets_container,
            blob=output_filename
        )
        
        from azure.storage.blob import ContentSettings
        content_settings = ContentSettings(content_type='application/geo+json')
        
        blob_client.upload_blob(
            geojson_content,
            overwrite=True,
            content_settings=content_settings
        )
        
        logger.info(f"[{correlation_id}] GeoJSON generated: {len(features)} features, {missing_coords} missing coordinates")
        
        return func.HttpResponse(
            json.dumps({
                'message': 'GeoJSON generated successfully',
                'output_file': output_filename,
                'total_rows': len(rows),
                'features_created': len(features),
                'missing_coordinates': missing_coords,
                'correlation_id': correlation_id
            }),
            status_code=200,
            mimetype="application/json"
        )
    
    except Exception as e:
        logger.error(f"[{correlation_id}] GeoJSON generation failed: {e}", exc_info=True)
        return func.HttpResponse(
            json.dumps({
                'error': str(e),
                'correlation_id': correlation_id
            }),
            status_code=500,
            mimetype="application/json"
        )
