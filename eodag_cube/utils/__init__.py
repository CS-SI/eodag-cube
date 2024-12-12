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

import logging
import mimetypes
import os
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, List, Mapping, Optional, cast
from urllib.parse import urlparse

import fsspec
import requests
import rioxarray
import xarray as xr
from fsspec.implementations.local import LocalFileOpener
from rasterio.crs import CRS

from eodag.utils import parse_header
from eodag_cube.types import XarrayDict

if TYPE_CHECKING:
    from io import IOBase

DEFAULT_PROJ = CRS.from_epsg(4326)

logger = logging.getLogger("eodag-cube.utils")


def guess_engines(file: IOBase) -> List[str]:
    """Guess matching xarray engines for fsspec file"""
    filename = None
    # http
    if "https" in file.fs.protocol:
        headers = None
        try:
            resp = requests.head(file.path, **file.kwargs)
            resp.raise_for_status()
        except requests.RequestException:
            pass
        else:
            headers = resp.headers
        if not headers:
            # if HEAD method is not available, try to get a minimal part of the file
            try:
                resp = requests.get(file.path, stream=True, **file.kwargs)
                resp.raise_for_status()
            except requests.RequestException:
                pass
            else:
                headers = resp.headers
        if headers:
            content_disposition = headers.get("content-disposition")
            if content_disposition:
                filename = cast(
                    Optional[str],
                    parse_header(content_disposition).get_param("filename", None),
                )
        if filename is None:
            mime_type = headers.get("content-type", "").split(";")[0]
            if mime_type != "application/octet-stream":
                extension = mimetypes.guess_extension(mime_type)
                if not extension and "grib" in mime_type:
                    extension = ".grib"
                if not extension and "netcdf" in mime_type:
                    extension = ".nc"
                if extension and mime_type:
                    filename = f"foo{extension}"

        if filename is None:
            parts = urlparse(file.path)
            filename = parts._replace(query="").geturl()

    path = filename or file.path

    guessed_engines = []
    for engine, backend in xr.backends.list_engines().items():
        if backend.guess_can_open(path):
            guessed_engines.append(engine)

    return guessed_engines


def try_open_dataset(file: IOBase, **xarray_kwargs: Mapping[str, Any]) -> xr.Dataset:
    """Try opening xarray dataset from fsspec file"""
    if engine := xarray_kwargs.pop("engine", None):
        all_engines = [
            engine,
        ]
    else:
        all_engines = guess_engines(file) or list(xr.backends.list_engines().keys())

    if isinstance(file, LocalFileOpener):
        engines = all_engines

        # use path str as cfgrib does not support IOBase as input
        file_or_path = file.path

        # if no engine was passed, let xarray guess it for local data
        if len(engines) > 1:
            try:
                start = time.time()
                ds = xr.open_dataset(file_or_path, **xarray_kwargs)
                ellapsed = time.time() - start
                logger.debug(
                    f"{file.path} opened using {file.fs.protocol} + guessed engine in {ellapsed:.2f}s"
                )
                return ds

            except Exception as e:
                ellapsed = time.time() - start
                raise ValueError(
                    f"Cannot open local dataset {file.path}: {str(e)}, {ellapsed:.2f}s ellapsed"
                )

    else:
        # remove engines that do not support remote access
        # https://tutorial.xarray.dev/intermediate/remote_data/remote-data.html#supported-format-read-from-buffers-remote-access
        engines = [eng for eng in all_engines if eng not in ["netcdf4", "cfgrib"]]

        file_or_path = file

    # loop for engines on remote data, as xarray does not always guess it right
    for engine in engines:
        # re-open file to prevent I/O operation on closed file
        # (and `closed` attr does not seem up-to-date)
        file = file.fs.open(path=file.path)

        try:
            start = time.time()
            if engine == "rasterio":
                # prevents to read all file in memory since rasterio 1.4.0
                # https://github.com/rasterio/rasterio/issues/3232
                opener = file.fs.open if "s3" not in file.fs.protocol else None
                ds = rioxarray.open_rasterio(
                    getattr(file, "full_name", file.path),
                    opener=opener,
                    **xarray_kwargs,
                )
            else:
                ds = xr.open_dataset(file_or_path, engine=engine, **xarray_kwargs)

        except Exception as e:
            ellapsed = time.time() - start
            logger.debug(
                f"Cannot open {file.path} with {file.fs.protocol} + {engine}: {str(e)}, {ellapsed:.2f}s ellapsed"
            )
        else:
            ellapsed = time.time() - start
            logger.debug(
                f"{file.path} opened using {file.fs.protocol} + {engine} in {ellapsed:.2f}s"
            )
            return ds

    raise ValueError(
        f"None of the engines {engines} could open the dataset at {file.path}."
    )


def build_local_xarray_dict(
    local_path: str, **xarray_kwargs: Mapping[str, Any]
) -> XarrayDict:
    """Build XarrayDict for local data"""
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
        except ValueError as e:
            logger.debug(e)

    return xarray_dict
