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
"""Miscellaneous utilities to be used throughout eodag.

Everything that does not fit into one of the specialised categories of utilities in
this package should go here
"""
from __future__ import annotations

import os
import glob
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union, Mapping

import fsspec
import xarray as xr
from fsspec.implementations.local import LocalFileOpener
from rasterio.crs import CRS
from eodag.utils.exceptions import DownloadError, UnsupportedDatasetAddressScheme
from eodag_cube.types import XarrayDict

if TYPE_CHECKING:
    from io import IOBase

DEFAULT_PROJ = CRS.from_epsg(4326)

logger = logging.getLogger("eodag-cube.utils")

def try_open_dataset(file: IOBase, **xarray_kwargs: Mapping[str, Any]) -> xr.Dataset:
    """
    """    
    if engine := xarray_kwargs.pop("engine", None):
        engines = [engine,]
    else:
        engines = xr.backends.list_engines()
       
    if isinstance(file, LocalFileOpener):    
        # use path str as cfgrib does not support IOBase as input
        file_or_path = file.path

        # if no engine was passed, let xarray guess it for local data
        if len(engines) != 1:
            try:                
                ds = xr.open_dataset(file_or_path, **xarray_kwargs)
                logger.debug(f"{file.path} opened using {file.fs.protocol} + guessed engine")
                return ds
                
            except Exception as e:
                raise ValueError(f"Cannot open local dataset {file.path}: {str(e)}")

    else:
        file_or_path = file

    # remove engines that do not support remote access
    # https://tutorial.xarray.dev/intermediate/remote_data/remote-data.html#supported-format-read-from-buffers-remote-access
    engines.pop("netcdf4", None)
    engines.pop("cfgrib", None)
    # loop for engines on remote data, as xarray does not always guess it right
    for engine in engines:
        # re-open file to prevent I/O operation on closed file
        # (and `closed` attr does not seem up-to-date)
        file_or_path = file.fs.open(path=file.path)

        try:
            ds = xr.open_dataset(file_or_path, engine=engine, **xarray_kwargs)
            
        except Exception as e:
            logger.debug(f"Cannot open {file.path} with {file.fs.protocol} + {engine}: {str(e)}")
        else:
            logger.debug(f"{file.path} opened using {file.fs.protocol} + {engine}")
            return ds
    
    raise ValueError(f"None of the engines {engines} could open the dataset at {file.path}.")


def build_local_xarray_dict(local_path: str, **xarray_kwargs: Mapping[str, Any]):
    """
    """
    xarray_dict = XarrayDict()
    fs = fsspec.filesystem("file")

    if os.path.isfile(local_path):
        files = [local_path,]
    else:
        files = list(Path(local_path).rglob("*"))

    for file_str in files:
        if not os.path.isfile(file_str):
            continue
        file = fs.open(file_str)
        try:
            ds = try_open_dataset(file, **xarray_kwargs)
            key = os.path.relpath(file_str, local_path)
            xarray_dict[key] = ds
        except ValueError as e:
            logger.debug(e)

    return xarray_dict