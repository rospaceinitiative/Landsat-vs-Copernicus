import xarray as xr  # Library for handling and analyzing multidimensional arrays, such as NetCDF datasets
import os

base_path = "copernicus_data"  

for root, dirs, files in os.walk(base_path):
    for file in files:
        # Look for the specific NetCDF file that contains LST data
        if file == "LST_in.nc":
            file_path = os.path.join(root, file)  # Get the complete file path
            print(f"Checking variables in {file_path}")
            # Open the NetCDF dataset to examine its structure and variables
            with xr.open_dataset(file_path) as ds:
                print(ds)  # Print the dataset structure, showing variable names, dimensions, and attributes
