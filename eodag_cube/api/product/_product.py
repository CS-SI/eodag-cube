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
from __future__ import annotations

import concurrent.futures
import logging
import os
from contextlib import contextmanager, nullcontext
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable, Optional, Union
from urllib.parse import urlparse

import fsspec
import numpy as np
import rasterio
import rioxarray
import xarray as xr
from eodag.api.product._product import EOProduct as EOProduct_core
from eodag.api.product.metadata_mapping import OFFLINE_STATUS
from eodag.plugins.download.aws import AwsDownload
from eodag.utils import (
    DEFAULT_DOWNLOAD_TIMEOUT,
    DEFAULT_DOWNLOAD_WAIT,
    USER_AGENT,
    _deprecated,
    get_geometry_from_various,
)
from eodag.utils.exceptions import DownloadError, UnsupportedDatasetAddressScheme
from fsspec.core import OpenFile
from rasterio.vrt import WarpedVRT
from requests import PreparedRequest
from requests.structures import CaseInsensitiveDict

from eodag_cube.api.product._assets import AssetsDict
from eodag_cube.types import XarrayDict
from eodag_cube.utils.exceptions import DatasetCreationError
from eodag_cube.utils.xarray import try_open_dataset

if TYPE_CHECKING:
    # from fsspec.core import OpenFile
    from rasterio.enums import Resampling
    from shapely.geometry.base import BaseGeometry
    from xarray import DataArray, Dataset

logger = logging.getLogger("eodag-cube.api.product")


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
    :param properties: The metadata of the product
    :ivar product_type: The product type
    :vartype product_type: str
    :ivar location: The path to the product, either remote or local if downloaded
    :vartype location: str
    :ivar remote_location: The remote path to the product
    :vartype remote_location: str
    :ivar search_kwargs: The search kwargs used by eodag to search for the product
    :vartype search_kwargs: Any
    :ivar geometry: The geometry of the product
    :vartype geometry: :class:`shapely.geometry.base.BaseGeometry`
    :ivar search_intersection: The intersection between the product's geometry
                               and the search area.
    :vartype search_intersection: :class:`shapely.geometry.base.BaseGeometry` or None

    .. note::
        The geojson spec `enforces <https://github.com/geojson/draft-geojson/pull/6>`_
        the expression of geometries as
        WGS84 CRS (EPSG:4326) coordinates and EOProduct is intended to be transmitted
        as geojson between applications. Therefore it stores geometries in the before
        mentioned CRS.
    """

    def __init__(self, provider: str, properties: dict[str, Any], **kwargs: Any) -> None:
        super(EOProduct, self).__init__(provider=provider, properties=properties, **kwargs)
        core_assets_data = self.assets.data
        self.assets = AssetsDict(self)
        self.assets.update(core_assets_data)

    @_deprecated("Use to_xarray instead")
    def get_data(
        self,
        band: str,
        crs: Optional[str] = None,
        resolution: Optional[float] = None,
        extent: Optional[Union[str, dict[str, float], list[float], BaseGeometry]] = None,
        resampling: Optional[Resampling] = None,
        **rioxr_kwargs: Any,
    ) -> Union[Dataset, DataArray, list[Dataset]]:
        """Retrieves all or part of the raster data abstracted by the :class:`EOProduct`

        :param band: The band of the dataset to retrieve (e.g.: 'B01')
        :param crs: (optional) The coordinate reference system in which the dataset should be returned
        :param resolution: (optional) The resolution in which the dataset should be returned
                            (given in the unit of the crs)
        :param extent: (optional) The coordinates on which to zoom, matching the given CRS. Can be defined in
                    different ways (its bounds will be used):

                    * with a Shapely geometry object:
                      :class:`shapely.geometry.base.BaseGeometry`
                    * with a bounding box (dict with keys: "lonmin", "latmin", "lonmax", "latmax"):
                      ``dict.fromkeys(["lonmin", "latmin", "lonmax", "latmax"])``
                    * with a bounding box as list of float:
                      ``[lonmin, latmin, lonmax, latmax]``
                    * with a WKT str

        :param resampling: (optional) Warp resampling algorithm passed to :class:`rasterio.vrt.WarpedVRT`
        :param rioxr_kwargs: kwargs passed to :func:`rioxarray.open_rasterio`
        :returns: The numeric matrix corresponding to the sub dataset or an empty
                    array if unable to get the data

        .. deprecated:: 0.6.0b1
           Use the :meth:`eodag_cube.api.product._product.EOProduct.to_xarray` method instead.
        """
        fail_value = xr.DataArray(np.empty(0))
        try:
            logger.debug("Getting data address")
            dataset_address = self.driver.legacy.get_data_address(self, band)
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
            dataset_address = self.driver.legacy.get_data_address(self, band)

        clip_geom = get_geometry_from_various(geometry=extent) if extent else self.geometry
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
        def pass_resource(resource: Any, **kwargs: Any) -> Any:
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
                        if extent and hasattr(da, "rio"):
                            da = da.rio.clip_box(minx=minx, miny=miny, maxx=maxx, maxy=maxy)
                        if resolution and hasattr(da, "rio"):
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

    def _get_rio_env(self, dataset_address: str) -> dict[str, Any]:
        """Get rasterio environment variables needed for data access.

        :param dataset_address: address of the data to read
        :return: The rasterio environment variables
        """
        product_location_scheme = dataset_address.split("://")[0]
        if "s3" in product_location_scheme and isinstance(self.downloader, AwsDownload):
            bucket_name, prefix = self.downloader.get_product_bucket_name_and_prefix(self, dataset_address)
            auth_dict = self.downloader_auth.authenticate() if self.downloader_auth else {}
            rio_env_dict = (
                {"session": rasterio.session.AWSSession(**self.downloader.get_rio_env(bucket_name, prefix, auth_dict))}
                if prefix is not None and isinstance(auth_dict, dict)
                else {}
            )

            endpoint_url = getattr(self.downloader.config, "s3_endpoint", None)
            if endpoint_url:
                aws_s3_endpoint = endpoint_url.split("://")[-1]
                rio_env_dict.update(
                    AWS_S3_ENDPOINT=aws_s3_endpoint,
                    AWS_HTTPS="YES",
                    AWS_VIRTUAL_HOSTING="FALSE",
                )
            return rio_env_dict
        else:
            return {}

    def _get_storage_options(
        self,
        asset_key: Optional[str] = None,
        wait: float = DEFAULT_DOWNLOAD_WAIT,
        timeout: float = DEFAULT_DOWNLOAD_TIMEOUT,
    ) -> dict[str, Any]:
        """
        Get fsspec storage_options keyword arguments
        """
        auth = self.downloader_auth.authenticate() if self.downloader_auth else None
        if self.downloader is None:
            return {}

        # order if product is offline
        if self.properties.get("storageStatus") == OFFLINE_STATUS and hasattr(self.downloader, "order"):
            self.downloader.order(self, auth, wait=wait, timeout=timeout)

        # default url and headers
        try:
            url = self.assets[asset_key]["href"] if asset_key else self.location
        except KeyError as e:
            raise DatasetCreationError(f"{asset_key} not found in {self} assets") from e
        headers = {**USER_AGENT}

        if isinstance(auth, dict):
            auth_kwargs: dict[str, Any] = dict()
            # AwsAuth
            s3_endpoint = getattr(self.downloader.config, "s3_endpoint", None)
            if s3_endpoint is not None:
                auth_kwargs["client_kwargs"] = {"endpoint_url": self.downloader.config.s3_endpoint}
            if "aws_access_key_id" in auth:
                auth_kwargs["key"] = auth["aws_access_key_id"]
            if "aws_secret_access_key" in auth:
                auth_kwargs["secret"] = auth["aws_secret_access_key"]
            if "aws_session_token" in auth:
                auth_kwargs["token"] = auth["aws_session_token"]
            if "profile_name" in auth:
                auth_kwargs["profile"] = auth["profile_name"]
            return {"path": url, **auth_kwargs}

        # update url and headers with auth
        req = PreparedRequest()
        req.url = url
        req.headers = CaseInsensitiveDict(headers)

        auth_req = auth(req) if auth else req

        return {"path": auth_req.url, "headers": auth_req.headers}

    def get_file_obj(
        self,
        asset_key: Optional[str] = None,
        wait: float = DEFAULT_DOWNLOAD_WAIT,
        timeout: float = DEFAULT_DOWNLOAD_TIMEOUT,
    ) -> OpenFile:
        """Open data using fsspec

        :param asset_key: (optional) key of the asset. If not specified the whole
                          product will be opened
        :param wait: (optional) If order is needed, wait time in minutes between two
                     order status check
        :param timeout: (optional) If order is needed, maximum time in minutes before
                        stop checking order status
        :returns: product data file object
        """
        storage_options = self._get_storage_options(asset_key, wait, timeout)

        path = storage_options.pop("path", None)
        if path is None:
            raise UnsupportedDatasetAddressScheme(f"Could not get {self} path")

        protocol = fsspec.utils.get_protocol(path)

        if protocol == "zip+s3":
            fs = fsspec.filesystem("s3", **storage_options)
            return OpenFile(fs, path)

        fs = fsspec.filesystem(protocol, **storage_options)
        return fs.open(path=path)

    def rio_env(self, dataset_address: Optional[str] = None) -> Union[rasterio.env.Env, nullcontext]:
        """Get rasterio environment

        :param dataset_address: address of the data to read
        :return: The rasterio environment
        """
        if dataset_address:
            if env_dict := self._get_rio_env(dataset_address):
                return rasterio.Env(**env_dict)
            return nullcontext()

        for asset in self.assets.values():
            cm = asset.rio_env()
            if not isinstance(cm, nullcontext):
                return cm
        return nullcontext()

    def _build_local_xarray_dict(self, local_path: str, **xarray_kwargs: Any) -> XarrayDict:
        """Build :class:`eodag_cube.types.XarrayDict` for local data

        :param local_path: local path to scan for data
        :param xarray_kwargs: (optional) keyword arguments passed to :func:`xarray.open_dataset`
        :returns: a dictionary of :class:`xarray.Dataset`
        """
        xarray_dict = XarrayDict()
        fs = fsspec.filesystem("file")

        if os.path.isfile(local_path):
            files = [
                local_path,
            ]
        else:
            files = [str(x) for x in Path(local_path).rglob("*") if x.is_file()]

        for file_path in files:
            if not os.path.isfile(file_path):
                continue
            file = fs.open(file_path)
            try:
                ds = try_open_dataset(file, **xarray_kwargs)
                key, _ = self.driver.guess_asset_key_and_roles(file_path, self)
                if key is not None:
                    xarray_dict[key] = ds
                    xarray_dict._files[key] = file
                else:
                    logger.debug(f"Could not guess asset key for {file_path}")
            except DatasetCreationError as e:
                logger.debug(e)

        return xarray_dict

    def to_xarray(
        self,
        asset_key: Optional[str] = None,
        wait: float = DEFAULT_DOWNLOAD_WAIT,
        timeout: float = DEFAULT_DOWNLOAD_TIMEOUT,
        roles: Iterable[str] = {"data", "data-mask"},
        **xarray_kwargs: Any,
    ) -> XarrayDict:
        """
        Return product data as a dictionary of :class:`xarray.Dataset`.

        :param asset_key: (optional) key of the asset. If not specified the whole
                          product data will be retrieved
        :param wait: (optional) If order is needed, wait time in minutes between two
                     order status check
        :param timeout: (optional) If order is needed, maximum time in minutes before
                        stop checking order status
        :param roles: (optional) roles of assets that must be fetched
        :param xarray_kwargs: (optional) keyword arguments passed to :func:`xarray.open_dataset`
        :returns: a dictionary of :class:`xarray.Dataset`
        """
        if asset_key is None and len(self.assets) > 0:
            # assets

            # have roles been set in assets ?
            roles_exist = any("roles" in a for a in self.assets.values())

            xd = XarrayDict()
            with concurrent.futures.ThreadPoolExecutor() as executor:
                futures = (
                    executor.submit(self.to_xarray, key, wait, timeout, **xarray_kwargs)
                    for key, asset in self.assets.items()
                    if roles
                    and asset.get("roles")
                    and any(r in asset["roles"] for r in roles)
                    or not roles
                    or not roles_exist
                )
                for future in concurrent.futures.as_completed(futures):
                    try:
                        future_xd = future.result()
                        xd.update(**future_xd)
                    except DatasetCreationError as e:
                        logger.debug(e)

            if xd:
                xd.sort()
                return xd

        # single file
        try:
            file = self.get_file_obj(asset_key, wait, timeout)
            # fix messy protocol with zip+s3 and ignore zip content after "!"
            base_file_for_env = (
                getattr(file, "full_name", file.path).replace("s3://zip+s3://", "zip+s3://").split("!")[0]
            )
            gdal_env = self._get_rio_env(base_file_for_env)
            with rasterio.Env(**gdal_env):
                ds = try_open_dataset(file, **xarray_kwargs)
            # set attributes
            ds.attrs.update(**self.properties)
            xd_key = asset_key or "data"
            xd = XarrayDict({xd_key: ds})
            xd._files[xd_key] = file
            return xd

        except (
            UnsupportedDatasetAddressScheme,
            OSError,
            DatasetCreationError,
        ) as e:
            logger.debug(f"Cannot open {self} {asset_key if asset_key else ''}: {e}")

            # download the file and try again with local files
            path = self.download(asset=asset_key, wait=wait, timeout=timeout, extract=True)

            if asset_key is not None:
                # path is not asset-specific, find asset path
                # TODO: make download return asset path
                basename = urlparse(self.assets[asset_key]["href"]).path.strip("/").split("/")[-1]
                try:
                    path = str(next(Path(path).rglob(basename)))
                except StopIteration:
                    logger.debug(f"{basename} not found in {path}")

            xd = self._build_local_xarray_dict(path, **xarray_kwargs)
            if not xd:
                raise DatasetCreationError(
                    f"Could not build local XarrayDict for {self} {asset_key if asset_key else ''}"
                ) from None
            # set attributes
            for k in xd.keys():
                xd[k].attrs.update(**self.properties)
            # sort by keys
            xd.sort()

            return xd
