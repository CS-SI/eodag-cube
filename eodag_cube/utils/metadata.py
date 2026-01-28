# -*- coding: utf-8 -*-
# Copyright 2026, CS GROUP - France, http://www.c-s.fr
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
"""Metadata-related utilities for eodag-cube."""

from math import isnan
from typing import Any, Union

import numpy as np
from xarray import DataArray, Dataset

from eodag_cube.types import XarrayDict


def extract_projection_info(ds: Dataset) -> dict[str, Any]:
    """
    Extract projection information from a :class:`xarray.Dataset`.

    :param ds: :class:`xarray.Dataset` to extract projection information from
    :return: dictionary with projection information
    """
    proj_info: dict[str, Any] = {}

    epsg_code = 4326
    proj_bbox = None

    if hasattr(ds, "rio") and ds.rio.crs is not None:
        epsg_code = ds.rio.crs.to_epsg() or 4326
        try:
            proj_bbox = list(ds.rio.bounds())
        except Exception:
            proj_bbox = None

    proj_info["proj:code"] = f"EPSG:{epsg_code}"
    if proj_bbox is not None:
        proj_info["proj:bbox"] = proj_bbox
    if "x" in ds.sizes and "y" in ds.sizes:
        proj_info["proj:shape"] = [ds.sizes["y"], ds.sizes["x"]]
    return proj_info


def _get_nodata_value(var: DataArray) -> Union[float, str, None]:
    """
    Get nodata value from a variable's attributes or return a default value.

    :param var: variable to get nodata value from
    :return: nodata value
    """
    if "nodata" in var.attrs:
        value = var.attrs["nodata"]
    elif "_FillValue" in var.encoding:
        value = var.encoding["_FillValue"]
    elif "missing_value" in var.encoding:
        value = var.encoding["missing_value"]
    elif hasattr(var, "rio"):
        value = getattr(var.rio, "encoded_nodata", None)
        if value is None:
            value = getattr(var.rio, "nodata", None)
    else:
        return None

    if value is None:
        return None

    # handle NaN
    value = float(value)
    if isnan(value):
        return str(value)

    return value


def set_variables(ds: Dataset) -> dict[str, Any]:
    """
    Set variables metadata from a :class:`xarray.Dataset`.

    :param ds: :class:`xarray.Dataset` to extract variables metadata from
    :return: dictionary with variables metadata
    """
    variables: dict[str, dict] = {}
    auxiliary_geo_vars: dict[str, str] = {
        "latitude": "Latitude",
        "longitude": "Longitude",
    }
    for var_name, var in ds.data_vars.items():
        variables[str(var_name)] = {
            "dimensions": list(var.dims),
            "type": "data",
            "data_type": str(var.dtype),
        }
        if desc := var.attrs.get("description"):
            variables[str(var_name)]["description"] = desc
        variables[str(var_name)]["nodata"] = _get_nodata_value(var)

    for aux_name, desc in auxiliary_geo_vars.items():
        if aux_name in ds:
            var = ds[aux_name]

            if aux_name in variables:
                continue
            if aux_name in ds.dims:
                continue

            variables[aux_name] = {
                "dimensions": list(var.dims),
                "type": "auxiliary",
                "description": desc,
                "data_type": str(var.dtype),
            }
            variables[aux_name]["nodata"] = _get_nodata_value(var)

    return variables


def build_cube_metadata(ds: Dataset) -> tuple[dict, dict, dict]:
    """
    Build datacube and projection metadata from given :class:`xarray.Dataset`.

    :param ds: input xarray dataset
    :return: tuple of 3 dicts for cube dimensions, cube variables and projection info
    """
    dimensions: dict[str, dict] = {}
    variables: dict[str, dict] = {}

    proj_info: dict[str, Any] = extract_projection_info(ds)

    # Dimensions
    for dim_name in ds.sizes.keys():
        dim_name_str = str(dim_name)

        # Type
        dim_type = (
            "spatial" if dim_name_str in ("x", "y", "lon", "lat") else "temporal" if dim_name_str == "time" else "other"
        )

        dim_entry: dict[str, Any] = {"type": dim_type}

        if dim_type == "spatial":
            # Axis
            if dim_name_str in ("x", "lon"):
                dim_entry["axis"] = "x"
            elif dim_name_str in ("y", "lat"):
                dim_entry["axis"] = "y"
            elif dim_name_str == "z":
                dim_entry["axis"] = "z"

            proj_code = proj_info.get("proj:code", "EPSG:4326")
            try:
                dim_entry["reference_system"] = int(proj_code.split(":")[-1])
            except ValueError:
                pass

        if dim_name_str in ds.coords:
            values = ds[dim_name_str].values
            if values.ndim == 1:
                if values.size <= 10:
                    dim_entry["values"] = values.tolist()
                else:
                    dim_entry["extent"] = (
                        [float(values.min()), float(values.max())]
                        if np.issubdtype(values.dtype, np.number)
                        else [str(values.min()), str(values.max())]
                    )
                    diffs = np.diff(values)
                    if np.allclose(diffs, diffs[0]):
                        dim_entry["step"] = float(diffs[0]) if np.issubdtype(values.dtype, np.number) else str(diffs[0])
            else:
                dim_entry["extent"] = [float(np.nanmin(values)), float(np.nanmax(values))]

        dimensions[dim_name_str] = dim_entry

    # Variables
    var_ds = set_variables(ds)
    variables.update(var_ds)

    return dimensions, variables, proj_info


def build_bands(xd: XarrayDict) -> list[dict]:
    """
    Build STAC bands metadata from xarray datasets.

    If names are not available, use generic band names.

    :param xd: input xarray dict
    :return: list of bands metadata
    """
    band_count = 0

    for ds in xd.values():
        for var in ds.data_vars.values():
            for dim in var.dims:
                if str(dim).lower() in ("band", "bands"):
                    band_count = ds.sizes[dim]
                    break
            if band_count:
                break

        if band_count:
            break

    if band_count == 0:
        band_count = len(next(iter(xd.values())).data_vars)

    return [{"name": f"band{i + 1}"} for i in range(band_count)]


def merge_bands(existing_bands: list[dict], new_bands: list[dict]) -> list[dict]:
    """
    Merge existing bands metadata with newly generated ones from xarray.

    Existing bands metadata take precedence over generated ones.

    :param existing_bands: existing bands metadata
    :param new_bands: newly generated bands metadata
    :return: merged bands metadata
    """
    merged = []

    for i, band in enumerate(existing_bands):
        band = dict(band)
        band.setdefault("name", f"band{i + 1}")
        merged.append(band)

    for i in range(len(existing_bands), len(new_bands)):
        merged.append(new_bands[i])

    return merged
