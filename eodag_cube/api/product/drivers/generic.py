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
from pathlib import Path

import rasterio

from eodag.api.product.drivers.base import DatasetDriver
from eodag.utils import uri_to_path
from eodag.utils.exceptions import AddressNotFound, UnsupportedDatasetAddressScheme


class GenericDriver(DatasetDriver):
    """Generic Driver for products that need to be downloaded"""

    def get_data_address(self, eo_product, band):
        """Get the address of a product subdataset.

        See :func:`~eodag.api.product.drivers.base.DatasetDriver.get_data_address` to get help on the formal
        parameters.
        """
        product_location_scheme = eo_product.location.split("://")[0]
        if product_location_scheme == "file":

            filenames = Path(uri_to_path(eo_product.location)).glob(f"**/*{band}*")

            for filename in filenames:
                try:
                    # return the first file readable by rasterio
                    rasterio.drivers.driver_from_extension(filename)
                    return str(filename)
                except ValueError:
                    pass
            raise AddressNotFound
        raise UnsupportedDatasetAddressScheme(
            "eo product {} is accessible through a location scheme that is not yet "
            "supported by eodag: {}".format(eo_product, product_location_scheme)
        )
