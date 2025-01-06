.. image:: https://badge.fury.io/py/eodag-cube.svg
    :target: https://badge.fury.io/py/eodag-cube

.. image:: https://img.shields.io/pypi/l/eodag-cube.svg
    :target: https://pypi.org/project/eodag-cube/

.. image:: https://img.shields.io/pypi/pyversions/eodag-cube.svg
    :target: https://pypi.org/project/eodag-cube/

.. image:: https://mybinder.org/badge_logo.svg
    :target: https://mybinder.org/v2/git/https%3A%2F%2Fgithub.com%2FCS-SI%2Feodag-cube.git/develop?filepath=docs%2Fnotebooks%2Fget_data_basic.ipynb

EODAG-cube
==========

This project is the data-access part of `EODAG <https://github.com/CS-SI/eodag>`_

.. image:: https://eodag.readthedocs.io/en/latest/_static/eodag_bycs.png
    :target: https://github.com/CS-SI/eodag

|


Installation
============

EODAG-cube is on `PyPI <https://pypi.org/project/eodag-cube/>`_::

    python -m pip install eodag-cube

Usage - Python API
==================

Example usage for interacting with the api in your Python code:

.. code-block:: python

    from eodag import EODataAccessGateway
    from rasterio.crs import CRS

    dag = EODataAccessGateway()
    search_criteria = dict(
        provider='earth_search',
        productType='S2_MSI_L1C',
        geom=[1, 43.5, 2, 44],
        start='2020-06-04',
        end='2020-06-05',
    )
    search_results = dag.search(**search_criteria)
    product = search_results[0]
    product

.. image:: docs/_static/eoproduct.png?raw=true
   :alt: EOProduct

Whole product as ``XarrayDict``:

.. code-block:: python

    product.to_xarray()

.. image:: docs/_static/xarray_dict.png?raw=true
   :alt: XarrayDict

Single asset as ``xarray.Dataset``:

.. code-block:: python

    product.assets["blue"].to_xarray()

.. image:: docs/_static/dataset.png?raw=true
   :alt: Dataset

``fsspec.core.OpenFile`` file object:

.. code-block:: python

    product.assets["blue"].get_file_obj()

``<File-like object S3FileSystem, sentinel-s2-l1c/tiles/31/T/DJ/2020/6/4/0/B02.jp2>``

Contribute
==========

If you intend to contribute to eodag-cube source code::

    git clone https://github.com/CS-SI/eodag-cube.git
    cd eodag-cube
    python -m pip install -e .[dev]
    pre-commit install
    tox

LICENSE
=======

EODAG is licensed under Apache License v2.0.
See LICENSE file for details.


AUTHORS
=======

EODAG is developed by `CS GROUP - France <https://www.c-s.fr>`_.
