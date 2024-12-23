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

from pathlib import Path
from tempfile import TemporaryDirectory

import xarray as xr

from eodag_cube.types import XarrayDict
from tests import EODagTestCase
from tests.context import AwsDownload, EOProduct, PluginConfig, path_to_uri
from tests.utils import populate_directory_with_heterogeneous_files


class TestEOProductXarray(EODagTestCase):
    @classmethod
    def setUpClass(cls):
        super(TestEOProductXarray, cls).setUpClass()
        cls.tmp_dir = TemporaryDirectory(prefix="eodag-cube-tests")

    @classmethod
    def tearDownClass(cls):
        super(TestEOProductXarray, cls).tearDownClass()
        cls.tmp_dir.cleanup()

    def test_to_xarray_local(self):
        """to_xarray must build a Dataset from found local paths"""
        product = EOProduct(
            self.provider, self.eoproduct_props, productType=self.product_type
        )
        product.register_downloader(AwsDownload("foo", PluginConfig()), None)
        product.location = path_to_uri(self.tmp_dir.name)
        populate_directory_with_heterogeneous_files(self.tmp_dir.name)

        xarray_dict = product.to_xarray()

        self.assertIsInstance(xarray_dict, XarrayDict)
        self.assertEqual(len(xarray_dict), 2)
        for key, value in xarray_dict.items():
            self.assertIn(Path(key).suffix, {".nc", ".jp2"})
            self.assertIsInstance(value, xr.Dataset)

        for k, ds in xarray_dict.items():
            ds.close()
            if k in xarray_dict._files:
                xarray_dict._files[k].close()
