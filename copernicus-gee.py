import ee
import geemap
import datetime

# Authenticate to Earth Engine
service_account = 'copenricus-vs-landsat-workshop@ee-simoneldavid.iam.gserviceaccount.com'
credentials = ee.ServiceAccountCredentials(service_account, 'ee-simoneldavid-84d91d8a227c.json')
ee.Initialize(credentials)

# Define the Area of Interest (AOI) - Example: Rome bounding box
aoi = ee.Geometry.BBox(12.48, 41.88, 12.54, 41.92)

# Define date range for LST data
start_date = '2023-01-01'
end_date = '2023-01-31'

# Load Sentinel-3 SLSTR dataset and filter by date and AOI
lst_dataset = ee.ImageCollection("COPERNICUS/S3/SLSTR")
filtered_lst = lst_dataset.filterBounds(aoi).filterDate(start_date, end_date).select('LST')

# Compute the mean LST over the specified time range
mean_lst = filtered_lst.mean().clip(aoi)

# Define visualization parameters for LST (in Kelvin)
vis_params = {
    'min': 260,  # Adjust the range based on your area or analysis
    'max': 320,
    'palette': ['blue', 'green', 'yellow', 'orange', 'red']
}

# Create an interactive map
Map = geemap.Map(center=(41.9, 12.5), zoom=10)
Map.addLayer(mean_lst, vis_params, "Mean LST")
Map.addLayerControl()  # Add layer control to toggle layers on/off

# Save the map to an HTML file
output_file = "LST_map.html"
Map.to_html(outfile=output_file)
print(f"Map saved to {output_file}")
