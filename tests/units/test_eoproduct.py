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

import errno
import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, get_ident

import xarray as xr
from rasterio.session import AWSSession

from eodag_cube.types import XarrayDict
from tests import TEST_RESOURCES_PATH, EODagTestCase
from tests.context import (
    DEFAULT_DOWNLOAD_TIMEOUT,
    DEFAULT_DOWNLOAD_WAIT,
    AwsAuth,
    AwsDownload,
    DatasetCreationError,
    EOProduct,
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

    @mock.patch("fsspec.filesystem")
    @mock.patch("eodag.api.product._product.EOProduct.get_storage_options", autospec=True)
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

    @mock.patch("eodag_cube.utils.xarray.try_open_dataset", autospec=True)
    @mock.patch("fsspec.filesystem")
    def test_build_local_xarray_dict_skips_unrecognized_files(self, mock_fs, mock_open_ds):
        product = EOProduct(self.provider, self.eoproduct_props, collection=self.collection)
        local_path = os.path.join(TEST_RESOURCES_PATH, "NOTICE")

        with mock.patch.object(product.driver, "guess_asset_key_and_roles", return_value=(None, [])) as mock_guess:
            xd = product._build_local_xarray_dict(local_path)

        mock_guess.assert_called_once_with(local_path, product)
        mock_fs.return_value.open.assert_not_called()
        mock_open_ds.assert_not_called()
        self.assertFalse(xd)

    @mock.patch("eodag_cube.utils.xarray.try_open_dataset", autospec=True)
    @mock.patch("fsspec.filesystem")
    def test_build_local_xarray_dict_closes_failed_files(self, mock_fs, mock_open_ds):
        product = EOProduct(self.provider, self.eoproduct_props, collection=self.collection)
        local_path = os.path.join(TEST_RESOURCES_PATH, "NOTICE")
        mock_open_ds.side_effect = DatasetCreationError("unsupported dataset")

        with mock.patch.object(product.driver, "guess_asset_key_and_roles", return_value=("band", [])):
            xd = product._build_local_xarray_dict(local_path, engine="rasterio")

        mock_fs.return_value.open.assert_called_once_with(local_path)
        mock_open_ds.assert_called_once_with(mock_fs.return_value.open.return_value, engine="rasterio")
        mock_fs.return_value.open.return_value.close.assert_called_once_with()
        self.assertFalse(xd)

    @mock.patch("eodag_cube.utils.xarray.try_open_dataset", autospec=True)
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

    @mock.patch("eodag_cube.api.product._product.EOProduct.download", autospec=True)
    @mock.patch("eodag_cube.api.product._product.EOProduct._build_local_xarray_dict", autospec=True)
    @mock.patch("eodag_cube.api.product._product.EOProduct.get_file_obj", autospec=True)
    def test_to_xarray_downloaded_directory(self, mock_get_file, mock_build_local, mock_download):
        product = EOProduct(self.provider, self.eoproduct_props, collection=self.collection)
        local_path = os.path.abspath(os.path.join(TEST_RESOURCES_PATH, "products"))
        for error in [
            IsADirectoryError(errno.EISDIR, "Is a directory", local_path),
            PermissionError(errno.EACCES, "Permission denied", local_path),
        ]:
            mock_get_file.side_effect = error
            for download_fallback in [False, True]:
                with self.subTest(error=type(error).__name__, download_fallback=download_fallback):
                    mock_build_local.reset_mock()
                    mock_build_local.return_value = XarrayDict({"z": xr.Dataset(), "a": xr.Dataset()})

                    xd = product.to_xarray(download_fallback=download_fallback, engine="rasterio")

                    mock_build_local.assert_called_once_with(product, local_path, engine="rasterio")
                    mock_download.assert_not_called()
                    self.assertEqual(list(xd), ["a", "z"])
                    for dataset in xd.values():
                        self.assertDictEqual(product.properties, dataset.attrs)

        mock_build_local.return_value = XarrayDict()
        with self.assertRaisesRegex(DatasetCreationError, "Could not build local XarrayDict"):
            product.to_xarray()
        mock_download.assert_not_called()

    @mock.patch("eodag_cube.api.product._product.EOProduct.download", autospec=True)
    @mock.patch("eodag_cube.api.product._product.EOProduct._build_local_xarray_dict", autospec=True)
    @mock.patch("eodag_cube.api.product._product.EOProduct.get_file_obj", autospec=True)
    def test_to_xarray_file_permission_error(self, mock_get_file, mock_build_local, mock_download):
        product = EOProduct(self.provider, self.eoproduct_props, collection=self.collection)
        local_path = os.path.abspath(os.path.join(TEST_RESOURCES_PATH, "NOTICE"))
        mock_get_file.side_effect = PermissionError(errno.EACCES, "Permission denied", local_path)

        with self.assertRaises(PermissionError):
            product.to_xarray()

        mock_build_local.assert_not_called()
        mock_download.assert_not_called()

    @mock.patch("eodag_cube.utils.xarray.try_open_dataset", autospec=True)
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
        opening_threads = []
        opening_barrier = Barrier(2)

        def open_dataset(*args, **kwargs):
            opening_threads.append(get_ident())
            opening_barrier.wait(timeout=5)
            return mock_open_ds.return_value

        mock_open_ds.side_effect = open_dataset
        xd = product.to_xarray(foo="bar")
        self.assertEqual(len(set(opening_threads)), 2)
        self.assertNotIn(get_ident(), opening_threads)
        mock_get_file.assert_any_call(product, "foo", DEFAULT_DOWNLOAD_WAIT, DEFAULT_DOWNLOAD_TIMEOUT)
        mock_get_file.assert_any_call(product, "bar", DEFAULT_DOWNLOAD_WAIT, DEFAULT_DOWNLOAD_TIMEOUT)
        mock_open_ds.assert_called_with(mock_get_file.return_value, foo="bar")
        self.assertEqual(len(xd), 2)
        self.assertTrue(xd["foo"].equals(mock_open_ds.return_value))
        self.assertTrue(xd["bar"].equals(mock_open_ds.return_value))
        self.assertDictEqual(product.properties, xd["foo"].attrs)
        self.assertDictEqual(product.properties, xd["bar"].attrs)

    @mock.patch("eodag_cube.utils.xarray.try_open_dataset", autospec=True)
    @mock.patch("eodag_cube.api.product._product.EOProduct.get_file_obj", autospec=True)
    def test_to_xarray_max_workers(self, mock_get_file, mock_open_ds):
        product = EOProduct(self.provider, self.eoproduct_props, collection=self.collection)
        product.assets.update({key: {"href": f"https://foo/{key}.tif", "roles": ["data"]} for key in ["foo", "bar"]})
        mock_get_file.return_value.path = "https://foo/band.tif"
        mock_open_ds.return_value = xr.Dataset()

        for max_workers in [None, 1, 2]:
            with self.subTest(max_workers=max_workers):
                with mock.patch("concurrent.futures.ThreadPoolExecutor", wraps=ThreadPoolExecutor) as mock_executor:
                    xd = product.to_xarray(max_workers=max_workers, roles=iter(["data"]), foo="bar")

                mock_executor.assert_called_once_with(max_workers=max_workers)
                self.assertEqual(list(xd), ["bar", "foo"])
                mock_open_ds.assert_called_with(mock_get_file.return_value, foo="bar")

    @mock.patch("concurrent.futures.ThreadPoolExecutor")
    @mock.patch("eodag_cube.utils.xarray.try_open_dataset", autospec=True)
    @mock.patch("eodag_cube.api.product._product.EOProduct.get_file_obj", autospec=True)
    def test_to_xarray_filtered_assets_without_executor(self, mock_get_file, mock_open_ds, mock_executor):
        product = EOProduct(self.provider, self.eoproduct_props, collection=self.collection)
        product.assets.update(
            {
                "band": {"href": "https://foo/band.tif", "roles": ["data"]},
                "metadata": {"href": "https://foo/metadata.xml", "roles": ["metadata"]},
            }
        )
        mock_get_file.return_value.path = "https://foo/band.tif"
        mock_open_ds.return_value = xr.Dataset()

        for role, fails, expected_keys in [("missing", False, []), ("data", False, ["band"]), ("data", True, [])]:
            with self.subTest(role=role, fails=fails):
                mock_get_file.reset_mock()
                mock_open_ds.reset_mock()
                mock_open_ds.side_effect = OSError("remote read failed") if fails else None

                xd = product.to_xarray(roles=iter([role]), max_workers=2, foo="bar")

                self.assertEqual(list(xd), expected_keys)
                if role == "missing":
                    mock_get_file.assert_not_called()
                    mock_open_ds.assert_not_called()
                else:
                    mock_get_file.assert_called_once_with(
                        product, "band", DEFAULT_DOWNLOAD_WAIT, DEFAULT_DOWNLOAD_TIMEOUT
                    )
                    mock_open_ds.assert_called_once_with(mock_get_file.return_value, foo="bar")
                mock_executor.assert_not_called()

    def test_to_xarray_rejects_invalid_max_workers(self):
        product = EOProduct(self.provider, self.eoproduct_props, collection=self.collection)
        for max_workers in [0, -1]:
            with self.subTest(max_workers=max_workers):
                with self.assertRaisesRegex(ValueError, "max_workers must be greater than 0"):
                    product.to_xarray(max_workers=max_workers)

    @mock.patch("eodag_cube.api.product._product.EOProduct.download", autospec=True)
    @mock.patch("eodag_cube.api.product._product.EOProduct.get_file_obj", autospec=True)
    def test_to_xarray_single_asset_remote_failure(self, mock_get_file, mock_download):
        """A remote read failure should be raised without downloading by default."""
        product = EOProduct(self.provider, self.eoproduct_props, collection=self.collection)
        mock_get_file.side_effect = OSError("remote read failed")

        with self.assertRaisesRegex(OSError, "remote read failed"):
            product.to_xarray()

        mock_download.assert_not_called()

    @mock.patch("eodag_cube.api.product._product.EOProduct.download", autospec=True)
    @mock.patch("eodag_cube.api.product._product.EOProduct.get_file_obj", autospec=True)
    def test_to_xarray_download_fallback(self, mock_get_file, mock_download):
        """A remote read failure should trigger a download when requested."""
        product = EOProduct(self.provider, self.eoproduct_props, collection=self.collection)
        mock_get_file.side_effect = OSError("remote read failed")
        mock_download.side_effect = RuntimeError("download attempted")

        with self.assertRaisesRegex(RuntimeError, "download attempted"):
            product.to_xarray(download_fallback=True)

        mock_download.assert_called_once_with(
            product,
            asset=None,
            wait=DEFAULT_DOWNLOAD_WAIT,
            timeout=DEFAULT_DOWNLOAD_TIMEOUT,
            extract=True,
        )

    @mock.patch("eodag_cube.api.product._product.EOProduct.download", autospec=True)
    @mock.patch("eodag_cube.api.product._product.EOProduct.get_file_obj", autospec=True)
    def test_to_xarray_assets_skip_failures(self, mock_get_file, mock_download):
        """Remote read failures should be skipped when reading several assets."""
        product = EOProduct(self.provider, self.eoproduct_props, collection=self.collection)
        product.assets.update(
            {
                "foo": {"href": "http://foo.bar"},
                "bar": {"href": "http://bar.baz"},
            }
        )
        mock_get_file.side_effect = OSError("remote read failed")

        xd = product.to_xarray()

        self.assertFalse(xd)
        mock_download.assert_not_called()

    def test_asset_to_xarray_download_fallback(self):
        """Asset.to_xarray should forward the download fallback option."""
        product = EOProduct(self.provider, self.eoproduct_props, collection=self.collection)
        product.assets.update({"foo": {"href": "http://foo.bar"}})
        dataset = xr.Dataset()

        with mock.patch.object(product, "to_xarray", return_value={"foo": dataset}) as mock_to_xarray:
            result = product.assets["foo"].to_xarray(download_fallback=True, foo="bar")

        self.assertIs(result, dataset)
        mock_to_xarray.assert_called_once_with(
            "foo",
            DEFAULT_DOWNLOAD_WAIT,
            DEFAULT_DOWNLOAD_TIMEOUT,
            download_fallback=True,
            foo="bar",
        )

    def test_assets_are_sorted_when_updated(self):
        """Assets should remain sorted and wrapped when updated."""
        product = EOProduct(self.provider, self.eoproduct_props, collection=self.collection)

        product.assets.update(
            {
                "foo": {"href": "http://foo.bar"},
                "bar": {"href": "http://bar.baz"},
            }
        )
        product.assets["baz"] = {"href": "http://baz.qux"}

        self.assertEqual(list(product.assets), ["bar", "baz", "foo"])
        self.assertTrue(all(asset.product is product for asset in product.assets.values()))
