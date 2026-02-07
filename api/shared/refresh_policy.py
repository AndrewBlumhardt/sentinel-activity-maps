"""
Refresh policy manager with throttling and incremental updates.
Handles time-based gating and watermark tracking for data sources.
"""
import os
import logging
from typing import Optional, Tuple
from datetime import datetime, timedelta
from .blob_storage import BlobStorageClient

logger = logging.getLogger(__name__)


class RefreshPolicy:
    """Manages refresh intervals and incremental query logic."""
    
    def __init__(self, blob_client: BlobStorageClient):
        """
        Initialize the refresh policy manager.
        
        Args:
            blob_client: BlobStorageClient instance for metadata operations
        """
        self.blob_client = blob_client
        self.default_interval = int(os.getenv('DEFAULT_REFRESH_INTERVAL_SECONDS', '300'))
    
    def should_refresh(self, source_id: str, interval_seconds: int) -> Tuple[bool, Optional[str]]:
        """
        Check if a data source should be refreshed based on last update time.
        
        Args:
            source_id: Data source identifier
            interval_seconds: Minimum interval between refreshes
            
        Returns:
            Tuple of (should_refresh: bool, reason: str)
        """
        metadata = self.blob_client.read_metadata(source_id)
        
        if metadata is None:
            return True, "first_run"
        
        last_update_str = metadata.get('last_updated')
        if not last_update_str:
            return True, "no_last_update"
        
        try:
            last_update = datetime.fromisoformat(last_update_str)
            elapsed = (datetime.utcnow() - last_update).total_seconds()
            
            if elapsed >= interval_seconds:
                return True, f"interval_exceeded_{int(elapsed)}s"
            else:
                remaining = int(interval_seconds - elapsed)
                return False, f"too_soon_{remaining}s_remaining"
        
        except Exception as e:
            logger.warning(f"Failed to parse last update time: {e}")
            return True, "parse_error"
    
    def get_query_timespan(self, source_id: str, time_window_hours: int, 
                           overlap_minutes: int, incremental: bool) -> Tuple[timedelta, Optional[datetime]]:
        """
        Calculate the query timespan for a data source.
        
        For incremental queries, uses watermark with overlap window.
        For full queries, uses the full time window.
        
        Args:
            source_id: Data source identifier
            time_window_hours: Default time window in hours
            overlap_minutes: Overlap window for incremental queries
            incremental: Whether to use incremental query logic
            
        Returns:
            Tuple of (timespan: timedelta, watermark: datetime or None)
        """
        if not incremental:
            # Full query - use entire time window
            logger.info(f"Using full query window: {time_window_hours} hours")
            return timedelta(hours=time_window_hours), None
        
        # Incremental query - check watermark
        metadata = self.blob_client.read_metadata(source_id)
        
        if metadata is None or 'last_query_watermark' not in metadata:
            # First run - use full time window
            logger.info(f"First incremental run - using full window: {time_window_hours} hours")
            return timedelta(hours=time_window_hours), None
        
        try:
            watermark = datetime.fromisoformat(metadata['last_query_watermark'])
            
            # Calculate time since watermark with overlap
            now = datetime.utcnow()
            watermark_with_overlap = watermark - timedelta(minutes=overlap_minutes)
            timespan = now - watermark_with_overlap
            
            logger.info(f"Incremental query from {watermark} (with {overlap_minutes}min overlap)")
            return timespan, watermark
        
        except Exception as e:
            logger.warning(f"Failed to parse watermark, using full window: {e}")
            return timedelta(hours=time_window_hours), None
    
    def update_metadata(self, source_id: str, row_count: int, query_hash: str,
                       watermark: datetime = None) -> None:
        """
        Update metadata after successful refresh.
        
        Args:
            source_id: Data source identifier
            row_count: Number of rows in the result
            query_hash: Hash of the query for change tracking
            watermark: New watermark timestamp (defaults to now)
        """
        if watermark is None:
            watermark = datetime.utcnow()
        
        metadata = {
            'last_updated': datetime.utcnow().isoformat(),
            'last_query_watermark': watermark.isoformat(),
            'row_count': row_count,
            'query_hash': query_hash
        }
        
        self.blob_client.write_metadata(source_id, metadata)
        logger.info(f"Updated metadata for {source_id}: {row_count} rows")
    
    @staticmethod
    def compute_query_hash(kql_query: str) -> str:
        """
        Compute a hash of the KQL query for change detection.
        
        Args:
            kql_query: The KQL query string
            
        Returns:
            Hash string (first 8 chars of hex digest)
        """
        import hashlib
        return hashlib.sha256(kql_query.encode()).hexdigest()[:8]
