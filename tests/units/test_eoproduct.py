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

import xarray as xr
from rasterio.session import AWSSession

from tests import EODagTestCase
from tests.context import (
    DEFAULT_DOWNLOAD_TIMEOUT,
    DEFAULT_DOWNLOAD_WAIT,
    USER_AGENT,
    AwsAuth,
    AwsDownload,
    DatasetCreationError,
    Download,
    EOProduct,
    HTTPHeaderAuth,
    HttpQueryStringAuth,
    PluginConfig,
    UnsupportedDatasetAddressScheme,
)
from tests.utils import mock


class TestEOProduct(EODagTestCase):
    def test_get_rio_env(self):
        """RIO env should be adapted to the provider config"""
        product = EOProduct(self.provider, self.eoproduct_props, collection=self.collection)

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
        product = EOProduct(self.provider, self.eoproduct_props, collection=self.collection)
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

    def test_get_storage_options_http_no_auth(self):
        """_get_storage_options should be return path when no auth"""
        product = EOProduct(self.provider, self.eoproduct_props, collection=self.collection)
        # http headers auth
        product.register_downloader(
            Download("foo", PluginConfig()),
            None,
        )
        self.assertDictEqual(
            product._get_storage_options(),
            {
                "path": self.download_url,
            },
        )

    def test_get_storage_options_http_qs(self):
        """_get_storage_options should be adapted to the provider config"""
        product = EOProduct(self.provider, self.eoproduct_props, collection=self.collection)
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

    def test_get_storage_options_s3_credentials_endpoint(self):
        """_get_storage_options should be adapted to the provider config using s3 credentials and endpoint"""
        product = EOProduct(self.provider, self.eoproduct_props, collection=self.collection)
        product.register_downloader(
            Download("foo", PluginConfig()),
            AwsAuth(
                "foo",
                PluginConfig.from_mapping(
                    {
                        "type": "Authentication",
                        "s3_endpoint": "http://foo.bar",
                        "credentials": {
                            "aws_access_key_id": "foo",
                            "aws_secret_access_key": "bar",
                            "aws_session_token": "baz",
                        },
                        "requester_pays": True,
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
                "requester_pays": True,
            },
        )

    def test_get_storage_options_s3_credentials(self):
        """_get_storage_options should be adapted to the provider config using s3 credentials"""
        product = EOProduct(self.provider, self.eoproduct_props, collection=self.collection)
        product.register_downloader(
            Download("foo", PluginConfig()),
            AwsAuth(
                "foo",
                PluginConfig.from_mapping(
                    {
                        "type": "Authentication",
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
            },
        )

    @mock.patch("boto3.Session.get_credentials", return_value=None)
    def test_get_storage_options_s3_anon(self, mock_get_credentials):
        """_get_storage_options should be adapted to the provider config using anonymous s3 access"""
        product = EOProduct(self.provider, self.eoproduct_props, collection=self.collection)
        product.register_downloader(
            Download("foo", PluginConfig()),
            AwsAuth(
                "foo",
                PluginConfig.from_mapping({"type": "Authentication", "requester_pays": True}),
            ),
        )
        self.assertDictEqual(
            product._get_storage_options(),
            {
                "path": self.download_url,
                "anon": True,
            },
        )

    def test_get_storage_options_error(self):
        """_get_storage_options should be adapted to the provider config"""
        product = EOProduct(self.provider, self.eoproduct_props, collection=self.collection)
        product.downloader = mock.MagicMock()
        with self.assertRaises(DatasetCreationError, msg=f"foo not found in {product} assets"):
            product._get_storage_options(asset_key="foo")

    @mock.patch("eodag_cube.api.product._product.fsspec.filesystem")
    @mock.patch("eodag_cube.api.product._product.EOProduct._get_storage_options", autospec=True)
    def test_get_file_obj(self, mock_storage_options, mock_fs):
        """get_file_obj should call fsspec open with appropriate args"""
        product = EOProduct(self.provider, self.eoproduct_props, collection=self.collection)
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
        product = EOProduct(self.provider, self.eoproduct_props, collection=self.collection)
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
        product = EOProduct(self.provider, self.eoproduct_props, collection=self.collection)
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
