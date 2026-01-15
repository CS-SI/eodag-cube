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
import numpy as np
import responses
import xarray as xr
from fsspec.core import OpenFile

from eodag_cube.types import XarrayDict
from eodag_cube.utils import metadata
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
            mock_headers.return_value = {"content-disposition": 'attachment; filename="foo.grib"'}
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

        for eng in ["h5netcdf", "rasterio"]:
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

    @mock.patch("eodag_cube.utils.xarray.guess_engines", return_value=["h5netcdf", "foo"])
    @mock.patch("eodag_cube.api.product._product.fsspec.open")
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
    @mock.patch("eodag_cube.api.product._product.fsspec.open")
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
    @mock.patch("eodag_cube.api.product._product.fsspec.open")
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
            mock_open_dataset.assert_called_once_with(file.path, engine="cfgrib", foo="bar", baz="qux")

    @mock.patch("eodag_cube.utils.xarray.guess_engines", return_value=["h5netcdf", "foo"])
    @mock.patch("eodag_cube.api.product._product.fsspec.open")
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
            mock_open_dataset.assert_called_once_with(file, engine="h5netcdf", foo="bar", baz="qux")

    @mock.patch("eodag_cube.utils.xarray.guess_engines", return_value=["rasterio"])
    @mock.patch("eodag_cube.api.product._product.fsspec.open")
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
                file.path, opener=mock_open, mask_and_scale=True, foo="bar", baz="qux"
            )


class TestMetadataUtils(unittest.TestCase):
    def setUp(self):
        self.ds_1d = xr.Dataset(
            {
                "band_data": xr.DataArray(np.arange(4), dims=("band",)),  # reste data
            },
            coords={
                "x": [0, 1, 2, 3],
                "time": [0],
                "latitude": ("band", np.linspace(-90, 90, 4)),
                "longitude": ("band", np.linspace(-180, 180, 4)),
            },
        )

        self.ds_2d = xr.Dataset(
            data_vars={
                "band_data": xr.DataArray(
                    np.ones((2, 2)), dims=("y", "x"), attrs={"description": "2D band data", "nodata": -9999.0}
                )
            },
            coords={"x": [0, 1], "y": [10, 11]},
            attrs={"description": "Global dataset description"},
        )

        self.xd_dict = {"ds1": self.ds_1d, "ds2": self.ds_2d}

    def test_extract_projection_info_default(self):
        """Test extract_projection_info returns correct default EPSG and shape"""
        proj_info = metadata.extract_projection_info(self.ds_1d)
        self.assertIn("proj:code", proj_info)
        self.assertEqual(proj_info["proj:code"], "EPSG:4326")
        self.assertIn("proj:shape", proj_info)
        self.assertEqual(proj_info["proj:shape"], [4, 4, 1])
        self.assertNotIn("proj:bbox", proj_info)

    @mock.patch("builtins.hasattr", return_value=False)
    def test_extract_projection_info_no_rio(self, mock_hasattr):
        """Should work even if rio is not present"""
        proj_info = metadata.extract_projection_info(self.ds_1d)
        self.assertEqual(proj_info["proj:code"], "EPSG:4326")

    def test_extract_projection_info_with_rio_and_bbox(self):
        """Test extract_projection_info with rio and bounding box"""
        ds = self.ds_1d

        mock_crs = mock.Mock()
        mock_crs.to_epsg.return_value = 3857

        mock_rio = mock.Mock()
        mock_rio.crs = mock_crs
        mock_rio.bounds.return_value = (0.0, 1.0, 2.0, 3.0)

        with mock.patch.object(xr.Dataset, "rio", new_callable=mock.PropertyMock) as mock_rio_prop:
            mock_rio_prop.return_value = mock_rio

            proj_info = metadata.extract_projection_info(ds)

        self.assertEqual(proj_info["proj:code"], "EPSG:3857")
        self.assertEqual(proj_info["proj:bbox"], [0.0, 1.0, 2.0, 3.0])

    def test_extract_projection_info_rio_epsg_none(self):
        """Test extract_projection_info with rio where EPSG code is None"""
        ds = self.ds_1d

        mock_crs = mock.Mock()
        mock_crs.to_epsg.return_value = None

        mock_rio = mock.Mock()
        mock_rio.crs = mock_crs
        mock_rio.bounds.return_value = (0, 0, 1, 1)

        with mock.patch.object(xr.Dataset, "rio", new_callable=mock.PropertyMock) as mock_rio_prop:
            mock_rio_prop.return_value = mock_rio

            proj_info = metadata.extract_projection_info(ds)

        self.assertEqual(proj_info["proj:code"], "EPSG:4326")

    def test_extract_projection_info_rio_bounds_exception(self):
        """Test extract_projection_info with rio where bounds raise an exception"""
        ds = self.ds_1d

        mock_crs = mock.Mock()
        mock_crs.to_epsg.return_value = 4326

        mock_rio = mock.Mock()
        mock_rio.crs = mock_crs
        mock_rio.bounds.side_effect = Exception("boom")

        with mock.patch.object(xr.Dataset, "rio", new_callable=mock.PropertyMock) as mock_rio_prop:
            mock_rio_prop.return_value = mock_rio

            proj_info = metadata.extract_projection_info(ds)

        self.assertEqual(proj_info["proj:code"], "EPSG:4326")
        self.assertNotIn("proj:bbox", proj_info)

    def test_get_nodata_value(self):
        """Test _get_nodata_value function"""

        # variable with nodata attribute
        var_with_nodata = xr.DataArray(
            np.array([1, 2, 3]),
            attrs={"nodata": -9999},
        )
        var_with_nodata.encoding = {}
        self.assertEqual(metadata._get_nodata_value(var_with_nodata), -9999.0)

        # variable with _FillValue encoding
        var_with_fillvalue = xr.DataArray(
            np.array([1, 2, 3]),
        )
        var_with_fillvalue.encoding["_FillValue"] = -8888
        self.assertEqual(metadata._get_nodata_value(var_with_fillvalue), -8888.0)

        # variable with missing_value encoding
        var_with_missing_value = xr.DataArray(
            np.array([1, 2, 3]),
        )
        var_with_missing_value.encoding["missing_value"] = -7777
        self.assertEqual(metadata._get_nodata_value(var_with_missing_value), -7777.0)

        # variable with rio encoded_nodata
        var_with_rio_enc = xr.DataArray(np.array([1, 2, 3]))
        mock_rio_enc = mock.Mock()
        mock_rio_enc.encoded_nodata = -6666
        with mock.patch.object(xr.DataArray, "rio", new_callable=mock.PropertyMock, return_value=mock_rio_enc):
            self.assertEqual(metadata._get_nodata_value(var_with_rio_enc), -6666.0)

        # variable with rio nodata (when encoded_nodata is None)
        var_with_rio_std = xr.DataArray(np.array([1, 2, 3]))
        mock_rio_std = mock.Mock()
        mock_rio_std.encoded_nodata = None
        mock_rio_std.nodata = -5555
        with mock.patch.object(xr.DataArray, "rio", new_callable=mock.PropertyMock, return_value=mock_rio_std):
            self.assertEqual(metadata._get_nodata_value(var_with_rio_std), -5555.0)

        # variable where rio exists but nodata is None
        var_rio_none = xr.DataArray(np.array([1, 2, 3]))
        mock_rio_none = mock.Mock()
        mock_rio_none.encoded_nodata = None
        mock_rio_none.nodata = None
        with mock.patch.object(xr.DataArray, "rio", new_callable=mock.PropertyMock, return_value=mock_rio_none):
            self.assertIsNone(metadata._get_nodata_value(var_rio_none))

        # variable without any nodata information
        class MockVar:
            def __init__(self):
                self.attrs = {}
                self.encoding = {}

        var_without_rio = MockVar()
        self.assertIsNone(metadata._get_nodata_value(var_without_rio))

    def test_build_cube_metadata(self):
        """Test cube dimensions, variables and projection metadata"""

        dims, vars_, proj_info = metadata.build_cube_metadata(self.xd_dict)

        self.assertIn("x", dims)
        self.assertIn("y", dims)
        self.assertIn("time", dims)

        self.assertEqual(dims["x"]["type"], "spatial")
        self.assertEqual(dims["x"]["axis"], "x")

        self.assertEqual(dims["y"]["type"], "spatial")
        self.assertEqual(dims["y"]["axis"], "y")

        self.assertEqual(dims["time"]["type"], "temporal")

        if "extent" in dims["x"]:
            self.assertEqual(len(dims["x"]["extent"]), 2)

        if "step" in dims["x"]:
            self.assertIsInstance(dims["x"]["step"], (int, float))

        self.assertIn("band_data", vars_)
        self.assertEqual(vars_["band_data"]["type"], "data")

        self.assertIn("latitude", vars_)
        self.assertIn("longitude", vars_)

        self.assertEqual(vars_["latitude"]["type"], "auxiliary")
        self.assertEqual(vars_["longitude"]["type"], "auxiliary")

        self.assertEqual(vars_["latitude"]["description"], "Latitude")
        self.assertEqual(vars_["longitude"]["description"], "Longitude")

        self.assertIn("dimensions", vars_["latitude"])
        self.assertIsInstance(vars_["latitude"]["dimensions"], list)

        self.assertEqual(proj_info["proj:code"], "EPSG:4326")
        self.assertIn("proj:shape", proj_info)
        self.assertIsInstance(proj_info["proj:shape"], list)

    def test_aux_variable_not_added_if_dimension(self):
        """latitude/longitude must not be added as auxiliary if they are dimensions"""

        ds = xr.Dataset(
            data_vars={"band_data": (("latitude",), [1, 2, 3])},
            coords={"latitude": [10, 20, 30]},
        )

        xd = XarrayDict({"test": ds})

        dims, vars_, _ = metadata.build_cube_metadata(xd)

        self.assertIn("latitude", dims)
        self.assertNotIn("latitude", vars_)

    def test_build_bands(self):
        """Test bands generation"""
        bands = metadata.build_bands({"ds": self.ds_1d})
        self.assertEqual(len(bands), 4)
        self.assertTrue(all("name" in b for b in bands))

    def test_merge_bands(self):
        """Test that existing bands are merged correctly with new bands"""
        existing = [{"name": "B1"}, {"name": "B2"}]
        new = [{"name": "B1"}, {"name": "B2"}, {"name": "B3"}]
        merged = metadata.merge_bands(existing, new)
        self.assertEqual(len(merged), 3)
        self.assertEqual(merged[0]["name"], "B1")
        self.assertEqual(merged[2]["name"], "B3")

    def test_build_bands_no_band_dim(self):
        """If no 'band' dimension, should fallback to number of data_vars"""
        ds_simple = xr.Dataset({"a": (("x",), [1, 2]), "b": (("x",), [3, 4])})
        bands = metadata.build_bands({"simple": ds_simple})
        self.assertEqual(len(bands), 2)
        self.assertEqual(bands[0]["name"], "band1")
        self.assertEqual(bands[1]["name"], "band2")
