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

from tests.context import (
    TEST_RESOURCES_PATH,
    AwsDownload,
    EOProduct,
    PluginConfig,
    path_to_uri,
)
from tests.integration import test_eoproduct_xarray


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


def test_benchmark_to_xarray_local(benchmark):
    case = test_eoproduct_xarray.TestEOProductXarray(methodName="test_to_xarray_local")
    case.setUp()
    products_path = os.path.join(TEST_RESOURCES_PATH, "products")

    def _to_xarray_local():
        product = EOProduct(case.provider, case.eoproduct_props, collection=case.collection)
        product.register_downloader(AwsDownload("foo", PluginConfig()), None)
        product.location = path_to_uri(products_path)
        with product.to_xarray() as xarray_dict:
            return len(xarray_dict)

    try:
        benchmark(_to_xarray_local)
    finally:
        case.tearDown()
