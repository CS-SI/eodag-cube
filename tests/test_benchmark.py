# -*- coding: utf-8 -*-
# Copyright 2026, CS GROUP - France, https://www.csgroup.eu/
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
import subprocess
import sys
from functools import partial

import aiohttp
import pytest

from tests.context import (
    TEST_RESOURCES_PATH,
    AwsDownload,
    EOProduct,
    PluginConfig,
    path_to_uri,
)
from tests.integration import test_eoproduct_xarray

REMOTE_RASTER_URL = (
    "https://cs-si.github.io/eodag/tests/resources/products/"
    "S2A_MSIL1C_20180101T105441_N0206_R051_T31TDH_20180101T124911/"
    "GRANULE/L1C_T31TDH_A013204_20180101T105435/IMG_DATA/T31TDH_20180101T105441_B01.jp2"
)


def _open_local_datasets(case):
    """Open the local benchmark products without loading their data."""
    product = EOProduct(case.provider, case.eoproduct_props, collection=case.collection)
    product.register_downloader(AwsDownload("foo", PluginConfig()), None)
    product.location = path_to_uri(os.path.join(TEST_RESOURCES_PATH, "products"))
    return product.to_xarray(download_fallback=True)


def _read_datasets(xarray_dict, read_mode):
    """Load full datasets or a 16-by-16 window along their spatial dimensions."""
    loaded_bytes = 0
    for dataset in xarray_dict.values():
        if read_mode == "window":
            indexers = {
                dim: slice(0, 16) for dim in dataset.dims if dim in {"x", "y", "latitude", "longitude", "lat", "lon"}
            }
            dataset = dataset.isel(indexers)
        dataset.load()
        loaded_bytes += dataset.nbytes
    return loaded_bytes


def _benchmark_conversion(benchmark, open_datasets, read_mode):
    """Time opening or loading, with fresh datasets and cleanup for each round."""

    def _open():
        with open_datasets() as xarray_dict:
            return len(xarray_dict)

    def _setup():
        return (open_datasets(), read_mode), {}

    def _teardown(xarray_dict, read_mode):
        xarray_dict.close()

    if read_mode == "open":
        assert benchmark(_open) > 0
    else:
        loaded_bytes = benchmark.pedantic(_read_datasets, setup=_setup, teardown=_teardown, rounds=5, iterations=1)
        assert loaded_bytes > 0
        benchmark.extra_info["loaded_bytes"] = loaded_bytes


def _run_unittest_method(test_case_cls, method_name):
    """Run one unittest test method with isolated setup/teardown."""
    test_case = test_case_cls(methodName=method_name)
    test_case.setUp()
    try:
        getattr(test_case, method_name)()
    finally:
        test_case.tearDown()


def _import_eodag_cube_subprocess():
    """Import eodag_cube in a subprocess (cold start / import cost path)."""
    result = subprocess.run(
        [sys.executable, "-c", "import eodag_cube"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def _import_eodag_public_api_subprocess():
    """Resolve eodag's public product classes in a subprocess.

    When eodag-cube is installed, plain eodag silently resolves
    ``eodag.api.product.EOProduct``/``Asset``/``AssetsDict`` to the eodag-cube
    subclasses (see ``eodag.api.product._resolve``). This measures the
    import/resolution cost that plain eodag users pay just by having eodag-cube
    installed, without calling any eodag-cube-specific method.
    """
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import eodag;"
                "from eodag.api.product import EOProduct, Asset, AssetsDict;"
                "assert EOProduct.__module__.startswith('eodag_cube'), EOProduct.__module__"
            ),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_benchmark_import_eodag_cube_subprocess(benchmark):
    benchmark.pedantic(
        _import_eodag_cube_subprocess,
        rounds=10,
        iterations=1,
    )


def test_benchmark_import_eodag_public_api_subprocess(benchmark):
    benchmark.pedantic(
        _import_eodag_public_api_subprocess,
        rounds=10,
        iterations=1,
    )


def test_benchmark_eoproduct_instantiation(benchmark):
    # ``EOProduct`` here is the class plain eodag also resolves to when eodag-cube
    # is installed. eodag-cube's ``__init__`` rebuilds the assets through its own
    # ``AssetsDict``, so this captures the per-product side-effect paid even when
    # no eodag-cube-specific method (to_xarray/get_data) is ever called.
    case = test_eoproduct_xarray.TestEOProductXarray(methodName="test_to_xarray_local")
    case.setUp()
    try:
        benchmark(lambda: EOProduct(case.provider, case.eoproduct_props, collection=case.collection))
    finally:
        case.tearDown()


@pytest.mark.parametrize("read_mode", ["open", "window", "full"])
def test_benchmark_to_xarray_http(benchmark, read_mode, monkeypatch):
    monkeypatch.setenv("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
    case = test_eoproduct_xarray.TestEOProductXarray(methodName="test_to_xarray_local")
    case.setUp()
    try:
        product = EOProduct(case.provider, case.eoproduct_props, collection=case.collection)
        monkeypatch.setattr(
            product,
            "get_storage_options",
            lambda *args, **kwargs: {
                "path": REMOTE_RASTER_URL,
                "block_size": 16 * 1024,
                "skip_instance_cache": True,
                "client_kwargs": {"timeout": aiohttp.ClientTimeout(total=30), "trust_env": True},
            },
        )
        benchmark.extra_info["source_url"] = REMOTE_RASTER_URL
        _benchmark_conversion(benchmark, partial(product.to_xarray, engine="rasterio"), read_mode)
    finally:
        case.tearDown()


def test_benchmark_eoproduct_assets_population(benchmark):
    # Populating assets goes through eodag-cube's ``AssetsDict.__setitem__``, which
    # wraps every entry in eodag-cube's ``Asset``. This is a side-effect on plain
    # eodag asset construction (e.g. when parsing search results), with no xarray
    # or rasterio usage involved.
    case = test_eoproduct_xarray.TestEOProductXarray(methodName="test_to_xarray_local")
    case.setUp()
    assets = {f"band{i}": {"href": f"http://example.com/band{i}.tif"} for i in range(20)}

    def _populate_assets():
        product = EOProduct(case.provider, case.eoproduct_props, collection=case.collection)
        product.assets.update(assets)
        return len(product.assets)

    try:
        benchmark(_populate_assets)
    finally:
        case.tearDown()


@pytest.mark.parametrize("read_mode", ["open", "window", "full"])
def test_benchmark_to_xarray_local(benchmark, read_mode):
    case = test_eoproduct_xarray.TestEOProductXarray(methodName="test_to_xarray_local")
    case.setUp()
    try:
        _benchmark_conversion(benchmark, partial(_open_local_datasets, case), read_mode)
    finally:
        case.tearDown()
