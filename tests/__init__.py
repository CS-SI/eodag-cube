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
import unittest
from unittest import mock  # PY3

from eodag.api.product.metadata_mapping import DEFAULT_METADATA_MAPPING
from shapely import wkt

jp = os.path.join
dirn = os.path.dirname

TEST_RESOURCES_PATH = jp(dirn(__file__), "resources")
RESOURCES_PATH = jp(dirn(__file__), "..", "eodag", "resources")
TESTS_DOWNLOAD_PATH = "/tmp/eodag_tests"

TEST_GRIB_PRODUCT = (
    "CAMS_EAC4_20210101_20210102_4d792734017419d1719b53f4d5b5d4d6888641de"
)
TEST_GRIB_FILENAME = f"{TEST_GRIB_PRODUCT}.grib"
TEST_GRIB_PRODUCT_PATH = os.path.join(
    TEST_RESOURCES_PATH,
    "products",
    TEST_GRIB_PRODUCT,
)
TEST_GRIB_FILE_PATH = os.path.join(TEST_GRIB_PRODUCT_PATH, TEST_GRIB_FILENAME)


class EODagTestCase(unittest.TestCase):
    def setUp(self):
        self.provider = "sobloo"
        self.download_url = "https://sobloo.eu/api/v1/services/download/8ff765a2-e089-465d-a48f-cc27008a0962"
        self.local_filename = (
            "S2A_MSIL1C_20180101T105441_N0206_R051_T31TDH_20180101T124911.SAFE"
        )
        self.local_product_abspath = os.path.abspath(
            jp(TEST_RESOURCES_PATH, "products", self.local_filename)
        )
        self.local_product_as_archive_path = os.path.abspath(
            jp(
                TEST_RESOURCES_PATH,
                "products",
                "as_archive",
                "{}.zip".format(self.local_filename),
            )
        )
        self.local_band_file = jp(
            self.local_product_abspath,
            "GRANULE",
            "L1C_T31TDH_A013204_20180101T105435",
            "IMG_DATA",
            "T31TDH_20180101T105441_B01.jp2",
        )
        # A good valid geometry of a sentinel 2 product around Toulouse
        self.geometry = wkt.loads(
            "POLYGON((0.495928592903789 44.22596415476343, 1.870237286761489 "
            "44.24783068396879, "
            "1.888683014192297 43.25939191053712, 0.536772323136669 43.23826255332707, "
            "0.495928592903789 44.22596415476343))"
        )
        # The footprint requested
        self.footprint = {
            "lonmin": 1.3128662109375002,
            "latmin": 43.65197548731186,
            "lonmax": 1.6754150390625007,
            "latmax": 43.699651229671446,
        }
        self.product_type = "S2_MSI_L1C"
        self.platform = "S2A"
        self.instrument = "MSI"
        self.provider_id = "9deb7e78-9341-5530-8fe8-f81fd99c9f0f"

        self.eoproduct_props = {
            "id": "9deb7e78-9341-5530-8fe8-f81fd99c9f0f",
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [0.495928592903789, 44.22596415476343],
                        [1.870237286761489, 44.24783068396879],
                        [1.888683014192297, 43.25939191053712],
                        [0.536772323136669, 43.23826255332707],
                        [0.495928592903789, 44.22596415476343],
                    ]
                ],
            },
            "productType": self.product_type,
            "platform": "Sentinel-2",
            "platformSerialIdentifier": self.platform,
            "instrument": self.instrument,
            "title": self.local_filename,
            "downloadLink": self.download_url,
        }
        # Put an empty string as value of properties which are not relevant for the
        # tests
        self.eoproduct_props.update(
            {
                key: ""
                for key in DEFAULT_METADATA_MAPPING
                if key not in self.eoproduct_props
            }
        )

        self.requests_http_get_patcher = mock.patch("requests.get", autospec=True)
        self.requests_http_post_patcher = mock.patch("requests.post", autospec=True)
        self.requests_http_get = self.requests_http_get_patcher.start()
        self.requests_http_post = self.requests_http_post_patcher.start()

    def tearDown(self):
        self.requests_http_get_patcher.stop()
        self.requests_http_post_patcher.stop()
        unwanted_product_dir = jp(
            dirn(self.local_product_as_archive_path), self.local_filename
        )
        if os.path.isdir(unwanted_product_dir):
            shutil.rmtree(unwanted_product_dir)

    def override_properties(self, **kwargs):
        """Overrides the properties with the values specified in the input parameters"""
        self.__dict__.update(
            {
                prop: new_value
                for prop, new_value in kwargs.items()
                if prop in self.__dict__ and new_value != self.__dict__[prop]
            }
        )

    def assertHttpGetCalledOnceWith(self, expected_url, expected_params=None):
        """Helper method for doing assertions on requests http get method mock"""
        self.assertEqual(self.requests_http_get.call_count, 1)
        actual_url = self.requests_http_get.call_args[0][0]
        self.assertEqual(actual_url, expected_url)
        if expected_params:
            actual_params = self.requests_http_get.call_args[1]["params"]
            self.assertDictEqual(actual_params, expected_params)

    @staticmethod
    def _tuples_to_lists(shapely_mapping):
        """Transforms all tuples in shapely mapping to lists.

        When doing for example::
            shapely_mapping = geometry.mapping(geom)

        ``shapely_mapping['coordinates']`` will contain only tuples.

        When doing for example::
            geojson_load = geojson.loads(geojson.dumps(obj_with_geo_interface))

        ``geojson_load['coordinates']`` will contain only lists.

        Then this helper exists to transform all tuples in
        ``shapely_mapping['coordinates']`` to lists in-place, so
        that ``shapely_mapping['coordinates']`` can be compared to
        ``geojson_load['coordinates']``
        """
        shapely_mapping["coordinates"] = list(shapely_mapping["coordinates"])
        for i, coords in enumerate(shapely_mapping["coordinates"]):
            shapely_mapping["coordinates"][i] = list(coords)
            coords = shapely_mapping["coordinates"][i]
            for j, pair in enumerate(coords):
                # Coordinates rounded to 6 decimals by geojson lib
                # So rounding coordinates in order to be able to compare
                # coordinates after a `geojson.loads`
                # see https://github.com/jazzband/geojson.git
                pair = tuple(round(i, 6) for i in pair)

                coords[j] = list(pair)
        return shapely_mapping
