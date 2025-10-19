import geemap.core as geemap

class S2Cloudless():
    def __init__(self, ee):
        self.ee = ee


    def _get_s2_sr_cld_col(self, aoi, start_date, end_date, cloud_filter=60):
        # Import and filter S2 SR.
        s2_sr_col = (self.ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
            .filterBounds(aoi)
            .filterDate(start_date, end_date)
            .filter(self.ee.Filter.lte('CLOUDY_PIXEL_PERCENTAGE', cloud_filter)))

        # Import and filter s2cloudless.
        s2_cloudless_col = (self.ee.ImageCollection('COPERNICUS/S2_CLOUD_PROBABILITY')
            .filterBounds(aoi)
            .filterDate(start_date, end_date))

        # Join the filtered s2cloudless collection to the SR collection by the 'system:index' property.
        return self.ee.ImageCollection(self.ee.Join.saveFirst('s2cloudless').apply(**{
            'primary': s2_sr_col,
            'secondary': s2_cloudless_col,
            'condition': self.ee.Filter.equals(**{
                'leftField': 'system:index',
                'rightField': 'system:index'
            })
        }))
        
        
    def _add_cloud_bands(self, img, cloud_probability_threshold=50):
        # Get s2cloudless image, subset the probability band.
        cld_prb = self.ee.Image(img.get('s2cloudless')).select('probability')

        # Condition s2cloudless by the probability threshold value.
        is_cloud = cld_prb.gt(cloud_probability_threshold).rename('clouds')

        # Add the cloud probability layer and cloud mask as image bands.
        return img.addBands(self.ee.Image([cld_prb, is_cloud]))

    def _add_shadow_bands(self, img, nir_dark_threshold=0.15, cloud_projection_distance=1):
        # Identify water pixels from the SCL band.
        not_water = img.select('SCL').neq(6)

        # Identify dark NIR pixels that are not water (potential cloud shadow pixels).
        SR_BAND_SCALE = 1e4
        dark_pixels = img.select('B8').lt(nir_dark_threshold*SR_BAND_SCALE).multiply(not_water).rename('dark_pixels')

        # Determine the direction to project cloud shadow from clouds (assumes UTM projection).
        shadow_azimuth = self.ee.Number(90).subtract(self.ee.Number(img.get('MEAN_SOLAR_AZIMUTH_ANGLE')))

        # Project shadows from clouds for the distance specified by the cloud_projection_distance input.
        cld_proj = (img.select('clouds').directionalDistanceTransform(shadow_azimuth, cloud_projection_distance*10)
            .reproject(**{'crs': img.select(0).projection(), 'scale': 100})
            .select('distance')
            .mask()
            .rename('cloud_transform'))

        # Identify the intersection of dark pixels with cloud shadow projection.
        shadows = cld_proj.multiply(dark_pixels).rename('shadows')

        # Add dark pixels, cloud projection, and identified shadows as image bands.
        return img.addBands(self.ee.Image([dark_pixels, cld_proj, shadows]))
    
    def _add_cld_shdw_mask(self, img, cloud_probability_threshold=50, nir_dark_threshold=0.15, buffer=50, cloud_projection_distance=1):
        # Add cloud component bands.
        img_cloud = self._add_cloud_bands(img, cloud_probability_threshold)

        # Add cloud shadow component bands.
        img_cloud_shadow = self._add_shadow_bands(img_cloud, nir_dark_threshold, cloud_projection_distance)

        # Combine cloud and shadow mask, set cloud and shadow as value 1, else 0.
        is_cld_shdw = img_cloud_shadow.select('clouds').add(img_cloud_shadow.select('shadows')).gt(0)

        # Remove small cloud-shadow patches and dilate remaining pixels by buffer input.
        # 20 m scale is for speed, and assumes clouds don't require 10 m precision.
        is_cld_shdw = (is_cld_shdw.focalMin(2).focalMax(buffer*2/20)
            .reproject(**{'crs': img.select([0]).projection(), 'scale': 20})
            .rename('cloudmask'))

        # Add the final cloud-shadow mask to the image.
        return img_cloud_shadow.addBands(is_cld_shdw)

    def apply_cld_shdw_mask(self, img):
        # Subset the cloudmask band and invert it so clouds/shadow are 0, else 1.
        not_cld_shdw = img.select('cloudmask').Not()

        # Subset reflectance bands and update their masks, return the result.
        return img.select('B.*').updateMask(not_cld_shdw)

    def cloud_col(self, aoi, start_date, end_date, buffer=50, cloud_filter=60):
        col = self._get_s2_sr_cld_col(aoi, start_date, end_date, cloud_filter)
        col_mask = col.map(lambda img: self._add_cld_shdw_mask(img, buffer=buffer))
        # Mosaic the image collection.
        return col_mask.mosaic()

    def cloud_layers_map(self, aoi, start_date, end_date, buffer=50, cloud_filter=60):
        # col = self._get_s2_sr_cld_col(aoi, start_date, end_date, cloud_filter)
        # col_mask = col.map(lambda img: self._add_cld_shdw_mask(img, buffer=buffer))
        # # Mosaic the image collection.
        # img = col_mask.mosaic()
        img = self.cloud_col(aoi, start_date, end_date, buffer=buffer, cloud_filter=cloud_filter)

        # Subset layers and prepare them for display.
        clouds = img.select('clouds').selfMask()
        shadows = img.select('shadows').selfMask()
        dark_pixels = img.select('dark_pixels').selfMask()
        probability = img.select('probability')
        cloudmask = img.select('cloudmask').selfMask()
        cloud_transform = img.select('cloud_transform')

        # Create a geemap Map object centered on AOI.
        m = geemap.Map(ee_initialize=False)
        m.centerObject(aoi, 12)

        # Add layers
        m.addLayer(img, {'bands': ['B4', 'B3', 'B2'], 'min': 0, 'max': 2500, 'gamma': 1.1}, 'S2 image')
        m.addLayer(probability, {'min': 0, 'max': 100}, 'probability (cloud)')
        m.addLayer(clouds, {'palette': ['e056fd']}, 'clouds')
        m.addLayer(cloud_transform, {'min': 0, 'max': 1, 'palette': ['white', 'black']}, 'cloud_transform')
        m.addLayer(dark_pixels, {'palette': ['red']}, 'dark_pixels')
        m.addLayer(shadows, {'palette': ['yellow']}, 'shadows')
        m.addLayer(cloudmask, {'palette': ['orange']}, 'cloudmask')

        return m
    
    def cloud_free_col(self, aoi, start_date, end_date, buffer=50, cloud_filter=60):
        col = self._get_s2_sr_cld_col(aoi, start_date, end_date, cloud_filter)
        return (col.map(
                                lambda img: self._add_cld_shdw_mask(img, buffer=buffer))
                             .map(self.apply_cld_shdw_mask)
                             .median())
    
    def cloud_free_map(self, aoi, start_date, end_date, buffer=50, cloud_filter=60):
        # col = self._get_s2_sr_cld_col(aoi, start_date, end_date, cloud_filter)
        # s2_sr_median = (col.map(
        #                         lambda img: self._add_cld_shdw_mask(img, buffer=buffer))
        #                      .map(self.apply_cld_shdw_mask)
        #                      .median())
        col = self.cloud_free_col(aoi, start_date, end_date, buffer=buffer, cloud_filter=cloud_filter)
        m = geemap.Map(ee_initialize=False)
        m.centerObject(aoi, 12)
        m.addLayer(col, {'bands': ['B4', 'B3', 'B2'], 'min': 0, 'max': 2500, 'gamma': 1.1}, 'S2 image')
        return m