"""
Geo-enrichment module for IP address geolocation.
Supports MaxMind GeoLite2 (full coordinates) and Azure Maps (country-only).

This product includes GeoLite2 data created by MaxMind, available from https://www.maxmind.com
"""
import os
import logging
import json
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests

logger = logging.getLogger(__name__)


class GeoEnrichmentClient:
    """Client for IP geolocation services (MaxMind or Azure Maps)."""
    
    def __init__(self, provider: str = "maxmind", key_vault_client=None):
        """
        Initialize the geo enrichment client.
        
        Args:
            provider: Geo provider to use - "maxmind" or "azure_maps"
            key_vault_client: Optional KeyVaultClient for retrieving secrets
        """
        self.provider = provider.lower()
        
        if self.provider == "maxmind":
            # Try Key Vault first, then environment variable
            if key_vault_client:
                self.license_key = key_vault_client.get_secret('MAXMIND-LICENSE-KEY', 'MAXMIND_LICENSE_KEY')
            else:
                self.license_key = os.environ.get('MAXMIND_LICENSE_KEY')
            
            self.database_path = os.environ.get('MAXMIND_DATABASE_PATH', '/tmp/GeoLite2-City.mmdb')
            if not self.license_key:
                logger.warning("MAXMIND_LICENSE_KEY not set - will attempt to use existing database")
            self._maxmind_reader = None
            logger.info("MaxMind GeoLite2 client initialized")
        elif self.provider == "azure_maps":
            # Try Key Vault first, then environment variable
            if key_vault_client:
                self.subscription_key = key_vault_client.get_secret('AZURE-MAPS-SUBSCRIPTION-KEY', 'AZURE_MAPS_SUBSCRIPTION_KEY')
            else:
                self.subscription_key = os.environ.get('AZURE_MAPS_SUBSCRIPTION_KEY')
            
            if not self.subscription_key:
                logger.warning("AZURE_MAPS_SUBSCRIPTION_KEY not set - geo enrichment will fail")
            logger.info("Azure Maps client initialized (country-only)")
        else:
            logger.error(f"Unknown geo provider: {provider}")
            raise ValueError(f"Unknown geo provider: {provider}. Use 'maxmind' or 'azure_maps'")
    
    def _ensure_maxmind_database(self) -> bool:
        """
        Ensure MaxMind database exists, download if needed.
        
        Returns:
            True if database is available
        """
        import os.path
        
        # Check if database already exists
        if os.path.exists(self.database_path):
            logger.info(f"MaxMind database found at {self.database_path}")
            return True
        
        # Need to download - requires license key
        if not self.license_key:
            logger.error("MaxMind database not found and no license key to download")
            return False
        
        try:
            import tarfile
            import requests
            
            logger.info("Downloading MaxMind GeoLite2-City database...")
            
            # Download URL (this is the permalink format)
            url = f"https://download.maxmind.com/app/geoip_download?edition_id=GeoLite2-City&license_key={self.license_key}&suffix=tar.gz"
            
            response = requests.get(url, timeout=300)  # 5 min timeout for download
            if response.status_code != 200:
                logger.error(f"Failed to download MaxMind database: {response.status_code}")
                return False
            
            # Save and extract
            tar_path = '/tmp/GeoLite2-City.tar.gz'
            with open(tar_path, 'wb') as f:
                f.write(response.content)
            
            # Extract .mmdb file from tar
            with tarfile.open(tar_path, 'r:gz') as tar:
                for member in tar.getmembers():
                    if member.name.endswith('.mmdb'):
                        member.name = os.path.basename(member.name)
                        tar.extract(member, '/tmp')
                        os.rename('/tmp/' + member.name, self.database_path)
                        break
            
            os.remove(tar_path)
            logger.info(f"MaxMind database downloaded to {self.database_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to download MaxMind database: {e}")
            return False
    
    def _get_maxmind_reader(self):
        """
        Get or create MaxMind database reader.
        
        Returns:
            MaxMind reader instance or None
        """
        if self._maxmind_reader is None:
            try:
                import geoip2.database
                
                if not self._ensure_maxmind_database():
                    return None
                
                self._maxmind_reader = geoip2.database.Reader(self.database_path)
                logger.info("MaxMind reader initialized")
            except ImportError:
                logger.error("geoip2 library not installed. Run: pip install geoip2")
                return None
            except Exception as e:
                logger.error(f"Failed to initialize MaxMind reader: {e}")
                return None
        
        return self._maxmind_reader
    
    def lookup_ip_location(self, ip_address: str) -> Optional[Dict[str, Any]]:
        """
        Lookup geolocation for an IP address using configured provider.
        
        Args:
            ip_address: IP address to lookup
            
        Returns:
            Dictionary with geo data or None if lookup fails
        """
        if self.provider == "maxmind":
            return self._lookup_maxmind(ip_address)
        elif self.provider == "azure_maps":
            return self._lookup_azure_maps(ip_address)
        else:
            logger.error(f"Unknown provider: {self.provider}")
            return None
    
    def _lookup_maxmind(self, ip_address: str) -> Optional[Dict[str, Any]]:
        """
        Lookup IP using MaxMind GeoLite2 database.
        
        Args:
            ip_address: IP address to lookup
            
        Returns:
            Dictionary with geo data or None
        """
        try:
            reader = self._get_maxmind_reader()
            if not reader:
                logger.error("MaxMind reader not available")
                return None
            
            response = reader.city(ip_address)
            
            result = {
                "ip_address": ip_address,
                "country": response.country.iso_code or "",
                "country_name": response.country.name or "",
                "region": response.subdivisions.most_specific.name if response.subdivisions else "",
                "city": response.city.name or "",
                "latitude": response.location.latitude,
                "longitude": response.location.longitude,
                "isp": "",  # GeoLite2-City doesn't include ISP (need GeoLite2-ASN for that)
                "confidence": "full",
                "lookup_timestamp": datetime.utcnow().isoformat()
            }
            
            logger.info(f"MaxMind: IP {ip_address}: {result['city']}, {result['country']} ({result['latitude']}, {result['longitude']})")
            return result
            
        except Exception as e:
            logger.warning(f"MaxMind lookup failed for {ip_address}: {e}")
            return None
    
    def _lookup_azure_maps(self, ip_address: str) -> Optional[Dict[str, Any]]:
        """
        Lookup IP using Azure Maps (country-only).
        
        Args:
            ip_address: IP address to lookup
            
        Returns:
            Dictionary with geo data (country-only) or None
        """
        try:
            url = "https://atlas.microsoft.com/geolocation/ip/json"
            params = {
                "api-version": "1.0",
                "ip": ip_address
            }
            headers = {
                "subscription-key": self.subscription_key
            }
            
            response = requests.get(url, params=params, headers=headers, timeout=10)
            
            if response.status_code != 200:
                logger.warning(f"Azure Maps lookup failed for {ip_address}: {response.status_code}")
                return None
            
            data = response.json()
            country_region = data.get("countryRegion", {})
            country_code = country_region.get("isoCode", "")
            
            if not country_code:
                logger.info(f"IP {ip_address}: No data in Azure Maps")
                return None
            
            result = {
                "ip_address": ip_address,
                "country": country_code,
                "country_name": "",
                "region": "",
                "city": "",
                "latitude": None,
                "longitude": None,
                "isp": "",
                "confidence": "country_only",
                "lookup_timestamp": datetime.utcnow().isoformat()
            }
            
            logger.info(f"Azure Maps: IP {ip_address}: Country {country_code} (no coordinates)")
            return result
            
        except Exception as e:
            logger.error(f"Azure Maps lookup failed for {ip_address}: {e}")
            return None
    
    def batch_lookup(self, ip_addresses: List[str], max_workers: int = 5) -> Dict[str, Dict[str, Any]]:
        """
        Lookup multiple IP addresses with concurrency.
        
        Args:
            ip_addresses: List of IP addresses to lookup
            max_workers: Maximum concurrent requests
            
        Returns:
            Dictionary mapping IP addresses to location data
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        results = {}
        unique_ips = list(set(ip_addresses))  # Deduplicate
        
        logger.info(f"Starting batch lookup for {len(unique_ips)} unique IPs")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_ip = {executor.submit(self.lookup_ip_location, ip): ip for ip in unique_ips}
            
            for future in as_completed(future_to_ip):
                ip = future_to_ip[future]
                try:
                    result = future.result()
                    if result:
                        results[ip] = result
                except Exception as e:
                    logger.error(f"Exception looking up {ip}: {e}")
        
        logger.info(f"Batch lookup complete: {len(results)}/{len(unique_ips)} successful")
        return results
    
    @staticmethod
    def create_geojson_feature(indicator: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Create a GeoJSON feature from a threat indicator with geolocation.
        
        Args:
            indicator: Threat indicator dictionary with lat/lon
            
        Returns:
            GeoJSON feature or None if missing coordinates
        """
        try:
            lat = indicator.get("Latitude") or indicator.get("latitude")
            lon = indicator.get("Longitude") or indicator.get("longitude")
            
            if lat is None or lon is None:
                return None
            
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [float(lon), float(lat)]  # GeoJSON is [lon, lat]
                },
                "properties": {
                    "observableValue": indicator.get("ObservableValue", ""),
                    "type": indicator.get("Type", ""),
                    "label": indicator.get("Label", ""),
                    "confidence": indicator.get("Confidence", ""),
                    "description": indicator.get("Description", ""),
                    "country": indicator.get("Country", ""),
                    "city": indicator.get("City", ""),
                    "sourceSystem": indicator.get("SourceSystem", ""),
                    "timeGenerated": indicator.get("TimeGenerated", ""),
                    "created": indicator.get("Created", ""),
                    "isActive": indicator.get("IsActive", True)
                }
            }
            
            return feature
        
        except Exception as e:
            logger.error(f"Failed to create GeoJSON feature: {e}")
            return None
    
    @staticmethod
    def create_geojson_collection(features: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Create a GeoJSON FeatureCollection from a list of features.
        
        Args:
            features: List of GeoJSON features
            
        Returns:
            GeoJSON FeatureCollection
        """
        return {
            "type": "FeatureCollection",
            "metadata": {
                "generated": datetime.utcnow().isoformat(),
                "count": len(features),
                "source": "Sentinel Activity Maps - Threat Intelligence"
            },
            "features": features
        }
    
    @staticmethod
    def parse_tsv_with_geo(tsv_content: str) -> Tuple[List[str], List[Dict[str, Any]]]:
        """
        Parse TSV content and extract rows with geolocation data.
        
        Args:
            tsv_content: TSV file content as string
            
        Returns:
            Tuple of (headers, rows as dictionaries)
        """
        lines = tsv_content.strip().split('\n')
        if not lines:
            return [], []
        
        headers = lines[0].split('\t')
        rows = []
        
        for line in lines[1:]:
            values = line.split('\t')
            if len(values) == len(headers):
                row = dict(zip(headers, values))
                rows.append(row)
        
        return headers, rows
    
    @staticmethod
    def needs_geo_lookup(row: Dict[str, Any]) -> bool:
        """
        Check if a row needs geolocation lookup.
        
        Args:
            row: Row dictionary from TSV
            
        Returns:
            True if geolocation is missing or invalid
        """
        lat = row.get("Latitude", "")
        lon = row.get("Longitude", "")
        
        # Need lookup if either is missing or empty
        return not lat or not lon or lat == "" or lon == ""
