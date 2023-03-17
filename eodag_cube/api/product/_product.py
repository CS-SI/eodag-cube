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
from contextlib import contextmanager

import numpy as np
import rasterio
import rioxarray
import xarray as xr
from rasterio.vrt import WarpedVRT

from eodag.api.product._product import EOProduct as EOProduct_core
from eodag.utils import get_geometry_from_various
from eodag.utils.exceptions import DownloadError, UnsupportedDatasetAddressScheme

logger = logging.getLogger("eodag.api.product")


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

    def get_data(
        self,
        band,
        crs=None,
        resolution=None,
        extent=None,
        resampling=None,
        **rioxr_kwargs,
    ):
        """Retrieves all or part of the raster data abstracted by the :class:`EOProduct`

        :param band: The band of the dataset to retrieve (e.g.: 'B01')
        :type band: str
        :param crs: (optional) The coordinate reference system in which the dataset should be returned
        :type crs: str
        :param resolution: (optional) The resolution in which the dataset should be returned
                            (given in the unit of the crs)
        :type resolution: float
        :param extent: (optional) The coordinates on which to zoom, matching the given CRS. Can be defined in
                    different ways (its bounds will be used):

                    * with a Shapely geometry object:
                      :class:`shapely.geometry.base.BaseGeometry`
                    * with a bounding box (dict with keys: "lonmin", "latmin", "lonmax", "latmax"):
                      ``dict.fromkeys(["lonmin", "latmin", "lonmax", "latmax"])``
                    * with a bounding box as list of float:
                      ``[lonmin, latmin, lonmax, latmax]``
                    * with a WKT str

        :type extent: Union[str, dict, shapely.geometry.base.BaseGeometry]
        :param resampling: (optional) Warp resampling algorithm passed to :class:`rasterio.vrt.WarpedVRT`
        :type resampling: Resampling
        :param rioxr_kwargs: kwargs passed to ``rioxarray.open_rasterio()``
        :type rioxr_kwargs: dict
        :returns: The numeric matrix corresponding to the sub dataset or an empty
                    array if unable to get the data
        :rtype: xarray.DataArray
        """
        fail_value = xr.DataArray(np.empty(0))
        try:
            logger.debug("Getting data address")
            dataset_address = self.driver.get_data_address(self, band)
        except UnsupportedDatasetAddressScheme:
            logger.warning(
                "Eodag does not support getting data from distant sources by now. "
                "Falling back to first downloading the product and then getting the "
                "data..."
            )
            try:
                path_of_downloaded_file = self.download(extract=True)
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

        clip_geom = (
            get_geometry_from_various(geometry=extent) if extent else self.geometry
        )
        clip_bounds = clip_geom.bounds
        minx, miny, maxx, maxy = clip_bounds

        # rasterio/gdal needed env variables for auth
        gdal_env = self._get_rio_env(dataset_address)

        warped_vrt_args = {}
        if crs is not None:
            warped_vrt_args["crs"] = crs
        if resampling is not None:
            warped_vrt_args["resampling"] = resampling

        @contextmanager
        def pass_resource(resource, **kwargs):
            yield resource

        if warped_vrt_args:
            warped_vrt_class = WarpedVRT
        else:
            warped_vrt_class = pass_resource

        logger.debug(f"Getting data from {dataset_address}")

        try:
            with rasterio.Env(**gdal_env):
                with rasterio.open(dataset_address) as src:
                    with warped_vrt_class(src, **warped_vrt_args) as vrt:
                        da = rioxarray.open_rasterio(vrt, **rioxr_kwargs)
                        if extent:
                            da = da.rio.clip_box(
                                minx=minx, miny=miny, maxx=maxx, maxy=maxy
                            )
                        if resolution:
                            height = int((maxy - miny) / resolution)
                            width = int((maxx - minx) / resolution)
                            out_shape = (height, width)

                            reproject_args = {}
                            if crs is not None:
                                reproject_args["dst_crs"] = crs
                            if resampling is not None:
                                reproject_args["resampling"] = resampling

                            da = da.rio.reproject(
                                shape=out_shape,
                                **reproject_args,
                            )
                        return da
        except Exception as e:
            logger.error(e)
            return fail_value

    def _get_rio_env(self, dataset_address):
        """Get rasterio environement variables needed for data access.

        :param dataset_address: address of the data to read
        :type dataset_address: str

        :return: The rasterio environement variables
        :rtype: dict
        """
        product_location_scheme = dataset_address.split("://")[0]
        if product_location_scheme == "s3" and hasattr(
            self.downloader, "get_bucket_name_and_prefix"
        ):
            bucket_name, prefix = self.downloader.get_bucket_name_and_prefix(
                self, dataset_address
            )
            auth_dict = self.downloader_auth.authenticate()
            return {
                "session": rasterio.session.AWSSession(
                    **self.downloader.get_rio_env(bucket_name, prefix, auth_dict)
                )
            }
        else:
            return {}

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
