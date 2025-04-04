import requests
import json
import os
from urllib.parse import urlparse
from urllib3.exceptions import InsecureRequestWarning
from pymongo import MongoClient
from datetime import datetime
from dotenv import load_dotenv


# Disable SSL warnings
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

class RedfishCollector:
    def __init__(self, host, username, password, test_mode=False):
        self.base_url = f"https://{host}"
        self.session = requests.Session()
        self.session.auth = (username, password)
        self.session.verify = False
        self.test_mode = test_mode
        self.output_dir = "redfish_data"
        os.makedirs(self.output_dir, exist_ok=True)
        
        # MongoDB configuration with type conversion
        self.mongo_uri = str(os.getenv("MONGO_URI"))
        self.mongo_db = str(os.getenv("MONGO_DB"))
        self.mongo_collection = str(os.getenv("MONGO_COLLECTION"))
        
        # Hardcoded API endpoints
        self.api_endpoints = [
            '/redfish/v1',
            '/redfish/v1/Systems/1',
            '/redfish/v1/Chassis/1',
            '/redfish/v1/Managers/1'
        ]

    def _get_mongo_client(self):
        """Create and return MongoDB client with error handling"""
        try:
            client = MongoClient(
                self.mongo_uri,
                serverSelectionTimeoutMS=5000  # 5 second timeout
            )
            # Verify connection works
            client.server_info()
            return client
        except Exception as e:
            print(f"MongoDB connection error: {e}")
            return None

    def _save_to_mongodb(self, data, endpoint):
        """Save data to MongoDB with proper error handling"""
        client = None
        try:
            client = self._get_mongo_client()
            if not client:
                return False
                
            db = client[self.mongo_db]
            collection = db[self.mongo_collection]
            
            document = {
                'endpoint': str(endpoint),
                'data': data,
                'collection_date': datetime.utcnow(),
                'source': str(self.base_url),
                'test_mode': self.test_mode
            }
            
            result = collection.insert_one(document)
            print(f"Successfully saved to MongoDB (ID: {result.inserted_id})")
            return True
            
        except Exception as e:
            print(f"Error saving to MongoDB: {str(e)}")
            return False
        finally:
            if client:
                client.close()

    def _save_to_file(self, data, endpoint):
        """Save response to JSON file"""
        try:
            filename = endpoint.strip('/').replace('/', '_') or 'root'
            filename = f"{filename}.json"
            filepath = os.path.join(self.output_dir, filename)
            
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=4)
            
            print(f"Saved response to {filepath}")
            return True
        except Exception as e:
            print(f"Error saving file: {e}")
            return False

    def get_api_response(self, endpoint):
        """Get API response from real iLO or return test data"""
        if self.test_mode:
            print(f"[TEST MODE] Simulating request to {endpoint}")
            mock_data = {
                'endpoint': endpoint,
                'mock_data': True,
                'timestamp': datetime.utcnow().isoformat()
            }
            self._save_to_file(mock_data, endpoint)
            self._save_to_mongodb(mock_data, endpoint)
            return mock_data
            
        url = f"{self.base_url}{endpoint}"
        try:
            response = self.session.get(url)
            response.raise_for_status()
            data = response.json()
            
            # Save to both file and MongoDB
            self._save_to_file(data, endpoint)
            self._save_to_mongodb(data, endpoint)
            
            return data
        except requests.exceptions.RequestException as e:
            print(f"Error accessing {url}: {e}")
            return None

    def collect_all(self):
        """Collect data from all configured endpoints"""
        print(f"\n{'[TEST MODE] ' if self.test_mode else ''}Starting collection...")
        print(f"Storage targets: Local JSON files and MongoDB at {self.mongo_uri}")
        
        for endpoint in self.api_endpoints:
            print(f"\nCollecting {endpoint}")
            self.get_api_response(endpoint)
        
        print("\nCollection complete!")

def main():
    # Load environment variables
    load_dotenv()
    
    # Check for test mode
    test_mode = os.getenv('TEST_MODE', '').lower() in ('true', '1', 't')
    
    if test_mode:
        print("Running in TEST MODE - using mock data")
        collector = RedfishCollector(
            host="mock-ilo.example.com",
            username="test-user",
            password="test-pass",
            test_mode=True
        )
    else:
        # Verify production credentials exist
        required_vars = ['ILO_HOST', 'ILO_USER', 'ILO_PASSWORD']
        missing = [var for var in required_vars if not os.getenv(var)]
        if missing:
            raise ValueError(f"Missing required ILO credentials: {', '.join(missing)}")
        
        collector = RedfishCollector(
            host=os.getenv('ILO_HOST'),
            username=os.getenv('ILO_USER'),
            password=os.getenv('ILO_PASSWORD')
        )
    
    collector.collect_all()

if __name__ == "__main__":
    main()