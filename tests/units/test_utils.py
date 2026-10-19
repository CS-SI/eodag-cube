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

import io
import subprocess
import sys
import textwrap
import unittest
from pathlib import Path

import fsspec.implementations
import fsspec.implementations.http
import numpy as np
import responses
import xarray as xr
from fsspec.core import OpenFile

from eodag_cube.types import XarrayDict
from eodag_cube.utils import metadata
from tests import TEST_RESOURCES_PATH
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

    def test_fsspec_file_headers_streams_and_closes_responses(self):
        fs = fsspec.filesystem("https")
        for head_status, get_status in [(200, 200), (405, 200), (405, 500)]:
            for options in [{}, {"timeout": (1, 2), "stream": False}]:
                with self.subTest(head_status=head_status, get_status=get_status, options=options):
                    file = OpenFile(fs, "https://foo/bar.baz")
                    file.kwargs = options.copy()
                    with responses.RequestsMock(assert_all_requests_are_fired=False) as mocked:
                        mocked.add(responses.HEAD, file.path, status=head_status, headers={"a-header": "from-head"})
                        mocked.add(
                            responses.GET,
                            file.path,
                            status=get_status,
                            headers={"a-header": "from-get"},
                            body=b"unread raster data",
                        )
                        headers = fsspec_file_headers(file)
                        methods = [call.request.method for call in mocked.calls]
                        self.assertEqual(methods, ["HEAD"] if head_status == 200 else ["HEAD", "GET"])
                        for call in mocked.calls:
                            self.assertTrue(call.request.req_kwargs["stream"])
                            self.assertEqual(call.request.req_kwargs["timeout"], options.get("timeout", (5, 30)))
                            self.assertTrue(call.response.raw.closed)
                            self.assertIs(call.response._content, False)
                    self.assertEqual(file.kwargs, options)
                    if head_status == 200:
                        self.assertEqual(headers["a-header"], "from-head")
                    elif get_status == 200:
                        self.assertEqual(headers["a-header"], "from-get")
                    else:
                        self.assertIsNone(headers)

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
    def test_xarray_dict_file_handles_are_instance_scoped(self):
        first_file = mock.Mock()
        second_file = mock.Mock()
        first = XarrayDict({"same": xr.Dataset()})
        second = XarrayDict({"same": xr.Dataset()})
        first._files["same"] = first_file
        second._files["same"] = second_file

        first.close()

        first_file.close.assert_called_once_with()
        second_file.close.assert_not_called()

    def test_zip_raster_lazy_read_after_concurrent_open(self):
        archive = next((Path(TEST_RESOURCES_PATH) / "products" / "as_archive").glob("*.zip"))
        code = textwrap.dedent(
            """
            import sys
            from concurrent.futures import ThreadPoolExecutor
            from types import SimpleNamespace
            from unittest.mock import Mock, patch
            from zipfile import ZipFile

            from fsspec.implementations.zip import ZipFileSystem
            from eodag_cube.utils.xarray import try_open_dataset

            archive = sys.argv[1]
            with ZipFile(archive) as zip_file:
                member = next(path for path in zip_file.namelist() if path.endswith(".jp2"))

            def open_band():
                url = "zip+s3://bucket/product.zip!" + member
                fs = Mock(protocol="s3", storage_options={})
                fs.open.side_effect = OSError("Read through the ZIP opener")
                file = SimpleNamespace(fs=fs, path=url, full_name=url)
                return try_open_dataset(file, engine="rasterio")

            def open_zip(**kwargs):
                return ZipFileSystem(fo=archive, skip_instance_cache=True)

            with patch("fsspec.implementations.zip.ZipFileSystem", side_effect=open_zip):
                with ThreadPoolExecutor(max_workers=2) as executor:
                    futures = [executor.submit(open_band) for unused in range(2)]
                    datasets = [future.result() for future in futures]

            for dataset in datasets:
                assert not dataset.band_data.variable._in_memory
                clipped = dataset.isel(x=slice(0, 16), y=slice(0, 16))
                clipped.load()
                assert clipped.band_data.shape == (1, 16, 16)
                projected = clipped.rio.reproject("EPSG:4326")
                assert projected.rio.crs.to_epsg() == 4326
                dataset.close()
            """
        )
        result = subprocess.run(
            [sys.executable, "-X", "faulthandler", "-c", code, str(archive)],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=Path(__file__).parents[2],
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_seekable_zip_opener_preserves_lazy_member_access(self):
        from eodag_cube.utils.xarray import _SeekableZipOpener

        member = io.BytesIO(b"raster data")
        zip_fs = mock.Mock()
        zip_fs.open.return_value = member
        opener = _SeekableZipOpener(zip_fs)

        opened = opener.open("band.jp2")

        self.assertIs(opened, member)
        self.assertTrue(opened._seekable)
        opened.seek(7)
        self.assertEqual(opened.read(), b"data")
        zip_fs.open.assert_called_once_with("band.jp2", "rb")
        zip_fs.cat_file.assert_not_called()

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

        # cfgrib relies on eccodes which may not be available on all platforms
        if "cfgrib" in all_engines:
            file = OpenFile(fs, "https://foo/bar.grib")
            self.assertIn("cfgrib", guess_engines(file))

    @mock.patch("eodag_cube.utils.xarray.guess_engines", return_value=["h5netcdf", "foo"])
    @mock.patch("fsspec.open")
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
    @mock.patch("fsspec.open")
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
    @mock.patch("fsspec.open")
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
            mock_open.assert_not_called()

    @mock.patch("eodag_cube.utils.xarray.guess_engines", return_value=["h5netcdf", "foo"])
    @mock.patch("fsspec.open")
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
            mock_open.assert_not_called()

    @mock.patch("eodag_cube.utils.xarray.guess_engines", return_value=["h5netcdf", "scipy"])
    def test_try_open_dataset_remote_retry_handles(self, mock_guess_engines):
        for succeeds in [True, False]:
            with self.subTest(succeeds=succeeds):
                fs = mock.Mock(protocol="https")
                file = mock.Mock(fs=fs, path="https://foo/bar.nc")
                retry_file = fs.open.return_value
                dataset = xr.Dataset()
                close_backend = mock.Mock()
                dataset.set_close(close_backend)
                results = [ValueError("first backend failed"), dataset if succeeds else ValueError("retry failed")]

                with mock.patch("eodag_cube.utils.xarray.xr.open_dataset", side_effect=results) as mock_open_dataset:
                    if succeeds:
                        self.assertIs(try_open_dataset(file), dataset)
                        retry_file.close.assert_not_called()
                        close_backend.assert_not_called()
                        dataset.close()
                        close_backend.assert_called_once_with()
                    else:
                        with self.assertRaises(DatasetCreationError):
                            try_open_dataset(file)

                self.assertEqual(
                    mock_open_dataset.call_args_list,
                    [mock.call(file, engine="h5netcdf"), mock.call(retry_file, engine="scipy")],
                )
                fs.open.assert_called_once_with(path=file.path)
                file.close.assert_called_once_with()
                retry_file.close.assert_called_once_with()

    @mock.patch("eodag_cube.utils.xarray.guess_engines", return_value=["rasterio"])
    @mock.patch("fsspec.open")
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
            close_raster = mock.Mock()
            mock_open_rio.return_value.set_close(close_raster)
            ds = try_open_dataset(file, foo="bar", baz="qux")
            self.assertIsInstance(ds, xr.Dataset)
            close_raster.assert_called_once_with()
            ds.close()
            self.assertEqual(close_raster.call_count, 2)
            mock_open_rio.assert_called_once_with(
                file.path, opener=mock_open, mask_and_scale=True, foo="bar", baz="qux"
            )
            mock_open.assert_not_called()


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
        self.assertNotIn("proj:shape", proj_info)
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

        # variable with nodata nan attribute
        var_with_nodata = xr.DataArray(
            np.array([1, 2, 3]),
            attrs={"nodata": float("NaN")},
        )
        var_with_nodata.encoding = {}
        self.assertEqual(metadata._get_nodata_value(var_with_nodata), "nan")

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

    def test_build_stac_metadata_1d(self):
        """Test cube dimensions, variables and projection metadata"""

        stac_mtd = metadata.build_stac_metadata(self.ds_1d)

        self.assertIn("x", stac_mtd["cube:dimensions"])
        self.assertIn("time", stac_mtd["cube:dimensions"])

        self.assertEqual(stac_mtd["cube:dimensions"]["x"]["type"], "spatial")
        self.assertEqual(stac_mtd["cube:dimensions"]["x"]["axis"], "x")

        self.assertEqual(stac_mtd["cube:dimensions"]["time"]["type"], "temporal")

        if "extent" in stac_mtd["cube:dimensions"]["x"]:
            self.assertEqual(len(stac_mtd["cube:dimensions"]["x"]["extent"]), 2)

        if "step" in stac_mtd["cube:dimensions"]["x"]:
            self.assertIsInstance(stac_mtd["cube:dimensions"]["x"]["step"], (int, float))
        self.assertIn("band_data", stac_mtd["cube:variables"])
        self.assertEqual(stac_mtd["cube:variables"]["band_data"]["type"], "data")

        self.assertIn("latitude", stac_mtd["cube:variables"])
        self.assertIn("longitude", stac_mtd["cube:variables"])

        self.assertEqual(stac_mtd["cube:variables"]["latitude"]["type"], "auxiliary")
        self.assertEqual(stac_mtd["cube:variables"]["longitude"]["type"], "auxiliary")

        self.assertEqual(stac_mtd["cube:variables"]["latitude"]["description"], "Latitude")
        self.assertEqual(stac_mtd["cube:variables"]["longitude"]["description"], "Longitude")

        self.assertIn("dimensions", stac_mtd["cube:variables"]["latitude"])
        self.assertIsInstance(stac_mtd["cube:variables"]["latitude"]["dimensions"], list)
        self.assertEqual(stac_mtd["proj:code"], "EPSG:4326")
        self.assertNotIn("proj:shape", stac_mtd)

    def test_build_stac_metadata_2d(self):
        """Test cube dimensions, variables and projection metadata"""

        stac_mtd = metadata.build_stac_metadata(self.ds_2d)

        self.assertIn("x", stac_mtd["cube:dimensions"])
        self.assertIn("y", stac_mtd["cube:dimensions"])

        self.assertEqual(stac_mtd["cube:dimensions"]["x"]["type"], "spatial")
        self.assertEqual(stac_mtd["cube:dimensions"]["x"]["axis"], "x")

        self.assertEqual(stac_mtd["cube:dimensions"]["y"]["type"], "spatial")
        self.assertEqual(stac_mtd["cube:dimensions"]["y"]["axis"], "y")

        if "extent" in stac_mtd["cube:dimensions"]["x"]:
            self.assertEqual(len(stac_mtd["cube:dimensions"]["x"]["extent"]), 2)

        if "step" in stac_mtd["cube:dimensions"]["x"]:
            self.assertIsInstance(stac_mtd["cube:dimensions"]["x"]["step"], (int, float))
        self.assertIn("band_data", stac_mtd["cube:variables"])
        self.assertEqual(stac_mtd["cube:variables"]["band_data"]["type"], "data")

        self.assertEqual(stac_mtd["proj:code"], "EPSG:4326")
        self.assertIn("proj:shape", stac_mtd)
        self.assertEqual(stac_mtd["proj:shape"], [2, 2])

    def test_aux_variable_not_added_if_dimension(self):
        """latitude/longitude must not be added as auxiliary if they are dimensions"""

        ds = xr.Dataset(
            data_vars={"band_data": (("latitude",), [1, 2, 3])},
            coords={"latitude": [10, 20, 30]},
        )

        stac_mtd = metadata.build_stac_metadata(ds)

        self.assertIn("latitude", stac_mtd["cube:dimensions"])
        self.assertNotIn("latitude", stac_mtd["cube:variables"])

    def test_build_bands(self):
        """Test bands generation"""
        bands = metadata.build_bands(self.ds_1d)
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
        bands = metadata.build_bands(ds_simple)
        self.assertEqual(len(bands), 2)
        self.assertEqual(bands[0]["name"], "band1")
        self.assertEqual(bands[1]["name"], "band2")
