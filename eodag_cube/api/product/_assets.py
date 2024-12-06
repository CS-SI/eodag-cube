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
from eodag.utils.exceptions import DownloadError, UnsupportedDatasetAddressScheme

if TYPE_CHECKING:
    from rasterio.enums import Resampling
    from shapely.geometry.base import BaseGeometry
    from xarray import DataArray


logger = logging.getLogger("eodag-cube.api.product")


class AssetsDict(AssetsDict_core):
    """A UserDict object listing assets contained in a
    :class:`~eodag.api.product._product.EOProduct` resulting from a search.

    :param product: Product resulting from a search
    :type product: :class:`~eodag.api.product._product.EOProduct`
    :param args: (optional) Arguments used to init the dictionary
    :type args: Any
    :param kwargs: (optional) Additional named-arguments used to init the dictionary
    :type kwargs: Any
    """

    def __setitem__(self, key: str, value: Dict[str, Any]) -> None:
        super(AssetsDict_core, self).__setitem__(key, Asset(self.product, key, value))


class Asset(Asset_core):
    """A UserDict object containg one of the assets of a
    :class:`~eodag.api.product._product.EOProduct` resulting from a search.

    :param product: Product resulting from a search
    :type product: :class:`~eodag.api.product._product.EOProduct`
    :param key: asset key
    :type key: str
    :param args: (optional) Arguments used to init the dictionary
    :type args: Any
    :param kwargs: (optional) Additional named-arguments used to init the dictionary
    :type kwargs: Any
    """

    def get_data(
        self,
        crs: Optional[str] = None,
        resolution: Optional[float] = None,
        extent: Optional[
            Union[str, Dict[str, float], List[float], BaseGeometry]
        ] = None,
        resampling: Optional[Resampling] = None,
        clip_reproject=True,
        **rioxr_kwargs: Any,
    ) -> DataArray:
        """Retrieves asset raster data abstracted by the :class:`EOProduct`

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
        :type rioxr_kwargs: Any
        :returns: The numeric matrix corresponding to the sub dataset or an empty
                    array if unable to get the data
        :rtype: xarray.DataArray
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

    def to_xarray(self, **kwargs):
        """
        Return asset as an xarray Dataset.

        Any keyword arguments passed will be forwarded to xarray.open_dataset.
        """
        try:
            logger.debug("Getting data address")
            dataset_address = self.product.driver.get_data_address(
                self.product, self.key
            )
        except UnsupportedDatasetAddressScheme:
            logger.warning(
                "Eodag does not support getting data from distant sources by now. "
                "Falling back to first downloading the product and then getting the "
                "data..."
            )
            try:
                self.product.download(extract=True)
            except (RuntimeError, DownloadError) as exc:
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
                raise exc
            dataset_address = self.driver.get_data_address(self, self.key)

        auth_info = self.product._get_rio_env(dataset_address)

        logger.debug(f"Getting data from {dataset_address}")
        try:
            ds = xr.open_dataset(dataset_address, backend_kwargs=auth_info, **kwargs)
            return ds
        except Exception as e:
            logger.error(e)
            raise e
