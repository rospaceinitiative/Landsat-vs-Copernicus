import os
import requests
import zipfile
from shapely.geometry import box

# Set your Copernicus Data Space credentials and client ID
USERNAME = "simoneldavid17@gmail.com"  # Replace with your username
PASSWORD = "simonelD700!"               # Replace with your password
CLIENT_ID = "cdse-public"

# Directory to save downloaded files
DOWNLOAD_DIR = "downloaded_products"
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

# Define date range and AOI for Cluj-Napoca
start_date = "2021-07-01"
end_date = "2021-07-31"
aoi = box(23.53618, 46.73862, 23.63058, 46.80108)  # Hardcoded bounding box for Cluj-Napoca
aoi_wkt = aoi.wkt

def get_tokens():
    """Retrieve access and refresh tokens."""
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

def refresh_access_token(refresh_token):
    """Use the refresh token to get a new access token."""
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

# Get initial access and refresh tokens
access_token, refresh_token = get_tokens()
headers = {"Authorization": f"Bearer {access_token}"}
BASE_URL = "https://catalogue.dataspace.copernicus.eu/resto/api/collections/Sentinel3/search.json"

# Set up query parameters with hardcoded dates and AOI
query_params = {
    "startDate": start_date,
    "completionDate": end_date,
    "productType": "SL_2_LST___",  # Sentinel-3 Level-2 Land Surface Temperature product
    "geometry": aoi_wkt,
    "maxRecords": 10
}

# Make the search request
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
                # Refresh token if unauthorized
                access_token = refresh_access_token(refresh_token)
                session.headers.update({"Authorization": f"Bearer {access_token}"})
                download_response = session.get(download_url, stream=True)

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
