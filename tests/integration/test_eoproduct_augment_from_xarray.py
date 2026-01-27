from unittest import mock

import numpy as np
import xarray as xr

from eodag_cube.types import XarrayDict
from tests import EODagTestCase
from tests.context import EOProduct


class TestEOProductAugmentFromXarray(EODagTestCase):
    def _make_dataset(self, with_band_data=True):
        data_vars = {
            "latitude": xr.DataArray(np.linspace(-90, 90, 4), dims=("pixel",)),
            "longitude": xr.DataArray(np.linspace(-180, 180, 4), dims=("pixel",)),
        }
        if with_band_data:
            data_vars["band_data"] = xr.DataArray(np.ones((4, 2, 2)), dims=("band", "y", "x"))

        return xr.Dataset(
            data_vars=data_vars,
            coords={
                "x": [0, 1],
                "y": [0, 1],
            },
        )

    def test_augment_from_xarray_no_assets(self):
        """augment_from_xarray should populate product properties when no assets"""
        product = EOProduct(self.provider, self.eoproduct_props, collection=self.collection)

        ds = self._make_dataset()
        xd = XarrayDict({"data": ds})

        with mock.patch.object(product, "to_xarray", return_value=xd):
            result = product.augment_from_xarray()

        self.assertIs(result, product)

        # cube metadata
        self.assertIn("cube:dimensions", product.properties)
        self.assertIn("cube:variables", product.properties)

        # projection info at product level
        self.assertIn("proj:code", product.properties)
        self.assertEqual(product.properties["proj:code"], "EPSG:4326")

        # bands always added at product level
        self.assertIn("bands", product.properties)
        self.assertGreater(len(product.properties["bands"]), 0)

    def test_augment_from_xarray_with_assets_and_band_data(self):
        """augment_from_xarray should populate metadata at asset level"""
        product = EOProduct(self.provider, self.eoproduct_props, collection=self.collection)
        product.assets = {
            "asset1": {"roles": ["data"]},
            "asset2": {"roles": ["data-mask"]},
        }

        ds = self._make_dataset(with_band_data=True)
        xd = XarrayDict({"data": ds})

        with mock.patch.object(product, "to_xarray", return_value=xd):
            result = product.augment_from_xarray()

        self.assertIs(result, product)

        for asset in product.assets.values():
            self.assertIn("cube:dimensions", asset)
            self.assertIn("cube:variables", asset)

            # projection info at asset level
            self.assertIn("proj:code", asset)
            self.assertEqual(asset["proj:code"], "EPSG:4326")

            # bands added only because band_data exists
            self.assertIn("bands", asset)
            self.assertGreater(len(asset["bands"]), 0)

    def test_augment_from_xarray_with_assets_no_band_data(self):
        """bands must NOT be added if band_data is absent"""
        product = EOProduct(self.provider, self.eoproduct_props, collection=self.collection)
        product.assets = {
            "asset1": {"roles": ["data"]},
        }

        ds = self._make_dataset(with_band_data=False)
        xd = XarrayDict({"data": ds})

        with mock.patch.object(product, "to_xarray", return_value=xd):
            product.augment_from_xarray()

        asset = product.assets["asset1"]

        self.assertIn("cube:dimensions", asset)
        self.assertIn("cube:variables", asset)

        # No bands because no band_data
        self.assertNotIn("bands", asset)

    def test_augment_from_xarray_asset_to_xarray_failure(self):
        """If to_xarray fails for an asset, it should be skipped"""
        product = EOProduct(self.provider, self.eoproduct_props, collection=self.collection)
        product.assets = {
            "asset1": {"roles": ["data"]},
            "asset2": {"roles": ["data-mask"]},
        }

        def side_effect(asset_key=None, **kwargs):
            if asset_key == "asset1":
                raise Exception("boom")
            return XarrayDict({"data": self._make_dataset()})

        with mock.patch.object(product, "to_xarray", side_effect=side_effect):
            product.augment_from_xarray()

        # asset1 untouched
        self.assertEqual(product.assets["asset1"], {"roles": ["data"]})

        # asset2 populated
        self.assertIn("cube:dimensions", product.assets["asset2"])
        self.assertIn("cube:variables", product.assets["asset2"])

    def test_augment_from_xarray_skips_non_matching_roles(self):
        """Assets with non-matching roles should be skipped (continue)"""
        product = EOProduct(self.provider, self.eoproduct_props, collection=self.collection)

        # Define assets: one matches, one does not
        product.assets = {"matching_asset": {"roles": ["data"]}, "ignored_asset": {"roles": ["thumbnail"]}}

        # Mock to_xarray to return a valid dataset
        ds = self._make_dataset()
        xd = XarrayDict({"data": ds})

        with mock.patch.object(product, "to_xarray", return_value=xd) as mock_to_xarray:
            # We only want to process "data"
            product.augment_from_xarray(roles={"data"})

        # The matching asset should be enriched
        self.assertIn("cube:dimensions", product.assets["matching_asset"])

        # The ignored asset should still be exactly as it was
        self.assertEqual(product.assets["ignored_asset"], {"roles": ["thumbnail"]})
        self.assertNotIn("cube:dimensions", product.assets["ignored_asset"])

        # Verify that to_xarray was only called once (for the matching asset)
        self.assertEqual(mock_to_xarray.call_count, 1)

    def test_augment_from_xarray_skips_when_no_roles_exist(self):
        """If no assets have roles defined, they should be skipped according to current logic"""
        product = EOProduct(self.provider, self.eoproduct_props, collection=self.collection)
        product.assets = {"asset_without_role": {}}  # No "roles" key here

        with mock.patch.object(product, "to_xarray") as mock_to_xarray:
            product.augment_from_xarray(roles={"data"})

        # to_xarray should NEVER be called because roles_exist is False
        # and the logic triggers 'continue'
        mock_to_xarray.assert_not_called()
        self.assertEqual(product.assets["asset_without_role"], {})
