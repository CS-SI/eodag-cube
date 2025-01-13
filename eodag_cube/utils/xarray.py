# -*- coding: utf-8 -*-
# Copyright 2024, CS GROUP - France, http://www.c-s.fr
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
"""Xarray-related utilities"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

import fsspec
import rioxarray
import xarray as xr

from eodag_cube.types import XarrayDict
from eodag_cube.utils import fsspec_file_extension
from eodag_cube.utils.exceptions import DatasetCreationError

if TYPE_CHECKING:
    from fsspec.core import OpenFile

logger = logging.getLogger("eodag-cube.utils.xarray")


def guess_engines(file: OpenFile) -> list[str]:
    """Guess matching xarray engines for fsspec OpenFile

    :param file: fsspec https OpenFile
    :returns: engines list
    """
    ext = fsspec_file_extension(file)

    guessed_engines = []
    for engine, backend in xr.backends.list_engines().items():
        # xarray backends check path file extension
        if backend.guess_can_open(f"foo{ext}"):
            guessed_engines.append(engine)

    return guessed_engines


def try_open_dataset(file: OpenFile, **xarray_kwargs: dict[str, Any]) -> xr.Dataset:
    """Try opening xarray dataset from fsspec OpenFile

    :param file: fsspec https OpenFile
    :param xarray_kwargs: (optional) keyword arguments passed to xarray.open_dataset
    :returns: opened xarray dataset
    """
    LOCALFILE_ONLY_ENGINES = ["netcdf4", "cfgrib"]

    if engine := xarray_kwargs.pop("engine", None):
        all_engines = [
            engine,
        ]
    else:
        all_engines = guess_engines(file) or list(xr.backends.list_engines().keys())

    if "file" in file.fs.protocol:
        engines = all_engines

        # use path str as cfgrib does not support fsspec OpenFile as input
        file_or_path = file.path

        # if no engine was passed, let xarray guess it for local data
        if len(engines) > 1:
            try:
                ds = xr.open_dataset(file_or_path, **xarray_kwargs)
                logger.debug(
                    f"{file.path} opened using {file.fs.protocol} + guessed engine"
                )
                return ds

            except Exception as e:
                raise DatasetCreationError(
                    f"Cannot open local dataset {file.path}: {str(e)}"
                ) from e

    else:
        # remove engines that do not support remote access
        # https://tutorial.xarray.dev/intermediate/remote_data/remote-data.html#supported-format-read-from-buffers-remote-access
        engines = [eng for eng in all_engines if eng not in LOCALFILE_ONLY_ENGINES]

        file_or_path = file

    # loop for engines on remote data, as xarray does not always guess it right
    for engine in engines:
        # re-open file to prevent I/O operation on closed file
        # (and `closed` attr does not seem up-to-date)
        file = file.fs.open(path=file.path)

        try:
            if engine == "rasterio":
                # prevents to read all file in memory since rasterio 1.4.0
                # https://github.com/rasterio/rasterio/issues/3232
                opener = file.fs.open if "s3" not in file.fs.protocol else None
                da = rioxarray.open_rasterio(
                    getattr(file, "full_name", file.path),
                    opener=opener,
                    **xarray_kwargs,
                )
                ds = da.to_dataset(name="band_data")
            else:
                ds = xr.open_dataset(file_or_path, engine=engine, **xarray_kwargs)

        except Exception as e:
            logger.debug(
                f"Cannot open {file.path} with {file.fs.protocol} + {engine}: {str(e)}"
            )
        else:
            logger.debug(f"{file.path} opened using {file.fs.protocol} + {engine}")
            return ds

    raise DatasetCreationError(
        f"None of the engines {engines} could open the dataset at {file.path}."
    )


def build_local_xarray_dict(
    local_path: str, **xarray_kwargs: dict[str, Any]
) -> XarrayDict:
    """Build XarrayDict for local data

    :param local_path: local path to scan for data
    :param xarray_kwargs: (optional) keyword arguments passed to xarray.open_dataset
    :returns: a dictionary of :class:`xarray.Dataset`
    """
    xarray_dict = XarrayDict()
    fs = fsspec.filesystem("file")

    if os.path.isfile(local_path):
        files = [
            local_path,
        ]
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
            xarray_dict._files[key] = file
        except DatasetCreationError as e:
            logger.debug(e)

    return xarray_dict
