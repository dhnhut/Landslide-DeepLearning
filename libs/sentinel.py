
import os
import pandas as pd
import urllib.request
import logging
import zipfile
import tempfile

def mask_s2_clouds(image):
  """Masks clouds in a Sentinel-2 image using the QA band.

  Args:
      image (ee.Image): A Sentinel-2 image.

  Returns:
      ee.Image: A cloud-masked Sentinel-2 image.
  """
  qa = image.select('QA60')

  # Bits 10 and 11 are clouds and cirrus, respectively.
  cloud_bit_mask = 1 << 10
  cirrus_bit_mask = 1 << 11

  # Both flags should be set to zero, indicating clear conditions.
  mask = (
      qa.bitwiseAnd(cloud_bit_mask)
      .eq(0)
      .And(qa.bitwiseAnd(cirrus_bit_mask).eq(0))
  )

  return image.updateMask(mask).divide(10000)

def get_sentinel_image_thumbnail(
    ee,
    s2cloudless,
    event,
    idx,
    out_dir,
    start_date_offset=60,
    end_date_offset=0,
    buffer=50,
    cloud_filter=30,
    
):
    vis_params = {'bands': ['B4', 'B3', 'B2'], 'min': 0, 'max': 2500, 'gamma': 1.1}

    _point = event.geometry.centroid
    _lon = _point.x
    _lat = _point.y
    _point_geom = ee.Geometry.Point(_lon, _lat)
    _aoi = _point_geom.buffer(100)
    thumb_params = {
        'dimensions': 256,
        'region': _aoi,
        'format': 'png',
    }
    _start_date = (
        event['dateoccurence'].date() + pd.Timedelta(days=start_date_offset)
    ).strftime("%Y-%m-%d")
    
    _end_date = (
        event['dateoccurence'].date() + pd.Timedelta(days=end_date_offset)
    ).strftime("%Y-%m-%d")
    
    filename = f"{idx}_{_lon}_{_lat}_{_start_date}_{_end_date}"
    filename_tif = f"{filename}.tif"
    filename_png = f"{filename}.png"

    # ensure output directory exists and save thumbnail
    os.makedirs(out_dir, exist_ok=True)
    
    img_dir = os.path.join(out_dir, 'tif')
    rgb_dir = os.path.join(out_dir, 'rgb')
    marks_dir = os.path.join(out_dir, 'marks')
    os.makedirs(img_dir, exist_ok=True)
    os.makedirs(rgb_dir, exist_ok=True)
    os.makedirs(marks_dir, exist_ok=True)

    filepath_tif = os.path.join(img_dir, filename_tif)
    filepath_rgb = os.path.join(rgb_dir, filename_png)
    filepath_with_marker = os.path.join(marks_dir, filename_png)
    if os.path.exists(filepath_tif) and \
        os.path.exists(filepath_rgb) and \
        os.path.exists(filepath_with_marker):
        return filepath_tif, filepath_rgb, filepath_with_marker

    image = s2cloudless.cloud_free_col(_aoi, _start_date, _end_date, buffer=buffer, cloud_filter=cloud_filter)

    # Select only RGB bands to match the point image
    rgb_image = image.select(['B4', 'B3', 'B2'])
    
    # Create a red point marker
    point_feature = ee.FeatureCollection([ee.Feature(_point_geom)])
    point_image = point_feature.style(**{'color': 'red', 'pointSize': 5, 'width': 2})
    
    # Blend the point marker with the RGB satellite image
    image_with_marker = rgb_image.blend(point_image)
    
    # url = rgb_image.getThumbURL({**vis_params, **thumb_params})
    export_params = {
        'scale': 10,  # 10m resolution for Sentinel-2
        'region': _aoi,
        'fileFormat': 'GeoTIFF',
        'formatOptions': {'cloudOptimized': True}
    }
    url = image.getDownloadURL(export_params)
    url_rgb = rgb_image.getThumbURL({**vis_params, **thumb_params})
    url_with_marker = image_with_marker.getThumbURL({**vis_params, **thumb_params})

    try:
        # Download the ZIP file to a temporary location
        zip_filepath = filepath_tif + '.zip'
        urllib.request.urlretrieve(url, zip_filepath)
        
        # Extract the GeoTIFF from the ZIP archive
        with zipfile.ZipFile(zip_filepath, 'r') as zip_ref:
            # Earth Engine ZIP contains a single .tif file
            tif_files = [f for f in zip_ref.namelist() if f.endswith('.tif')]
            if not tif_files:
                print(f"No .tif file found in ZIP for index {idx}")
                os.remove(zip_filepath)
                return None, None, None
            
            # Extract the first (and typically only) .tif file
            tif_filename = tif_files[0]
            zip_ref.extract(tif_filename, img_dir)
            
            # Rename the extracted file to our desired filename
            extracted_path = os.path.join(img_dir, tif_filename)
            if extracted_path != filepath_tif:
                os.rename(extracted_path, filepath_tif)

        # Clean up the ZIP file
        os.remove(zip_filepath)

        urllib.request.urlretrieve(url_rgb, filepath_rgb)

        # Download the marker image
        urllib.request.urlretrieve(url_with_marker, filepath_with_marker)
        
        # update filename to the saved path for display
        filename = filepath_tif
    except Exception as e:
        print(f"Failed to download thumbnail for index {idx}: {e}")
        # Clean up partial files if they exist
        if os.path.exists(zip_filepath):
            os.remove(zip_filepath)
        return None, None, None

    return filepath_tif, filepath_rgb, filepath_with_marker