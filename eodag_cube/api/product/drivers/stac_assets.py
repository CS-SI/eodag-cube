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
import re

from eodag.api.product.drivers.base import DatasetDriver
from eodag.utils.exceptions import AddressNotFound


class StacAssets(DatasetDriver):
    """Driver for Stac Assets"""

    def get_data_address(self, eo_product, band):
        """Get the address of a subdataset for a STAC provider product.

        See :func:`~eodag.api.product.drivers.base.DatasetDriver.get_data_address` to get help on the formal
        parameters.
        """
        error_message = ""

        # try using exact
        p = re.compile(rf"^{band}$", re.IGNORECASE)
        matching_keys = [
            s
            for s in eo_product.assets.keys()
            if (
                (
                    "roles" in eo_product.assets[s]
                    and "data" in eo_product.assets[s]["roles"]
                )
                or ("roles" not in eo_product.assets[s])
            )
            and p.match(s)
        ]
        if len(matching_keys) == 1:
            return eo_product.assets[matching_keys[0]]["href"]
        else:
            error_message += (
                rf"{len(matching_keys)} assets keys found matching {p} AND "
            )

            # try to find keys containing given band
            p = re.compile(rf"^.*{band}.*$", re.IGNORECASE)
            matching_keys = [
                s
                for s in eo_product.assets.keys()
                if (
                    (
                        "roles" in eo_product.assets[s]
                        and "data" in eo_product.assets[s]["roles"]
                    )
                    or ("roles" not in eo_product.assets[s])
                )
                and p.match(s)
            ]
            if len(matching_keys) == 1:
                return eo_product.assets[matching_keys[0]]["href"]
            else:
                raise AddressNotFound(
                    rf"Please adapt given band parameter ('{band}') to match only one asset: {error_message}"
                    rf"{len(matching_keys)} assets keys found matching {p}"
                )
