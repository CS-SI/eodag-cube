# -*- coding: utf-8 -*-
# Copyright 2023, CS GROUP - France, https://www.csgroup.eu/
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

import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

import xarray as xr
from eodag.api.product._assets import Asset as Asset_core
from eodag.api.product._assets import AssetsDict as AssetsDict_core
from eodag.utils import DEFAULT_DOWNLOAD_TIMEOUT, DEFAULT_DOWNLOAD_WAIT, _deprecated

if TYPE_CHECKING:
    from contextlib import nullcontext

    from fsspec.core import OpenFile
    from rasterio.enums import Resampling
    from rasterio.env import Env
    from shapely.geometry.base import BaseGeometry
    from xarray import DataArray

logger = logging.getLogger("eodag-cube.api.product")


class AssetsDict(AssetsDict_core):
    """A UserDict object listing assets contained in a
    :class:`eodag.api.product._product.EOProduct` resulting from a search.

    :param product: Product resulting from a search
    :param args: (optional) Arguments used to init the dictionary
    :param kwargs: (optional) Additional named-arguments used to init the dictionary
    """

    def __setitem__(self, key: str, value: Dict[str, Any]) -> None:
        super(AssetsDict_core, self).__setitem__(key, Asset(self.product, key, value))


class Asset(Asset_core):
    """A UserDict object containg one of the assets of a
    :class:`eodag.api.product._product.EOProduct` resulting from a search.

    :param product: Product resulting from a search
    :param key: asset key
    :param args: (optional) Arguments used to init the dictionary
    :param kwargs: (optional) Additional named-arguments used to init the dictionary
    """

    @_deprecated("Use to_xarray instead")
    def get_data(
        self,
        crs: Optional[str] = None,
        resolution: Optional[float] = None,
        extent: Optional[Union[str, Dict[str, float], List[float], BaseGeometry]] = None,
        resampling: Optional[Resampling] = None,
        **rioxr_kwargs: Any,
    ) -> DataArray:
        """Retrieves asset raster data abstracted by the :class:`eodag.api.product._product.EOProduct`

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
           Use the :meth:`eodag_cube.api.product._assets.Asset.to_xarray` method instead.
        """
        band_pattern = rf"^{self.key}$"
        return self.product.get_data(
            band=band_pattern,
            crs=crs,
            resolution=resolution,
            extent=extent,
            resampling=resampling,
            **rioxr_kwargs,
        )

    def get_file_obj(
        self,
        wait: float = DEFAULT_DOWNLOAD_WAIT,
        timeout: float = DEFAULT_DOWNLOAD_TIMEOUT,
    ) -> OpenFile:
        """Open asset data using fsspec

        :param wait: (optional) If order is needed, wait time in minutes between two
                     order status check
        :param timeout: (optional) If order is needed, maximum time in minutes before
                        stop checking order status
        :returns: asset data file object
        """
        return self.product.get_file_obj(self.key, wait, timeout)

    def rio_env(self) -> Union[Env, nullcontext]:
        """Get rasterio environment

        :return: The rasterio environment
        """
        return self.product.rio_env(self.get("href"))

    def to_xarray(
        self,
        wait: float = DEFAULT_DOWNLOAD_WAIT,
        timeout: float = DEFAULT_DOWNLOAD_TIMEOUT,
        **xarray_kwargs: Any,
    ) -> xr.Dataset:
        """
        Return asset data as a :class:`xarray.Dataset`.

        :param wait: (optional) If order is needed, wait time in minutes between two
                     order status check
        :param timeout: (optional) If order is needed, maximum time in minutes before
                        stop checking order status
        :param xarray_kwargs: (optional) keyword arguments passed to :func:`xarray.open_dataset`
        :returns: Asset data as a :class:`xarray.Dataset`
        """
        xd = self.product.to_xarray(self.key, wait, timeout, **xarray_kwargs)
        if len(xd) > 1:
            logger.warning(f"Several Datasets were returned for {self.product} {self.key}: {xd.keys()}")
        return next(iter(xd.values()))
