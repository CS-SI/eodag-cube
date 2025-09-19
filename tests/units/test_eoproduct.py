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
import os
import random

import numpy as np
import xarray as xr
from rasterio.session import AWSSession

from tests import TEST_GRIB_FILE_PATH, TEST_GRIB_FILENAME, EODagTestCase
from tests.context import (
    DEFAULT_DOWNLOAD_TIMEOUT,
    DEFAULT_DOWNLOAD_WAIT,
    DEFAULT_PROJ,
    USER_AGENT,
    Authentication,
    AwsAuth,
    AwsDownload,
    DatasetCreationError,
    Download,
    DownloadError,
    EOProduct,
    HTTPHeaderAuth,
    HttpQueryStringAuth,
    NoDriver,
    PluginConfig,
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
        product = EOProduct(self.provider, self.eoproduct_props, productType=product_type)
        self.assertIsInstance(product.driver.legacy, Sentinel2L1C)

    def test_get_data_local_product_ok(self):
        """A call to get_data on a product present in the local filesystem must succeed"""  # noqa
        self.eoproduct_props.update({"downloadLink": "file:///{}".format(self.local_product_abspath.strip("/"))})
        product = EOProduct(self.provider, self.eoproduct_props, productType=self.product_type)
        product.driver.legacy = mock.MagicMock(spec_set=NoDriver())
        product.driver.legacy.get_data_address.return_value = self.local_band_file

        data, band = self.execute_get_data(product, give_back=("band",))

        self.assertEqual(product.driver.legacy.get_data_address.call_count, 1)
        product.driver.legacy.get_data_address.assert_called_with(product, band)
        self.assertIsInstance(data, xr.DataArray)
        self.assertNotEqual(data.values.size, 0)

    def test_get_data_local_grib_product_ok(self):
        """A call to get_data on a local product in GRIB format must succeed"""  # noqa
        product = EOProduct(self.provider, self.eoproduct_props)
        product.driver.legacy = mock.MagicMock(spec_set=NoDriver())
        product.driver.legacy.get_data_address.return_value = TEST_GRIB_FILE_PATH
        data = product.get_data(band=TEST_GRIB_FILENAME)
        self.assertEqual(product.driver.legacy.get_data_address.call_count, 1)

        self.assertIsInstance(data, xr.DataArray)
        self.assertEqual(data.attrs["GRIB_COMMENT"], "Temperature [C]")

    def test_get_data_download_on_unsupported_dataset_address_scheme_error(self):
        """If a product is not on the local filesystem, it must download itself before returning the data"""  # noqa
        product = EOProduct(self.provider, self.eoproduct_props, productType=self.product_type)

        def get_data_address(*args, **kwargs):
            eo_product = args[0]
            if eo_product.location.startswith("https"):
                raise UnsupportedDatasetAddressScheme
            return self.local_band_file

        product.driver.legacy = mock.MagicMock(spec_set=NoDriver())
        product.driver.legacy.get_data_address.side_effect = get_data_address

        mock_downloader = mock.MagicMock(
            spec_set=Download(
                provider=self.provider,
                config=config.PluginConfig.from_mapping({"type": "Download", "extract": False, "archive_depth": 1}),
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
                provider=self.provider, config=config.PluginConfig.from_mapping({"type": "Download"})
            )
        )

        product.register_downloader(mock_downloader, mock_authenticator.authenticate())
        data, band = self.execute_get_data(product, give_back=("band",))

        self.assertEqual(product.driver.legacy.get_data_address.call_count, 2)
        product.driver.legacy.get_data_address.assert_called_with(product, band)
        self.assertIsInstance(data, xr.DataArray)
        self.assertNotEqual(data.values.size, 0)

    def test_get_data_dl_on_unsupported_ds_address_scheme_error_wo_downloader(self):
        """If a product is not on filesystem and a downloader isn't registered, get_data must return an empty array"""  # noqa
        product = EOProduct(self.provider, self.eoproduct_props, productType=self.product_type)

        product.driver.legacy = mock.MagicMock(spec_set=NoDriver())
        product.driver.legacy.get_data_address.side_effect = UnsupportedDatasetAddressScheme

        self.assertRaises(RuntimeError, product.download)

        data = self.execute_get_data(product)

        self.assertEqual(product.driver.legacy.get_data_address.call_count, 1)
        self.assertIsInstance(data, xr.DataArray)
        self.assertEqual(data.values.size, 0)

    def test_get_data_bad_download_on_unsupported_dataset_address_scheme_error(self):
        """If downloader doesn't return the downloaded file path, get_data must return an empty array"""  # noqa
        product = EOProduct(self.provider, self.eoproduct_props, productType=self.product_type)

        product.driver.legacy = mock.MagicMock(spec_set=NoDriver())
        product.driver.legacy.get_data_address.side_effect = UnsupportedDatasetAddressScheme

        mock_downloader = mock.MagicMock(
            spec_set=Download(
                provider=self.provider,
                config=config.PluginConfig.from_mapping({"type": "Download", "extract": False}),
            )
        )
        mock_downloader.download.return_value = None
        mock_authenticator = mock.MagicMock(
            spec_set=Authentication(
                provider=self.provider, config=config.PluginConfig.from_mapping({"type": "Download"})
            )
        )

        product.register_downloader(mock_downloader, mock_authenticator)

        self.assertRaises(DownloadError, product.download)

        data, band = self.execute_get_data(product, give_back=("band",))

        self.assertEqual(product.driver.legacy.get_data_address.call_count, 1)
        product.driver.legacy.get_data_address.assert_called_with(product, band)
        self.assertIsInstance(data, xr.DataArray)
        self.assertEqual(data.values.size, 0)

    @staticmethod
    def execute_get_data(product, crs=None, resolution=None, band=None, extent=None, give_back=()):
        """Call the get_data method of given product with given parameters, then return
        the computed data and the parameters passed in whom names are in give_back for
        further assertions in the calling test method"""
        crs = crs or DEFAULT_PROJ
        resolution = resolution or 0.0006
        band = band or "B01"
        extent = extent or (2.1, 42.8, 2.2, 42.9)
        data = product.get_data(band=band, crs=crs, resolution=resolution, extent=extent)
        if give_back:
            returned_params = tuple(value for name, value in locals().items() if name in give_back)
            return tuple(itertools.chain.from_iterable(((data,), returned_params)))
        return data

    def test_get_rio_env(self):
        """RIO env should be adapted to the provider config"""
        product = EOProduct(self.provider, self.eoproduct_props, productType=self.product_type)

        # http
        self.assertDictEqual(product._get_rio_env("https://path/to/asset"), {})

        # aws s3
        product.register_downloader(AwsDownload("foo", PluginConfig()), AwsAuth("foo", PluginConfig()))
        product.downloader._get_authenticated_objects_unsigned = mock.MagicMock()
        product.downloader._get_authenticated_objects_unsigned.__name__ = "mocked"
        rio_env = product._get_rio_env("s3://path/to/asset")
        self.assertIsInstance(rio_env["session"], AWSSession)
        self.assertIn("amazonaws.com", rio_env["AWS_S3_ENDPOINT"])

        # aws s3 with custom endpoint
        product.register_downloader(AwsDownload("foo", PluginConfig()), AwsAuth("foo", PluginConfig()))
        product.downloader_auth.config.s3_endpoint = "https://some.where"
        rio_env = product._get_rio_env("s3://path/to/asset")
        self.assertEqual(len(rio_env), 4)
        self.assertIsInstance(rio_env["session"], AWSSession)
        self.assertEqual(rio_env["AWS_HTTPS"], "YES")
        self.assertEqual(rio_env["AWS_S3_ENDPOINT"], "some.where")
        self.assertEqual(rio_env["AWS_VIRTUAL_HOSTING"], "FALSE")

        # aws s3 with custom endpoint and band in zip
        rio_env = product._get_rio_env("zip+s3://path/to/asset.zip!band.tiff")
        self.assertEqual(len(rio_env), 4)
        self.assertIsInstance(rio_env["session"], AWSSession)
        self.assertEqual(rio_env["AWS_HTTPS"], "YES")
        self.assertEqual(rio_env["AWS_S3_ENDPOINT"], "some.where")
        self.assertEqual(rio_env["AWS_VIRTUAL_HOSTING"], "FALSE")

    def test_get_storage_options_http_headers(self):
        """_get_storage_options should be adapted to the provider config"""
        product = EOProduct(self.provider, self.eoproduct_props, productType=self.product_type)
        # http headers auth
        product.register_downloader(
            Download("foo", PluginConfig()),
            HTTPHeaderAuth(
                "foo",
                PluginConfig.from_mapping(
                    {
                        "type": "Download",
                        "credentials": {"apikey": "foo"},
                        "headers": {"X-API-Key": "{apikey}"},
                    }
                ),
            ),
        )
        self.assertDictEqual(
            product._get_storage_options(),
            {
                "path": self.download_url,
                "headers": {"X-API-Key": "foo", **USER_AGENT},
            },
        )

    def test_get_storage_options_http_qs(self):
        """_get_storage_options should be adapted to the provider config"""
        product = EOProduct(self.provider, self.eoproduct_props, productType=self.product_type)
        # http qs auth
        product.register_downloader(
            Download("foo", PluginConfig()),
            HttpQueryStringAuth(
                "foo",
                PluginConfig.from_mapping(
                    {
                        "type": "Download",
                        "credentials": {"apikey": "foo"},
                    }
                ),
            ),
        )
        self.assertDictEqual(
            product._get_storage_options(),
            {
                "path": f"{self.download_url}?apikey=foo",
                "headers": USER_AGENT,
            },
        )

    def test_get_storage_options_s3(self):
        """_get_storage_options should be adapted to the provider config"""
        product = EOProduct(self.provider, self.eoproduct_props, productType=self.product_type)
        # http s3 auth
        product.register_downloader(
            Download(
                "foo",
                PluginConfig.from_mapping(
                    {
                        "type": "Download",
                        "s3_endpoint": "http://foo.bar",
                    }
                ),
            ),
            AwsAuth(
                "foo",
                PluginConfig.from_mapping(
                    {
                        "type": "Download",
                        "credentials": {
                            "aws_access_key_id": "foo",
                            "aws_secret_access_key": "bar",
                            "aws_session_token": "baz",
                        },
                    }
                ),
            ),
        )
        self.assertDictEqual(
            product._get_storage_options(),
            {
                "path": self.download_url,
                "key": "foo",
                "secret": "bar",
                "token": "baz",
                "client_kwargs": {"endpoint_url": "http://foo.bar"},
            },
        )

    def test_get_storage_options_error(self):
        """_get_storage_options should be adapted to the provider config"""
        product = EOProduct(self.provider, self.eoproduct_props, productType=self.product_type)
        product.downloader = mock.MagicMock()
        with self.assertRaises(DatasetCreationError, msg=f"foo not found in {product} assets"):
            product._get_storage_options(asset_key="foo")

    @mock.patch("eodag_cube.api.product._product.fsspec.filesystem")
    @mock.patch("eodag_cube.api.product._product.EOProduct._get_storage_options", autospec=True)
    def test_get_file_obj(self, mock_storage_options, mock_fs):
        """get_file_obj should call fsspec open with appropriate args"""
        product = EOProduct(self.provider, self.eoproduct_props, productType=self.product_type)
        # https
        mock_storage_options.return_value = {"path": "https://foo.bar", "baz": "qux"}
        file = product.get_file_obj()
        mock_fs.assert_called_once_with("https", baz="qux")
        mock_fs.return_value.open.assert_called_once_with(path="https://foo.bar")
        self.assertEqual(file, mock_fs.return_value.open.return_value)
        mock_fs.reset_mock()
        # s3
        mock_storage_options.return_value = {"path": "s3://foo.bar", "baz": "qux"}
        file = product.get_file_obj()
        mock_fs.assert_called_once_with("s3", baz="qux")
        mock_fs.return_value.open.assert_called_once_with(path="s3://foo.bar")
        self.assertEqual(file, mock_fs.return_value.open.return_value)
        mock_fs.reset_mock()
        # local
        mock_storage_options.return_value = {
            "path": os.path.join("foo", "bar"),
            "baz": "qux",
        }
        file = product.get_file_obj()
        mock_fs.assert_called_once_with("file", baz="qux")
        mock_fs.return_value.open.assert_called_once_with(path=os.path.join("foo", "bar"))
        self.assertEqual(file, mock_fs.return_value.open.return_value)
        mock_fs.reset_mock()
        # not found
        mock_storage_options.return_value = {"baz": "qux"}
        with self.assertRaises(UnsupportedDatasetAddressScheme, msg=f"Could not get {product} path"):
            product.get_file_obj()

    @mock.patch("eodag_cube.api.product._product.try_open_dataset", autospec=True)
    @mock.patch("eodag_cube.api.product._product.EOProduct.get_file_obj", autospec=True)
    def test_to_xarray(self, mock_get_file, mock_open_ds):
        """to_xarrray should return well built XarrayDict"""
        product = EOProduct(self.provider, self.eoproduct_props, productType=self.product_type)
        mock_open_ds.return_value = xr.Dataset()
        mock_get_file.return_value.path = "http://foo.bar"
        xd = product.to_xarray(foo="bar")
        mock_get_file.assert_called_once_with(product, None, DEFAULT_DOWNLOAD_WAIT, DEFAULT_DOWNLOAD_TIMEOUT)
        mock_open_ds.assert_called_once_with(mock_get_file.return_value, foo="bar")
        self.assertEqual(len(xd), 1)
        self.assertTrue(xd["data"].equals(mock_open_ds.return_value))
        self.assertDictEqual(product.properties, xd["data"].attrs)

    @mock.patch("eodag_cube.api.product._product.try_open_dataset", autospec=True)
    @mock.patch("eodag_cube.api.product._product.EOProduct.get_file_obj", autospec=True)
    def test_to_xarray_assets(self, mock_get_file, mock_open_ds):
        """to_xarrray should return well built XarrayDict"""
        product = EOProduct(self.provider, self.eoproduct_props, productType=self.product_type)
        product.assets.update(
            {"foo": {"href": "http://foo.bar"}},
        )
        product.assets.update(
            {"bar": {"href": "http://bar.baz"}},
        )

        mock_open_ds.return_value = xr.Dataset()
        mock_get_file.return_value.path = "http://foo.bar"
        xd = product.to_xarray(foo="bar")
        mock_get_file.assert_any_call(product, "foo", DEFAULT_DOWNLOAD_WAIT, DEFAULT_DOWNLOAD_TIMEOUT)
        mock_get_file.assert_any_call(product, "bar", DEFAULT_DOWNLOAD_WAIT, DEFAULT_DOWNLOAD_TIMEOUT)
        mock_open_ds.assert_called_with(mock_get_file.return_value, foo="bar")
        self.assertEqual(len(xd), 2)
        self.assertTrue(xd["foo"].equals(mock_open_ds.return_value))
        self.assertTrue(xd["bar"].equals(mock_open_ds.return_value))
        self.assertDictEqual(product.properties, xd["foo"].attrs)
        self.assertDictEqual(product.properties, xd["bar"].attrs)
