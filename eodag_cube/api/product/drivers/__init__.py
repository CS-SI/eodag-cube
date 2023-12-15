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
"""EODAG drivers package"""
from eodag.api.product.drivers.base import NoDriver  # noqa
from eodag_cube.api.product.drivers.generic import GenericDriver
from eodag_cube.api.product.drivers.sentinel2_l1c import Sentinel2L1C
from eodag_cube.api.product.drivers.stac_assets import StacAssets

DRIVERS = [
    {
        "criteria": [
            lambda prod: True if len(getattr(prod, "assets", {})) > 0 else False
        ],
        "driver": StacAssets(),
    },
    {
        "criteria": [lambda prod: True if "assets" in prod.properties else False],
        "driver": StacAssets(),
    },
    {
        "criteria": [
            lambda prod: True
            if getattr(prod, "product_type") == "S2_MSI_L1C"
            else False
        ],
        "driver": Sentinel2L1C(),
    },
    {
        "criteria": [lambda prod: True],
        "driver": GenericDriver(),
    },
]
