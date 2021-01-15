# -*- coding: utf-8 -*-
# Copyright 2021, CS GROUP - France, http://www.c-s.fr
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
import logging

import numpy
import rasterio
import xarray as xr
from rasterio.enums import Resampling
from rasterio.vrt import WarpedVRT

from eodag.api.product._product import EOProduct as EOProduct_core
from eodag.utils.exceptions import DownloadError, UnsupportedDatasetAddressScheme

logger = logging.getLogger("eodag_cube.api.product")


class EOProduct(EOProduct_core):
    """A wrapper around an Earth Observation Product originating from a search.

    Every Search plugin instance must build an instance of this class for each of
    the result of its query method, and return a list of such instances. A EOProduct
    has a `location` attribute that initially points to its remote location, but is
    later changed to point to its path on the filesystem when the product has been
    downloaded. It also has a `remote_location` that always points to the remote
    location, so that the product can be downloaded at anytime if it is deleted from
    the filesystem. An EOProduct instance also has a reference to the search
    parameters that led to its creation.

    :param provider: The provider from which the product originates
    :type provider: str
    :param properties: The metadata of the product
    :type properties: dict

    .. note::
        The geojson spec `enforces <https://github.com/geojson/draft-geojson/pull/6>`_
        the expression of geometries as
        WGS84 CRS (EPSG:4326) coordinates and EOProduct is intended to be transmitted
        as geojson between applications. Therefore it stores geometries in the before
        mentioned CRS.
    """

    def __init__(self, *args, **kwargs):
        super(EOProduct, self).__init__(*args, **kwargs)

    def get_data(self, crs, resolution, band, extent):
        """Retrieves all or part of the raster data abstracted by the :class:`EOProduct`

        :param crs: The coordinate reference system in which the dataset should be
                    returned
        :type crs: str
        :param resolution: The resolution in which the dataset should be returned
                            (given in the unit of the crs)
        :type resolution: float
        :param band: The band of the dataset to retrieve (e.g.: 'B01')
        :type band: str
        :param extent: The coordinates on which to zoom as a tuple
                        (min_x, min_y, max_x, max_y) in the given `crs`
        :type extent: (float, float, float, float)
        :returns: The numeric matrix corresponding to the sub dataset or an empty
                    array if unable to get the data
        :rtype: xarray.DataArray
        """
        fail_value = xr.DataArray(numpy.empty(0))
        try:
            dataset_address = self.driver.get_data_address(self, band)
        except UnsupportedDatasetAddressScheme:
            logger.warning(
                "Eodag does not support getting data from distant sources by now. "
                "Falling back to first downloading the product and then getting the "
                "data..."
            )
            try:
                path_of_downloaded_file = self.download()
            except (RuntimeError, DownloadError):
                import traceback

                logger.warning(
                    "Error while trying to download the product:\n %s",
                    traceback.format_exc(),
                )
                logger.warning(
                    "There might be no download plugin registered for this EO product. "
                    "Try performing: product.register_downloader(download_plugin, "
                    "auth_plugin) before trying to call product.get_data(...)"
                )
                return fail_value
            if not path_of_downloaded_file:
                return fail_value
            dataset_address = self.driver.get_data_address(self, band)
        min_x, min_y, max_x, max_y = extent
        height = int((max_y - min_y) / resolution)
        width = int((max_x - min_x) / resolution)
        out_shape = (width, height)
        with rasterio.open(dataset_address) as src:
            with WarpedVRT(src, crs=crs, resampling=Resampling.bilinear) as vrt:
                array = vrt.read(
                    1,
                    window=vrt.window(*extent),
                    out_shape=out_shape,
                    resampling=Resampling.bilinear,
                )
                return xr.DataArray(array)

    def encode(self, raster, encoding="protobuf"):
        """Encode the subset to a network-compatible format.
        :param raster: The raster data to encode
        :type raster: xarray.DataArray
        :param encoding: The encoding of the export
        :type encoding: str
        :return: The data encoded in the specified encoding
        :rtype: bytes
        """
        # If no encoding return an empty byte
        if not encoding:
            logger.warning("Trying to encode a raster without specifying an encoding")
            return b""
        strategy = getattr(self, "_{encoding}".format(**locals()), None)
        if strategy:
            return strategy(raster)
        logger.error("Unknown encoding: %s", encoding)
        return b""

    def _protobuf(self, raster):
        """Google's Protocol buffers encoding strategy.
        :param raster: The raster to encode
        :type raster: xarray.DataArray
        :returns: The raster data represented by this subset in protocol buffers
                    encoding
        :rtype: bytes
        """
        from eodag_cube.api.product.protobuf import eo_product_pb2

        subdataset = eo_product_pb2.EOProductSubdataset()
        subdataset.id = self.properties["id"]
        subdataset.producer = self.provider
        subdataset.product_type = self.product_type
        subdataset.platform = self.properties["platformSerialIdentifier"]
        subdataset.sensor = self.properties["instrument"]
        data = subdataset.data
        data.array.extend(list(raster.values.flatten().astype(int)))
        data.shape.extend(list(raster.values.shape))
        data.dtype = raster.values.dtype.name
        return subdataset.SerializeToString()
