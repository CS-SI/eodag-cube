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

import os
from pathlib import Path

import xarray as xr

from eodag_cube.types import XarrayDict
from tests import EODagTestCase
from tests.context import (
    TEST_RESOURCES_PATH,
    AwsDownload,
    EOProduct,
    PluginConfig,
    path_to_uri,
)


class TestEOProductXarray(EODagTestCase):
    def test_to_xarray_local(self):
        """to_xarray must build a Dataset from found local paths"""
        product = EOProduct(
            self.provider, self.eoproduct_props, productType=self.product_type
        )
        product.register_downloader(AwsDownload("foo", PluginConfig()), None)

        products_path = os.path.join(
            TEST_RESOURCES_PATH,
            "products",
        )
        product.location = path_to_uri(products_path)

        with product.to_xarray() as xarray_dict:

            self.assertIsInstance(xarray_dict, XarrayDict)
            self.assertEqual(len(xarray_dict), 3)

            for key, value in xarray_dict.items():
                self.assertIn(Path(key).suffix, {".nc", ".grib", ".jp2"})
                self.assertIsInstance(value, xr.Dataset)
                # properties are a included in attrs
                self.assertLessEqual(product.properties.items(), value.attrs.items())

        # check that with statement closed all files
        for file in xarray_dict._files.values():
            self.assertTrue(file.closed)
