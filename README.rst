.. image:: https://badge.fury.io/py/eodag-cube.svg
    :target: https://badge.fury.io/py/eodag-cube

.. image:: https://img.shields.io/pypi/l/eodag-cube.svg
    :target: https://pypi.org/project/eodag-cube/

.. image:: https://img.shields.io/pypi/pyversions/eodag-cube.svg
    :target: https://pypi.org/project/eodag-cube/

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
    product_type = 'S2_MSI_L1C'
    footprint = {'lonmin': 1, 'latmin': 43.5, 'lonmax': 2, 'latmax': 44}
    start, end = '2020-06-04', '2020-06-05'
    search_results, _ = dag.search(productType=product_type, geom=footprint, start=start, end=end)
    data = search_results[0].get_data(
        crs=CRS.from_epsg(4326), 
        resolution=0.0006, 
        band="B01", 
        extent=footprint
    )
    print(data)

    <xarray.DataArray (dim_0: 750, dim_1: 566)>
    array([[1426, 1577, 1672, ..., 6219, 5916, 5281],
        [1416, 1668, 1830, ..., 6277, 6022, 5621],
        [1502, 1896, 2107, ..., 6287, 6081, 5890],
        ...,
        [1878, 2475, 2922, ..., 1605, 1604, 1654],
        [1732, 2219, 2630, ..., 1670, 1659, 1664],
        [1548, 1832, 2134, ..., 1722, 1732, 1718]], dtype=uint16)


LICENSE
=======

EODAG is licensed under Apache License v2.0.
See LICENSE file for details.


AUTHORS
=======

EODAG is developed by `CS GROUP - France <https://www.c-s.fr>`_.

