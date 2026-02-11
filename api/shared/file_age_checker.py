"""
Helper functions for file-age-based refresh logic.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
from azure.storage.blob import BlobClient

logger = logging.getLogger(__name__)


def check_file_age(blob_client: BlobClient, threshold_hours: int) -> Tuple[bool, Optional[datetime]]:
    """
    Check if a blob file exists and if it needs refresh based on age.
    
    Args:
        blob_client: Azure Blob Storage client
        threshold_hours: Age threshold in hours
        
    Returns:
        Tuple of (needs_refresh, last_modified_time)
        - needs_refresh: True if file doesn't exist or is older than threshold
        - last_modified_time: When file was last modified (None if doesn't exist)
    """
    try:
        props = blob_client.get_blob_properties()
        last_modified = props.last_modified
        
        age_hours = (datetime.now(last_modified.tzinfo) - last_modified).total_seconds() / 3600
        
        logger.info(f"File {blob_client.blob_name}: Last modified {last_modified} ({age_hours:.1f}h ago)")
        
        needs_refresh = age_hours >= threshold_hours
        return needs_refresh, last_modified
        
    except Exception as e:
        logger.info(f"File {blob_client.blob_name} does not exist or error checking: {e}")
        return True, None  # File doesn't exist, needs initial pull


def get_file_stats(blob_client: BlobClient) -> Optional[Dict[str, Any]]:
    """
    Get file statistics for response.
    
    Args:
        blob_client: Azure Blob Storage client
        
    Returns:
        Dictionary with file stats or None if file doesn't exist
    """
    try:
        props = blob_client.get_blob_properties()
        return {
            'exists': True,
            'last_modified': props.last_modified.isoformat(),
            'size_bytes': props.size,
            'age_hours': (datetime.now(props.last_modified.tzinfo) - props.last_modified).total_seconds() / 3600
        }
    except:
        return {
            'exists': False,
            'last_modified': None,
            'size_bytes': 0,
            'age_hours': None
        }
