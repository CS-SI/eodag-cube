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
"""Miscellaneous utilities to be used throughout eodag-cube.

Everything that does not fit into one of the specialised categories of utilities in
this package should go here
"""
from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any, Optional, cast
from urllib.parse import urlparse

import requests
from rasterio.crs import CRS

from eodag.utils import guess_extension, parse_header

if TYPE_CHECKING:
    from fsspec.core import OpenFile

logger = logging.getLogger("eodag-cube.utils")

DEFAULT_PROJ = CRS.from_epsg(4326)


def fsspec_file_headers(file: OpenFile) -> Optional[dict[str, Any]]:
    """
    Get HTTP headers from fsspec OpenFile

    :param file: fsspec https OpenFile
    :returns: file headers or ``None``
    """
    file_kwargs = getattr(file, "kwargs", {})
    if "https" in file.fs.protocol:
        try:
            resp = requests.head(file.path, **file_kwargs)
            resp.raise_for_status()
        except requests.RequestException:
            pass
        else:
            return resp.headers
        # if HEAD method is not available, try to get a minimal part of the file
        try:
            resp = requests.get(file.path, **file_kwargs)
            resp.raise_for_status()
        except requests.RequestException:
            pass
        else:
            return resp.headers
    return None


def fsspec_file_extension(file: OpenFile) -> Optional[str]:
    """
    Get file extension from fsspec OpenFile

    :param file: fsspec https OpenFile
    :returns: file extension or ``None``
    """
    IGNORED_MIMETYPES = ["application/octet-stream"]
    extension = None
    if headers := fsspec_file_headers(file):
        content_disposition = headers.get("content-disposition")
        if content_disposition:
            filename = cast(
                Optional[str],
                parse_header(content_disposition).get_param("filename", None),
            )
            _, extension = os.path.splitext(filename) if filename else (None, None)
        if not extension:
            mime_type = headers.get("content-type", "").split(";")[0]
            if mime_type not in IGNORED_MIMETYPES:
                extension = guess_extension(mime_type)

    if not extension:
        parts = urlparse(file.path)
        filename = parts._replace(query="").geturl()
        _, extension = os.path.splitext(filename) if filename else (None, None)

    return extension or None
