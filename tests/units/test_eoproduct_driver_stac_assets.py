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

import os
from contextlib import contextmanager

from rasterio.crs import CRS
from rasterio.enums import Resampling
from xarray import DataArray

from tests import TEST_RESOURCES_PATH, EODagTestCase
from tests.context import AddressNotFound, EOProduct, StacAssets
from tests.utils import mock


class TestEOProductDriverStacAssets(EODagTestCase):
    def setUp(self):
        super(TestEOProductDriverStacAssets, self).setUp()
        self.product = EOProduct(self.provider, self.eoproduct_props, productType=self.product_type)
        self.product.properties["title"] = os.path.join(
            TEST_RESOURCES_PATH,
            "products",
            "S2A_MSIL1C_20180101T105441_N0206_R051_T31TDH_20180101T124911.SAFE",
        )
        product_img_data_path = os.path.join(
            TEST_RESOURCES_PATH,
            "products",
            "S2A_MSIL1C_20180101T105441_N0206_R051_T31TDH_20180101T124911.SAFE",
            "GRANULE",
            "L1C_T31TDH_A013204_20180101T105435",
            "IMG_DATA",
        )
        self.product.assets.update(
            {
                "T31TDH_20180101T124911_B01.jp2": {
                    "title": "Band 1",
                    "type": "image/jp2",
                    "roles": ["data"],
                    "href": os.path.join(
                        product_img_data_path,
                        "T31TDH_20180101T105441_B01.jp2",
                    ),
                },
                "T31TDH_20180101T124911_B03.jp2": {
                    "title": "Band 3",
                    "type": "image/jp2",
                    "roles": ["data"],
                    "href": os.path.join(
                        product_img_data_path,
                        "T31TDH_20180101T105441_B03.jp2",
                    ),
                },
                "T31TDH_20180101T124911_B01.json": {
                    "title": "Band 1 metadata",
                    "type": "image/jp2",
                    "roles": ["metadata"],
                    "href": os.path.join(
                        product_img_data_path,
                        "T31TDH_20180101T105441_B01.json",
                    ),
                },
            }
        )
        # update the driver after having set the assets
        self.product.driver = self.product.get_driver()

    def test_driver_set_stac_assets(self):
        """The appropriate driver must have been set"""
        self.assertIsInstance(self.product.driver.legacy, StacAssets)

    def test_driver_get_local_dataset_address_bad_band(self):
        """Driver must raise AddressNotFound if non existent band is requested"""
        with self._filesystem_product() as product:
            driver = StacAssets()
            band = "B02"
            self.assertRaises(AddressNotFound, driver.get_data_address, product, band)
            band = "B0"
            self.assertRaises(AddressNotFound, driver.get_data_address, product, band)

    def test_driver_get_local_dataset_address_ok(self):
        """Driver returns a good address for an existing band"""
        with self._filesystem_product() as product:
            band = "b01"
            address = self.product.driver.legacy.get_data_address(product, band)
            self.assertEqual(address, self.local_band_file)
            band = "t31tdh_20180101t124911_b01"
            address = self.product.driver.legacy.get_data_address(product, band)
            self.assertEqual(address, self.local_band_file)
            band = "T31TDH_20180101T124911_B01.jp2"
            address = self.product.driver.legacy.get_data_address(product, band)
            self.assertEqual(address, self.local_band_file)
            band = "T31TDH.*B01.*"
            address = self.product.driver.legacy.get_data_address(product, band)
            self.assertEqual(address, self.local_band_file)

    def test_asset_get_data(self):
        """get_data should be executable directly from asset"""

        with self._filesystem_product() as product:
            data = product.assets["T31TDH_20180101T124911_B01.jp2"].get_data(
                crs=CRS.from_epsg(4326),
                resolution=0.1,
                extent=[1, 2, 3, 4],
                resampling=Resampling.bilinear,
            )
            self.assertIsInstance(data, DataArray)

    @mock.patch("eodag_cube.api.product._product.EOProduct.get_data", autospec=True)
    def test_asset_get_data_pattern(self, mock_get_data):
        """get_data on asset should use a pattern to match exactly its band"""

        self.product.assets["T31TDH_20180101T124911_B01.jp2"].get_data()
        mock_get_data.assert_called_once_with(
            self.product,
            band=r"^T31TDH_20180101T124911_B01.jp2$",
            crs=None,
            resolution=None,
            extent=None,
            resampling=None,
        )

    @contextmanager
    def _filesystem_product(self):
        original = self.product.location
        try:
            self.product.location = "file:///{}".format(self.product.properties["title"].strip("/"))
            yield self.product
        finally:
            self.product.location = original
