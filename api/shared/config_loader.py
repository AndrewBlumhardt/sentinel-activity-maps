"""
Configuration loader for data sources.
Reads sources.yaml and provides structured access to query definitions.
"""
import os
import yaml
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class DataSource:
    """Represents a single data source configuration."""
    
    def __init__(self, config: Dict[str, Any]):
        self.id = config['id']
        self.name = config['name']
        self.enabled = config.get('enabled', True)
        self.refresh_interval_seconds = config.get('refresh_interval_seconds', 300)
        self.query_time_window_hours = config.get('query_time_window_hours', 24)
        self.incremental = config.get('incremental', True)
        self.incremental_overlap_minutes = config.get('incremental_overlap_minutes', 10)
        self.output_filename = config['output_filename']
        self.kql_query = config['kql_query']
        self.columns = config.get('columns', [])
    
    def get_query(self, time_window_hours: int = None) -> str:
        """
        Get the KQL query with time window parameter substituted.
        
        Args:
            time_window_hours: Override the default time window
            
        Returns:
            KQL query string with {time_window} replaced
        """
        window = time_window_hours or self.query_time_window_hours
        return self.kql_query.format(time_window=window)


class ConfigLoader:
    """Loads and manages data source configurations."""
    
    def __init__(self, config_path: str = None):
        """
        Initialize the config loader.
        
        Args:
            config_path: Path to sources.yaml (defaults to sources.yaml in api folder)
        """
        if config_path is None:
            # Default to sources.yaml in the api folder
            api_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_path = os.path.join(api_dir, 'sources.yaml')
        
        self.config_path = config_path
        self._sources: List[DataSource] = []
        self._load_config()
    
    def _load_config(self):
        """Load configuration from YAML file."""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            sources_config = config.get('sources', [])
            self._sources = [DataSource(src) for src in sources_config]
            
            logger.info(f"Loaded {len(self._sources)} data sources from {self.config_path}")
        except Exception as e:
            logger.error(f"Failed to load config from {self.config_path}: {e}")
            raise
    
    def get_all_sources(self) -> List[DataSource]:
        """Get all configured data sources."""
        return self._sources
    
    def get_enabled_sources(self) -> List[DataSource]:
        """Get only enabled data sources."""
        return [src for src in self._sources if src.enabled]
    
    def get_source_by_id(self, source_id: str) -> DataSource:
        """
        Get a specific source by ID.
        
        Args:
            source_id: The source ID to retrieve
            
        Returns:
            DataSource object
            
        Raises:
            ValueError: If source ID not found
        """
        for source in self._sources:
            if source.id == source_id:
                return source
        raise ValueError(f"Data source '{source_id}' not found in configuration")
