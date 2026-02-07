"""
Azure Functions app for Sentinel Activity Maps.
HTTP-triggered function to refresh threat intelligence datasets.
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
    
    Query parameters:
        - source_id: Optional specific source to refresh (default: all enabled)
        - force: Optional flag to bypass throttling (default: false)
        - correlation_id: Optional correlation ID for logging
    
    Returns:
        200: Successfully refreshed
        204: No refresh needed (throttled)
        202: Refresh in progress (locked)
        429: Too many requests (rate limited)
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
        
        # Determine which sources to refresh
        if source_id:
            sources = [config_loader.get_source_by_id(source_id)]
            logger.info(f"[{correlation_id}] Refreshing specific source: {source_id}")
        else:
            sources = config_loader.get_enabled_sources()
            logger.info(f"[{correlation_id}] Refreshing {len(sources)} enabled sources")
        
        if not sources:
            return func.HttpResponse(
                json.dumps({"message": "No sources to refresh"}),
                status_code=204,
                mimetype="application/json"
            )
        
        # Track results
        results = []
        refreshed_count = 0
        
        for source in sources:
            try:
                result = _refresh_source(
                    source=source,
                    log_analytics=log_analytics,
                    blob_storage=blob_storage,
                    refresh_policy=refresh_policy,
                    force=force,
                    correlation_id=correlation_id
                )
                results.append(result)
                
                if result['status'] == 'refreshed':
                    refreshed_count += 1
            
            except Exception as e:
                logger.error(f"[{correlation_id}] Failed to refresh {source.id}: {e}")
                results.append({
                    'source_id': source.id,
                    'status': 'error',
                    'message': str(e)
                })
        
        # Determine overall status code
        if refreshed_count > 0:
            status_code = 200
            message = f"Refreshed {refreshed_count}/{len(sources)} sources"
        else:
            # Check if any were locked
            locked = any(r['status'] == 'locked' for r in results)
            if locked:
                status_code = 202
                message = "Refresh in progress"
            else:
                status_code = 204
                message = "No refresh needed"
        
        response_data = {
            'message': message,
            'refreshed_count': refreshed_count,
            'total_sources': len(sources),
            'results': results,
            'correlation_id': correlation_id
        }
        
        logger.info(f"[{correlation_id}] Request completed: {status_code}")
        
        return func.HttpResponse(
            json.dumps(response_data, default=str),
            status_code=status_code,
            mimetype="application/json",
            headers={
                'X-Correlation-ID': correlation_id,
                'X-Refreshed-Count': str(refreshed_count)
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


def _refresh_source(source, log_analytics, blob_storage, refresh_policy, force, correlation_id):
    """
    Refresh a single data source.
    
    Returns:
        Dictionary with refresh result
    """
    source_id = source.id
    logger.info(f"[{correlation_id}] Processing source: {source_id}")
    
    # Check if refresh is needed (unless forced)
    if not force:
        should_refresh, reason = refresh_policy.should_refresh(
            source_id,
            source.refresh_interval_seconds
        )
        
        if not should_refresh:
            logger.info(f"[{correlation_id}] Skipping {source_id}: {reason}")
            return {
                'source_id': source_id,
                'status': 'skipped',
                'reason': reason
            }
    
    # Try to acquire lock
    lease_id = blob_storage.acquire_lock(source_id, lease_duration=60)
    if lease_id is None:
        logger.warning(f"[{correlation_id}] Could not acquire lock for {source_id}")
        return {
            'source_id': source_id,
            'status': 'locked',
            'message': 'Another process is refreshing this source'
        }
    
    try:
        # Calculate query timespan
        timespan, watermark = refresh_policy.get_query_timespan(
            source_id,
            source.query_time_window_hours,
            source.incremental_overlap_minutes,
            source.incremental
        )
        
        # Execute query
        kql_query = source.get_query(int(timespan.total_seconds() / 3600))
        query_hash = refresh_policy.compute_query_hash(kql_query)
        
        logger.info(f"[{correlation_id}] Executing query for {source_id}")
        rows = log_analytics.execute_query(kql_query, timespan)
        
        # Write TSV to blob
        tsv_content = TSVWriter.write_tsv(rows, source.columns)
        blob_storage.write_tsv(source.output_filename, tsv_content)
        
        # Update metadata
        refresh_policy.update_metadata(
            source_id,
            len(rows),
            query_hash,
            watermark=datetime.utcnow()
        )
        
        logger.info(f"[{correlation_id}] Successfully refreshed {source_id}: {len(rows)} rows")
        
        return {
            'source_id': source_id,
            'status': 'refreshed',
            'row_count': len(rows),
            'output_file': source.output_filename
        }
    
    finally:
        # Always release the lock
        blob_storage.release_lock(source_id, lease_id)


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
