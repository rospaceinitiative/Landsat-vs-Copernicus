# Import necessary modules
import ee
import datetime
import geemap.foliumap as geemap
import subprocess
import json
import time
import sys
import os

# Authenticate to Earth Engine
service_account = 'copenricus-vs-landsat-workshop@ee-simoneldavid.iam.gserviceaccount.com'
credentials = ee.ServiceAccountCredentials(service_account, 'ee-simoneldavid-84d91d8a227c.json')
ee.Initialize(credentials)

# Ensure that the city name and years are provided as command-line arguments
if len(sys.argv) != 7:
    print("Usage: python3 gee_export.py <city_name> <start_year> <end_year> <start_month> <end_month> <address_type>")
    sys.exit(1)

# Get the city name, start year, and end year from the command-line arguments
city_name = sys.argv[1]
start_year = int(sys.argv[2])
end_year = int(sys.argv[3])
start_month = int(sys.argv[4])
end_month = int(sys.argv[5])
address_type = sys.argv[6]

# Calculate the day of year range
start_day_of_year = (datetime.datetime(start_year, start_month, 1) - datetime.datetime(start_year, 1, 1)).days + 1
end_day_of_year = (datetime.datetime(end_year, end_month, 1) - datetime.datetime(end_year, 1, 1)).days + 1

# Function to retrieve the bounding box using OpenStreetMap's Nominatim API
def get_bounding_boxes(city_name, address_type):
    url = f"https://nominatim.openstreetmap.org/search.php?q={city_name}&polygon_geojson=1&format=json"
    
    for attempt in range(5):  # Retry up to 5 times
        try:
            result = subprocess.run(
                ["curl", "-s", url],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            if result.returncode != 0:
                print(f"Error running curl command: {result.stderr}. Retrying in {2 ** attempt} seconds...")
                time.sleep(2 ** attempt)  # Exponential backoff
                continue
            
            data = json.loads(result.stdout)
            
            if not data:
                print(f"No data found for {city_name}")
                return None

            bounding_box = None

            for city_data in data:
                if city_data.get('type') == 'administrative' and city_data.get('addresstype') == address_type:
                    bounding_box = city_data.get('geojson').get('coordinates')
                    break  # Exit the loop once the correct type is found

            if not bounding_box:
                print(f"No bounding box found for {city_name} with type '{address_type}'")
                return None

            # Handle the structure based on the type of geometry
            if city_data.get('geojson').get('type') == 'MultiPolygon':
                return bounding_box[0][0]
            elif city_data.get('geojson').get('type') == 'Polygon':
                return bounding_box[0]
            else:
                print(f"Unsupported geometry type for {city_name}")
                return None
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON: {e}. Retrying in {2 ** attempt} seconds...")
            time.sleep(2 ** attempt)

    print("Failed to retrieve data after multiple attempts.")
    return None

# Retrieve AOI from bounding boxes
aoi = get_bounding_boxes(city_name, address_type)

if aoi is None:
    print("Failed to retrieve AOI for the given city and address type.")
    sys.exit(1)

# Convert the bounding box into an Earth Engine geometry
aoi_geom = ee.Geometry.Polygon(aoi)

# Create a Map and center it on the AOI
Map = geemap.Map()
Map.centerObject(aoi_geom, zoom=10)

# Assign variables for filtering the date and year range
DATE_RANGE = ee.Filter.dayOfYear(start_day_of_year, end_day_of_year)
YEAR_RANGE = ee.Filter.calendarRange(start_year, end_year, 'year')

# Set the basemap to display as satellite
Map.setOptions('SATELLITE')

# Define a variable to filter the Landsat Collection 2, Tier 1, Level 2 image collections
L8 = (ee.ImageCollection('LANDSAT/LC08/C02/T1_L2')
      .select(['ST_B10', 'QA_PIXEL'])
      .filterBounds(aoi_geom)
      .filter(DATE_RANGE)
      .filter(YEAR_RANGE)
      .map(lambda img: img.updateMask(img.select('QA_PIXEL').bitwiseAnd(1 << 3).Or(img.select('QA_PIXEL').bitwiseAnd(1 << 4)).Not())))

# Filter the collections by the CLOUD_COVER property
filtered_L8 = L8.filter(ee.Filter.lt('CLOUD_COVER', 20))

# Create a function using Landsat scale factors for deriving ST in Celsius
def applyScaleFactors(image):
    thermalBands = image.select('ST_B10').multiply(0.00341802).add(149.0).subtract(273.15)
    return image.addBands(thermalBands, None, True)

# Apply scale factors to the image collection
landsatST = filtered_L8.map(applyScaleFactors)

# Compute mean ST for each pixel throughout the filtered image collection
mean_LandsatST = landsatST.mean()

# Subset the imagery to the AOI
clip_mean_ST = mean_LandsatST.clip(aoi_geom)

# Define dynamic thresholds
mean_temp = clip_mean_ST.reduceRegion(
    reducer=ee.Reducer.mean(),
    geometry=aoi_geom,
    scale=30,
    maxPixels=1e9
).get('ST_B10').getInfo()

std_dev_temp = clip_mean_ST.reduceRegion(
    reducer=ee.Reducer.stdDev(),
    geometry=aoi_geom,
    scale=30,
    maxPixels=1e9
).get('ST_B10').getInfo()

heat_island_threshold_temp = mean_temp + 1 * std_dev_temp

def detect_heat_island_contours(image, threshold_temp):
    mask = image.gt(threshold_temp).selfMask()
    connected = mask.focal_max(kernel=ee.Kernel.circle(radius=7), iterations=8)
    vectors = connected.reduceToVectors(
        geometryType='polygon',
        reducer=ee.Reducer.countEvery(),
        scale=30,
        maxPixels=1e8,
        geometry=aoi_geom
    )
    return vectors

# Detect heat island contours
heat_island_contours = detect_heat_island_contours(clip_mean_ST.select('ST_B10'), heat_island_threshold_temp)

# Add the ST layer and contours to the map
Map.addLayer(clip_mean_ST, {
    'bands': 'ST_B10',
    'min': mean_temp - std_dev_temp,
    'max': mean_temp + 2 * std_dev_temp,
    'palette': ['blue', 'white', 'red']
}, "ST", True)

Map.addLayer(heat_island_contours, {'color': 'yellow'}, "Heat Island", True)

# Save the map to an HTML file
download_dir = 'landsat_export'
if not os.path.exists(download_dir):
    os.makedirs(download_dir)

html_file = os.path.join(download_dir, f'{city_name}_{start_year}_{end_year}_{start_month}_{end_month}_{address_type}.html')
Map.to_html(filename=html_file, title='Heat Island Map', width='100%', height='700px')
print(f"HTML file written successfully to {html_file}")
