from typing import Any, Optional

import numpy as np
from xarray import DataArray, Dataset

from eodag_cube.types import XarrayDict


def extract_projection_info(ds: Dataset) -> dict[str, Any]:
    """
    Extract projection information from an xarray.Dataset.

    :param ds: xarray.Dataset to extract projection information from
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
    proj_info["proj:shape"] = list(ds.sizes.values())
    return proj_info


def _get_nodata_value(var: DataArray) -> Optional[float]:
    """
    Get nodata value from a variable's attributes or return a default value.

    :param var: variable to get nodata value from
    :return: nodata value
    """
    if "nodata" in var.attrs:
        return float(var.attrs["nodata"])
    elif "_FillValue" in var.encoding:
        return float(var.encoding["_FillValue"])
    elif "missing_value" in var.encoding:
        return float(var.encoding["missing_value"])
    else:
        return None


def set_variables(ds: Dataset) -> dict:
    """
    Build cube:variables from a dict of xarray.Dataset.
    :return: variables_dict
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
        if no_data := _get_nodata_value(var):
            variables[str(var_name)]["nodata"] = no_data

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
            if no_data := _get_nodata_value(var):
                variables[aux_name]["nodata"] = no_data

    return variables


def build_cube_metadata(ds_dict: XarrayDict) -> tuple[dict, dict, dict]:
    """
    Build cube:dimensions and cube:variables from a dict of xarray.Dataset.

    :param ds_dict: dictionary of xarray.Dataset
    :return: tuple (dimensions_dict, variables_dict)
    """
    dimensions: dict[str, dict] = {}
    variables: dict[str, dict] = {}

    for ds in ds_dict.values():
        proj_info: dict[str, Any] = extract_projection_info(ds)

        # Dimensions
        for dim_name in ds.sizes.keys():
            dim_name_str = str(dim_name)

            # Type
            dim_type = (
                "spatial"
                if dim_name_str in ("x", "y", "lon", "lat")
                else "temporal"
                if dim_name_str == "time"
                else "other"
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

                dim_entry["reference_system"] = proj_info.get("proj:code", "EPSG:4326")

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
                            dim_entry["step"] = (
                                float(diffs[0]) if np.issubdtype(values.dtype, np.number) else str(diffs[0])
                            )
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
    """
    merged = []

    for i, band in enumerate(existing_bands):
        band = dict(band)
        band.setdefault("name", f"band{i + 1}")
        merged.append(band)

    for i in range(len(existing_bands), len(new_bands)):
        merged.append(new_bands[i])

    return merged
