# -*- coding: utf-8 -*-
# Copyright 2024, CS GROUP - France, http://www.c-s.fr
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

import unittest

import fsspec.implementations
import fsspec.implementations.http
import responses
import xarray as xr
from fsspec.core import OpenFile

from tests.context import (
    DatasetCreationError,
    fsspec_file_extension,
    fsspec_file_headers,
    guess_engines,
    try_open_dataset,
)
from tests.utils import mock


class TestUtils(unittest.TestCase):
    def test_fsspec_file_headers(self):
        """fsspec_file_headers must return headers from http openfile"""

        # http OpenFile
        fs = fsspec.filesystem("https")
        file = OpenFile(fs, "https://foo/bar.baz")

        # HEAD and GET succeed
        @responses.activate(registry=responses.registries.OrderedRegistry)
        def run():
            responses.add(
                responses.HEAD,
                "https://foo/bar.baz",
                status=200,
                headers={"a-header": "from-head"},
            )
            responses.add(
                responses.GET,
                "https://foo/bar.baz",
                stream=True,
                status=200,
                headers={"a-header": "from-get"},
            )
            headers = fsspec_file_headers(file)
            # check if headers contain expected content
            self.assertGreaterEqual(headers.items(), {"a-header": "from-head"}.items())

        run()

        # HEAD fails
        @responses.activate(registry=responses.registries.OrderedRegistry)
        def run():
            responses.add(
                responses.HEAD,
                "https://foo/bar.baz",
                status=400,
                headers={"a-header": "from-head"},
            )
            responses.add(
                responses.GET,
                "https://foo/bar.baz",
                status=200,
                headers={"a-header": "from-get"},
            )
            headers = fsspec_file_headers(file)
            # check if headers contain expected content
            self.assertGreaterEqual(headers.items(), {"a-header": "from-get"}.items())

        run()

        # both fail
        @responses.activate(registry=responses.registries.OrderedRegistry)
        def run():
            responses.add(
                responses.HEAD,
                "https://foo/bar.baz",
                status=400,
                headers={"a-header": "from-head"},
            )
            responses.add(
                responses.GET,
                "https://foo/bar.baz",
                status=400,
                headers={"a-header": "from-get"},
            )
            headers = fsspec_file_headers(file)
            # check if headers contain expected content
            self.assertIsNone(headers)

        run()

    def test_fsspec_file_extension(self):
        """fsspec_file_extension must return openfile file extension"""

        # http OpenFile
        fs = fsspec.filesystem("https")
        file = OpenFile(fs, "https://foo/bar.baz")

        # filename in headers
        with mock.patch(
            "eodag_cube.utils.fsspec_file_headers",
        ) as mock_headers:
            mock_headers.return_value = {
                "content-disposition": 'attachment; filename="foo.grib"'
            }
            self.assertEqual(fsspec_file_extension(file), ".grib")
        # content type in headers
        with mock.patch(
            "eodag_cube.utils.fsspec_file_headers",
        ) as mock_headers:
            mock_headers.return_value = {"content-type": "image/jp2"}
            self.assertEqual(fsspec_file_extension(file), ".jp2")
        # extension in url
        with mock.patch(
            "eodag_cube.utils.fsspec_file_headers",
        ) as mock_headers:
            mock_headers.return_value = None
            self.assertEqual(fsspec_file_extension(file), ".baz")


class TestXarray(unittest.TestCase):
    @mock.patch("eodag_cube.utils.requests.head", autospec=True)
    @mock.patch("eodag_cube.utils.requests.get", autospec=True)
    def test_guess_engines(self, mock_head, mock_get):
        """guess_engines must return guessed xarray engines"""

        all_engines = xr.backends.list_engines()

        for eng in ["h5netcdf", "cfgrib", "rasterio"]:
            self.assertIn(eng, all_engines)

        fs = fsspec.filesystem("https")

        file = OpenFile(fs, "https://foo/bar.baz")
        self.assertEqual(guess_engines(file), [])

        file = OpenFile(fs, "https://foo/bar.jp2")
        self.assertIn("rasterio", guess_engines(file))

        file = OpenFile(fs, "https://foo/bar.nc")
        self.assertIn("h5netcdf", guess_engines(file))

        file = OpenFile(fs, "https://foo/bar.grib")
        self.assertIn("cfgrib", guess_engines(file))

    @mock.patch(
        "eodag_cube.utils.xarray.guess_engines", return_value=["h5netcdf", "foo"]
    )
    @mock.patch("eodag_cube.utils.xarray.fsspec.open")
    def test_try_open_dataset_local(self, mock_open, mock_guess_engines):
        """try_open_dataset must call xaray.open_dataset with appropriate args"""
        # local file : let xarray guess engine
        fs = fsspec.filesystem("file")
        fs.open = mock_open
        file = OpenFile(fs, "/foo/bar.nc")

        with mock.patch(
            "eodag_cube.utils.xarray.xr.open_dataset",
        ) as mock_open_dataset:
            mock_open_dataset.return_value = xr.Dataset()
            ds = try_open_dataset(file, foo="bar", baz="qux")
            self.assertIsInstance(ds, xr.Dataset)
            mock_open_dataset.assert_called_once_with(file.path, foo="bar", baz="qux")
            # local file + error
            mock_open_dataset.side_effect = Exception("bla bla")
            with self.assertRaises(
                DatasetCreationError,
                msg="Cannot open local dataset /foo/bar.nc: bla bla",
            ):
                ds = try_open_dataset(file, foo="bar", baz="qux")

    @mock.patch("eodag_cube.utils.xarray.guess_engines", return_value=["cfgrib"])
    @mock.patch("eodag_cube.utils.xarray.fsspec.open")
    def test_try_open_dataset_remote_grib(self, mock_open, mock_guess_engines):
        """try_open_dataset must call xaray.open_dataset with appropriate args"""
        # remote file + grib
        fs = fsspec.filesystem("https")
        fs.open = mock_open
        file = OpenFile(fs, "https://foo/bar.grib")
        mock_open.return_value = file
        with self.assertRaises(
            DatasetCreationError,
            msg="None of the engines [] could open the dataset at https://foo/bar.grib",
        ):
            try_open_dataset(file, foo="bar", baz="qux")

    @mock.patch("eodag_cube.utils.xarray.guess_engines", return_value=["cfgrib"])
    @mock.patch("eodag_cube.utils.xarray.fsspec.open")
    def test_try_open_dataset_local_grib(self, mock_open, mock_guess_engines):
        """try_open_dataset must call xaray.open_dataset with appropriate args"""
        # local file + grib
        fs = fsspec.filesystem("file")
        fs.open = mock_open
        file = OpenFile(fs, "/foo/bar.grib")
        mock_open.return_value = file
        with mock.patch(
            "eodag_cube.utils.xarray.xr.open_dataset",
        ) as mock_open_dataset:
            mock_open_dataset.return_value = xr.Dataset()
            ds = try_open_dataset(file, foo="bar", baz="qux")
            self.assertIsInstance(ds, xr.Dataset)
            mock_open_dataset.assert_called_once_with(
                file.path, engine="cfgrib", foo="bar", baz="qux"
            )

    @mock.patch(
        "eodag_cube.utils.xarray.guess_engines", return_value=["h5netcdf", "foo"]
    )
    @mock.patch("eodag_cube.utils.xarray.fsspec.open")
    def test_try_open_dataset_remote_nc(self, mock_open, mock_guess_engines):
        """try_open_dataset must call xaray.open_dataset with appropriate args"""
        # remote file + nc
        fs = fsspec.filesystem("https")
        fs.open = mock_open
        file = OpenFile(fs, "https://foo/bar.nc")
        mock_open.return_value = file
        with mock.patch(
            "eodag_cube.utils.xarray.xr.open_dataset",
        ) as mock_open_dataset:
            mock_open_dataset.return_value = xr.Dataset()
            ds = try_open_dataset(file, foo="bar", baz="qux")
            self.assertIsInstance(ds, xr.Dataset)
            mock_open_dataset.assert_called_once_with(
                file, engine="h5netcdf", foo="bar", baz="qux"
            )

    @mock.patch("eodag_cube.utils.xarray.guess_engines", return_value=["rasterio"])
    @mock.patch("eodag_cube.utils.xarray.fsspec.open")
    def test_try_open_dataset_remote_jp2(self, mock_open, mock_guess_engines):
        """try_open_dataset must call open_rasterio with appropriate args"""
        # remote file + nc
        fs = fsspec.filesystem("https")
        fs.open = mock_open
        file = OpenFile(fs, "https://foo/bar.jp2")
        mock_open.return_value = file
        with mock.patch(
            "eodag_cube.utils.xarray.rioxarray.open_rasterio",
        ) as mock_open_rio:
            mock_open_rio.return_value = xr.DataArray()
            ds = try_open_dataset(file, foo="bar", baz="qux")
            self.assertIsInstance(ds, xr.Dataset)
            mock_open_rio.assert_called_once_with(
                file.path, opener=mock_open, foo="bar", baz="qux"
            )
