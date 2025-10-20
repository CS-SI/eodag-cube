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
from contextlib import nullcontext
from pathlib import Path
from typing import Any, Iterable, Optional, Union, cast
from urllib.parse import urlparse

import fsspec
import rasterio
from boto3 import Session
from boto3.resources.base import ServiceResource
from eodag.api.product._product import EOProduct as EOProduct_core
from eodag.api.product.metadata_mapping import OFFLINE_STATUS
from eodag.plugins.authentication.aws_auth import AwsAuth
from eodag.utils import (
    DEFAULT_DOWNLOAD_TIMEOUT,
    DEFAULT_DOWNLOAD_WAIT,
    USER_AGENT,
)
from eodag.utils.exceptions import UnsupportedDatasetAddressScheme
from fsspec.core import OpenFile
from requests import PreparedRequest
from requests.auth import AuthBase
from requests.structures import CaseInsensitiveDict

from eodag_cube.api.product._assets import AssetsDict
from eodag_cube.types import XarrayDict
from eodag_cube.utils.exceptions import DatasetCreationError
from eodag_cube.utils.xarray import try_open_dataset

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
    :ivar collection: The collection
    :vartype collection: str
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

    def _get_rio_env(self, dataset_address: str) -> dict[str, Any]:
        """Get rasterio environment variables needed for data access.

        :param dataset_address: address of the data to read
        :return: The rasterio environment variables
        """
        product_location_scheme = dataset_address.split("://")[0]
        if "s3" in product_location_scheme and isinstance(self.downloader_auth, AwsAuth):
            rio_env_dict = {"session": rasterio.session.AWSSession(**self.downloader_auth.get_rio_env())}
            auth = self.downloader_auth.s3_resource
            if auth is None:
                auth = self.downloader_auth.authenticate()

            if endpoint_url := auth.meta.client.meta.endpoint_url:
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
        if self.properties.get("order:status") == OFFLINE_STATUS and hasattr(self.downloader, "order"):
            self.downloader.order(self, auth, wait=wait, timeout=timeout)

        # default url and headers
        try:
            url = self.assets[asset_key]["href"] if asset_key else self.location
        except KeyError as e:
            raise DatasetCreationError(f"{asset_key} not found in {self} assets") from e
        headers = {**USER_AGENT}

        if isinstance(auth, ServiceResource) and isinstance(self.downloader_auth, AwsAuth):
            auth_kwargs: dict[str, Any] = dict()
            # AwsAuth
            if s3_endpoint := getattr(self.downloader_auth.config, "s3_endpoint", None):
                auth_kwargs["client_kwargs"] = {"endpoint_url": s3_endpoint}
            if creds := cast(Session, self.downloader_auth.s3_session).get_credentials():
                auth_kwargs["key"] = creds.access_key
                auth_kwargs["secret"] = creds.secret_key
                if creds.token:
                    auth_kwargs["token"] = creds.token
                if requester_pays := getattr(self.downloader_auth.config, "requester_pays", False):
                    auth_kwargs["requester_pays"] = requester_pays
            else:
                auth_kwargs["anon"] = True
            return {"path": url, **auth_kwargs}

        if isinstance(auth, AuthBase):
            # update url and headers with auth
            req = PreparedRequest()
            req.url = url
            req.headers = CaseInsensitiveDict(headers)

            auth_req = auth(req) if auth else req

            return {"path": auth_req.url, "headers": auth_req.headers}

        return {"path": url}

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
