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

import itertools
import random

import numpy as np
import xarray as xr

from tests import EODagTestCase
from tests.context import (
    DEFAULT_PROJ,
    Authentication,
    Download,
    DownloadError,
    EOProduct,
    NoDriver,
    Sentinel2L1C,
    UnsupportedDatasetAddressScheme,
    config,
    path_to_uri,
)
from tests.utils import mock


class TestEOProduct(EODagTestCase):
    NOT_ASSOCIATED_PRODUCT_TYPE = "EODAG_DOES_NOT_SUPPORT_THIS_PRODUCT_TYPE"

    def setUp(self):
        super(TestEOProduct, self).setUp()
        self.raster = xr.DataArray(np.arange(25).reshape(5, 5))

    def test_eoproduct_driver_ok(self):
        """EOProduct driver attr must be the one registered for valid platform and instrument in DRIVERS"""  # noqa
        product_type = random.choice(["S2_MSI_L1C"])
        product = EOProduct(
            self.provider, self.eoproduct_props, productType=product_type
        )
        self.assertIsInstance(product.driver, Sentinel2L1C)

    def test_get_data_local_product_ok(self):
        """A call to get_data on a product present in the local filesystem must succeed"""  # noqa
        self.eoproduct_props.update(
            {"downloadLink": "file://{}".format(self.local_product_abspath)}
        )
        product = EOProduct(
            self.provider, self.eoproduct_props, productType=self.product_type
        )
        product.driver = mock.MagicMock(spec_set=NoDriver())
        product.driver.get_data_address.return_value = self.local_band_file

        data, band = self.execute_get_data(product, give_back=("band",))

        self.assertEqual(product.driver.get_data_address.call_count, 1)
        product.driver.get_data_address.assert_called_with(product, band)
        self.assertIsInstance(data, xr.DataArray)
        self.assertNotEqual(data.values.size, 0)

    def test_get_data_download_on_unsupported_dataset_address_scheme_error(self):
        """If a product is not on the local filesystem, it must download itself before returning the data"""  # noqa
        product = EOProduct(
            self.provider, self.eoproduct_props, productType=self.product_type
        )

        def get_data_address(*args, **kwargs):
            eo_product = args[0]
            if eo_product.location.startswith("https"):
                raise UnsupportedDatasetAddressScheme
            return self.local_band_file

        product.driver = mock.MagicMock(spec_set=NoDriver())
        product.driver.get_data_address.side_effect = get_data_address

        mock_downloader = mock.MagicMock(
            spec_set=Download(
                provider=self.provider,
                config=config.PluginConfig.from_mapping(
                    {"extract": False, "archive_depth": 1}
                ),
            )
        )

        def mock_download(*args, **kwargs):
            eo_product = args[0]
            fs_path = self.local_product_as_archive_path
            eo_product.location = path_to_uri(fs_path)
            return fs_path

        mock_downloader.download.side_effect = mock_download
        # mock_downloader.config = {'extract': False, 'archive_depth': 1}
        mock_authenticator = mock.MagicMock(
            spec_set=Authentication(
                provider=self.provider, config=config.PluginConfig.from_mapping({})
            )
        )

        product.register_downloader(mock_downloader, mock_authenticator.authenticate())
        data, band = self.execute_get_data(product, give_back=("band",))

        self.assertEqual(product.driver.get_data_address.call_count, 2)
        product.driver.get_data_address.assert_called_with(product, band)
        self.assertIsInstance(data, xr.DataArray)
        self.assertNotEqual(data.values.size, 0)

    def test_get_data_dl_on_unsupported_ds_address_scheme_error_wo_downloader(self):
        """If a product is not on filesystem and a downloader isn't registered, get_data must return an empty array"""  # noqa
        product = EOProduct(
            self.provider, self.eoproduct_props, productType=self.product_type
        )

        product.driver = mock.MagicMock(spec_set=NoDriver())
        product.driver.get_data_address.side_effect = UnsupportedDatasetAddressScheme

        self.assertRaises(RuntimeError, product.download)

        data = self.execute_get_data(product)

        self.assertEqual(product.driver.get_data_address.call_count, 1)
        self.assertIsInstance(data, xr.DataArray)
        self.assertEqual(data.values.size, 0)

    def test_get_data_bad_download_on_unsupported_dataset_address_scheme_error(self):
        """If downloader doesn't return the downloaded file path, get_data must return an empty array"""  # noqa
        product = EOProduct(
            self.provider, self.eoproduct_props, productType=self.product_type
        )

        product.driver = mock.MagicMock(spec_set=NoDriver())
        product.driver.get_data_address.side_effect = UnsupportedDatasetAddressScheme

        mock_downloader = mock.MagicMock(
            spec_set=Download(
                provider=self.provider,
                config=config.PluginConfig.from_mapping({"extract": False}),
            )
        )
        mock_downloader.download.return_value = None
        mock_authenticator = mock.MagicMock(
            spec_set=Authentication(
                provider=self.provider, config=config.PluginConfig.from_mapping({})
            )
        )

        product.register_downloader(mock_downloader, mock_authenticator)

        self.assertRaises(DownloadError, product.download)

        data, band = self.execute_get_data(product, give_back=("band",))

        self.assertEqual(product.driver.get_data_address.call_count, 1)
        product.driver.get_data_address.assert_called_with(product, band)
        self.assertIsInstance(data, xr.DataArray)
        self.assertEqual(data.values.size, 0)

    @staticmethod
    def execute_get_data(
        product, crs=None, resolution=None, band=None, extent=None, give_back=()
    ):
        """Call the get_data method of given product with given parameters, then return
        the computed data and the parameters passed in whom names are in give_back for
        further assertions in the calling test method"""
        crs = crs or DEFAULT_PROJ
        resolution = resolution or 0.0006
        band = band or "B01"
        extent = extent or (2.1, 42.8, 2.2, 42.9)
        data = product.get_data(crs, resolution, band, extent)
        if give_back:
            returned_params = tuple(
                value for name, value in locals().items() if name in give_back
            )
            return tuple(itertools.chain.from_iterable(((data,), returned_params)))
        return data

    def test_eoproduct_encode_bad_encoding(self):
        """EOProduct encode method must return an empty bytes if encoding is not supported or is None"""  # noqa
        encoding = random.choice(["not_supported", None])
        product = EOProduct(
            self.provider, self.eoproduct_props, productType=self.product_type
        )
        encoded_raster = product.encode(self.raster, encoding)
        self.assertIsInstance(encoded_raster, bytes)
        self.assertEqual(encoded_raster, b"")

    def test_eoproduct_encode_protobuf(self):
        """Test encode method with protocol buffers encoding"""
        # Explicitly provide encoding
        product = EOProduct(
            self.provider, self.eoproduct_props, productType=self.product_type
        )
        encoded_raster = product.encode(self.raster, encoding="protobuf")
        self.assertIsInstance(encoded_raster, bytes)
        self.assertNotEqual(encoded_raster, b"")

    def test_eoproduct_encode_missing_platform_and_instrument(self):
        """Protobuf encode method must raise an error if no platform and instrument are given"""  # noqa
        self.eoproduct_props["platformSerialIdentifier"] = None
        self.eoproduct_props["instrument"] = None
        product = EOProduct(
            self.provider, self.eoproduct_props, productType=self.product_type
        )
        self.assertRaises(TypeError, product.encode, self.raster, encoding="protobuf")

        self.eoproduct_props["platformSerialIdentifier"] = None
        self.eoproduct_props["instrument"] = "MSI"
        product = EOProduct(
            self.provider, self.eoproduct_props, productType=self.product_type
        )
        self.assertRaises(TypeError, product.encode, self.raster, encoding="protobuf")

        self.eoproduct_props["platformSerialIdentifier"] = "S2A"
        self.eoproduct_props["instrument"] = None
        product = EOProduct(
            self.provider, self.eoproduct_props, productType=self.product_type
        )
        self.assertRaises(TypeError, product.encode, self.raster, encoding="protobuf")
