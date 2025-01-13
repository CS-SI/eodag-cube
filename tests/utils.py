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

import os
import shutil

# All tests files should import mock from this place
from unittest import mock  # noqa

from tests import TEST_RESOURCES_PATH


def no_blanks(string):
    """Removes all the blanks in string

    :param string: A string to remove blanks from
    :type string: str

    :returns the same string with all blank characters removed
    """
    return string.replace("\n", "").replace("\t", "").replace(" ", "")


def populate_directory_with_heterogeneous_files(destination):
    """
    Put various files in the destination directory:
    - a NetCDF file
    - a JPEG2000 file
    - an XML file
    """
    # Copy all files from a grib product
    cams_air_quality_product_path = os.path.join(
        TEST_RESOURCES_PATH,
        "products",
        "cams-europe-air-quality-forecasts",
    )
    shutil.copytree(cams_air_quality_product_path, destination, dirs_exist_ok=True)

    # Copy files from an S2A product
    s2a_path = os.path.join(
        TEST_RESOURCES_PATH,
        "products",
        "S2A_MSIL1C_20180101T105441_N0206_R051_T31TDH_20180101T124911.SAFE",
    )
    shutil.copytree(s2a_path, destination, dirs_exist_ok=True)
