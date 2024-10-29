import xarray as xr
import os

# Path to the extracted NetCDF files
base_path = "downloaded_products"  # Adjust if needed

for root, dirs, files in os.walk(base_path):
    for file in files:
        if file == "LST_in.nc":
            file_path = os.path.join(root, file)
            print(f"Checking variables in {file_path}")
            with xr.open_dataset(file_path) as ds:
                print(ds)  # Prints the dataset structure to see variable names
