# -*- coding: utf-8 -*-
# Copyright 2020, CS GROUP - France, http://www.c-s.fr
#
# This file is part of EODAG project
#     https://www.github.com/CS-SI/EODAG
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import os
import re
import warnings

import boto3
import rasterio

from eodag.api.product.drivers.base import DatasetDriver
from eodag.utils.exceptions import AddressNotFound, UnsupportedDatasetAddressScheme


class Sentinel2L1C(DatasetDriver):
    """Driver for Sentinel2 L1C product"""

    BAND_FILE_PATTERN_TPL = r"^.+_{band}\.jp2$"
    SPATIAL_RES_PER_BANDS = {
        "10m": ("B02", "B03", "B04", "B08"),
        "20m": ("B05", "B06", "B07", "B11", "B12", "B8A"),
        "60m": ("B01", "B09", "B10"),
        "TCI": ("TCI",),
    }

    def get_data_address(self, eo_product, band):
        """Compute the address of a subdataset for a Sentinel2 L1C product.

        The algorithm is as follows for a product on the local filesystem:
            - First compute the top level metadata file path by appending `MTD_MSIL1C.xml` to the
              ``eo_product.location``. Then open it as a `rasterio` dataset
            - Then mimics the shell command ``gdalinfo -sd n /path/metadata.xml`` to get the final address:
                - iterate through the subdataset addresses ('<DRIVER>:<path>/<mtd>.xml:<spatial-resolution>:<crs>')
                  detected by the rasterio dataset
                - open only the address for which the extracted spatial resolution maps to a tuple of bands including
                  the band of interest
            - Finally, filter the list of files of the previously opened rasterio dataset, to return the
              filesystem-like address that matches the band file pattern r'^.+_B01\\.jp2$' if band = 'B01' for
              example.

        See :func:`~eodag.api.product.drivers.base.DatasetDriver.get_data_address` to get help on the formal
        parameters.
        """
        product_location_scheme = eo_product.location.split("://")[0]
        if product_location_scheme == "file":
            top_level_mtd = os.path.join(
                re.sub(r"file://", "", eo_product.location), "MTD_MSIL1C.xml"
            )
            # Ignore the NotGeoreferencedWarning thrown by rasterio
            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore",
                    category=UserWarning,
                    message="Dataset has no geotransform set",
                )
                with rasterio.open(top_level_mtd) as dataset:
                    for address in dataset.subdatasets:
                        spatial_res = address.split(":")[-2]
                        if band in self.SPATIAL_RES_PER_BANDS[spatial_res]:
                            with rasterio.open(address) as subdataset:
                                band_file_pattern = re.compile(
                                    self.BAND_FILE_PATTERN_TPL.format(band=band)
                                )
                                for filename in filter(
                                    lambda f: band_file_pattern.match(f),
                                    subdataset.files,
                                ):
                                    return filename
                raise AddressNotFound
        if product_location_scheme == "s3":
            access_key, access_secret = eo_product.downloader_auth.authenticate()
            s3 = boto3.resource(
                "s3", aws_access_key_id=access_key, aws_secret_access_key=access_secret
            )
            bucket = s3.Bucket("sentinel-s2-l1c")
            for summary in bucket.objects.filter(
                Prefix=eo_product.location.split("s3://")[-1]
            ):
                if "{}.jp2".format(band) in summary.key:
                    return "s3://sentinel-s2-l1c/{}".format(summary.key)
            raise AddressNotFound
        raise UnsupportedDatasetAddressScheme(
            "eo product {} is accessible through a location scheme that is not yet "
            "supported by eodag: {}".format(eo_product, product_location_scheme)
        )
