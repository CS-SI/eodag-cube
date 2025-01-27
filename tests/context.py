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
"""Explicitly import here everything you want to use from the eodag package

    isort:skip_file
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from eodag import config
from eodag.api.product import EOProduct
from eodag.api.product.drivers.base import NoDriver
from eodag.config import PluginConfig
from eodag_cube.api.product.drivers.generic import GenericDriver
from eodag_cube.api.product.drivers.sentinel2_l1c import Sentinel2L1C
from eodag_cube.api.product.drivers.stac_assets import StacAssets
from eodag_cube.utils import fsspec_file_headers, fsspec_file_extension
from eodag_cube.utils.exceptions import DatasetCreationError
from eodag_cube.utils.xarray import (
    guess_engines,
    try_open_dataset,
)
from eodag.plugins.authentication.base import Authentication
from eodag.plugins.authentication.aws_auth import AwsAuth
from eodag.plugins.authentication.header import HTTPHeaderAuth
from eodag.plugins.authentication.qsauth import HttpQueryStringAuth
from eodag.plugins.download.base import Download
from eodag.plugins.download.aws import AwsDownload
from eodag.utils import (
    DEFAULT_PROJ,
    path_to_uri,
    USER_AGENT,
    DEFAULT_DOWNLOAD_TIMEOUT,
    DEFAULT_DOWNLOAD_WAIT,
    path_to_uri,
)
from eodag.utils.exceptions import (
    AddressNotFound,
    DownloadError,
    UnsupportedDatasetAddressScheme,
)
from tests import TEST_RESOURCES_PATH
