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
    product_type = 'S2_MSI_L2A_COG'
    footprint = {'lonmin': 1, 'latmin': 43.5, 'lonmax': 2, 'latmax': 44}
    start, end = '2020-06-04', '2020-06-05'
    search_results = dag.search(productType=product_type, geom=footprint, start=start, end=end)
    data = search_results[0].get_data(
        crs=CRS.from_epsg(4326),
        resolution=0.0006,
        band="B01",
        extent=footprint
    )
    print(data)

    <xarray.DataArray (band: 1, y: 833, x: 1666)>
    array([[[  432,   407,   430, ...,     0,     0,     0],
            [  587,   573,   589, ...,     0,     0,     0],
            [  742,   690,   622, ...,     0,     0,     0],
            ...,
            [15264, 15247, 15214, ...,     0,     0,     0],
            [15069, 15084, 15073, ...,     0,     0,     0],
            [14686, 14701, 14722, ...,     0,     0,     0]]], dtype=uint16)
    Coordinates:
    * x            (x) float64 0.9999 1.0 1.001 1.002 ... 1.887 1.887 1.888 1.888
    * y            (y) float64 44.0 44.0 44.0 44.0 44.0 ... 43.5 43.5 43.5 43.5
    * band         (band) int64 1
        spatial_ref  int64 0
    Attributes:
        scale_factor:  1.0
        add_offset:    0.0
        _FillValue:    0

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
