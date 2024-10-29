import os
import requests
import zipfile
from shapely.geometry import box

# Define credentials and client ID for accessing Copernicus Data Space
USERNAME = "your_username"  # Replace with actual username
PASSWORD = "your_password"  # Replace with actual password
CLIENT_ID = "cdse-public"

# Set up directory for downloaded Copernicus LST data files
DOWNLOAD_DIR = "copernicus_data"
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

# Define date range and Area of Interest (AOI) for Cluj-Napoca using a hardcoded bounding box
start_date = "2021-07-01"
end_date = "2021-07-31"
aoi = box(23.53618, 46.73862, 23.63058, 46.80108)  # Cluj-Napoca bounding box coordinates
aoi_wkt = aoi.wkt

# Function to retrieve access and refresh tokens for authenticated Copernicus API requests
def get_tokens():
    token_url = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
    response = requests.post(
        token_url,
        data={
            "client_id": CLIENT_ID,
            "username": USERNAME,
            "password": PASSWORD,
            "grant_type": "password"
        }
    )
    if response.status_code == 200:
        token_data = response.json()
        return token_data["access_token"], token_data["refresh_token"]
    else:
        raise Exception("Failed to retrieve tokens:", response.status_code, response.text)

# Function to refresh access token if it expires during the session
def refresh_access_token(refresh_token):
    token_url = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
    response = requests.post(
        token_url,
        data={
            "client_id": CLIENT_ID,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token
        }
    )
    if response.status_code == 200:
        return response.json()["access_token"]
    else:
        raise Exception("Failed to refresh access token:", response.status_code, response.text)

# Obtain initial tokens for accessing the Copernicus data
access_token, refresh_token = get_tokens()
headers = {"Authorization": f"Bearer {access_token}"}

# Define base URL for the Copernicus Data Space API and set up query parameters for LST data retrieval
BASE_URL = "https://catalogue.dataspace.copernicus.eu/resto/api/collections/Sentinel3/search.json"
query_params = {
    "startDate": start_date,
    "completionDate": end_date,
    "productType": "SL_2_LST___",
    "geometry": aoi_wkt,
    "maxRecords": 10
}

# Perform search request to retrieve Sentinel-3 LST products for the specified date range and AOI
response = requests.get(BASE_URL, params=query_params, headers=headers)
if response.status_code == 200:
    results = response.json()
    products = results.get("features", [])
    
    if products:
        print(f"Found {len(products)} LST products for the specified criteria.")
        for product in products:
            title = product["properties"]["title"]
            product_id = product["id"]
            download_url = f"https://download.dataspace.copernicus.eu/odata/v1/Products({product_id})/$value"
            session = requests.Session()
            session.headers.update(headers)

            # Download each product
            download_response = session.get(download_url, stream=True)
            if download_response.status_code == 401:
                # Refresh token if unauthorized and retry download
                access_token = refresh_access_token(refresh_token)
                session.headers.update({"Authorization": f"Bearer {access_token}"})
                download_response = session.get(download_url, stream=True)

            # Save and extract downloaded products
            if download_response.status_code == 200:
                zip_file_path = os.path.join(DOWNLOAD_DIR, f"{title}.zip")
                with open(zip_file_path, "wb") as file:
                    for chunk in download_response.iter_content(chunk_size=8192):
                        file.write(chunk)
                extract_path = os.path.join(DOWNLOAD_DIR, title)
                with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_path)
                print(f"Downloaded and extracted {title}.")
            else:
                print(f"Failed to download {title}. Status code: {download_response.status_code}")
    else:
        print("No products found for the specified criteria.")
else:
    print(f"Search request failed with status code: {response.status_code} and message: {response.text}")
