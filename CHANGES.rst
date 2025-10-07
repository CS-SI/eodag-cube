===============
Release history
===============

.. _changelog-unreleased:

v0.6.2 (2025-10-07)
===================

Bug Fixes
---------

* S3 conf for endpoint, anon, and requester_pays (`#105`_, `89adb65`_)

.. _#105: https://github.com/CS-SI/eodag-cube/pull/105
.. _89adb65: https://github.com/CS-SI/eodag-cube/commit/89adb6519ab8eaed3b55c52352b1356fa2cea485


.. _changelog-v0.6.1:

v0.6.1 (2025-09-26)
===================

Refactoring
-----------

- AwsAuth and rio_env (#102)

Build System
------------

- EODAG minimal version to 3.9.0

Testing
-------

- PluginConfig init update (#99)

v0.6.0 (2025-05-12)
===================

Major changes since last stable (`v0.5.0 <CHANGES.rst#050-2024-10-10>`_)
------------------------------------------------------------------------

- [v0.6.0b1] New ``get_file_obj()`` and ``to_xarray()`` methods, making ``get_data()`` deprecated (#79)
- [v0.6.0b2] Drivers to EODAG core for assets uniformization (#83)
- [v0.6.0b2] ``EOProduct.rio_env`` method (#85)

Remaining changes since `v0.6.0b2 <CHANGES.rst#060b2-2025-02-03>`_
------------------------------------------------------------------

- Documentation through EODAG readthedocs (#90), updated docstrings (#88)
- Project configuration moved to ``pyproject.toml`` (#93)
- ``ruff`` linter and formatter usage (#94)
- Typing fixes and ``mypy`` usage (#92)
- Various minor fixes and improvements (#89)(#91)(#95)(#96)

v0.6.0b2 (2025-02-03)
=====================

- Drivers to EODAG core for assets uniformization (#83)
- ``EOProduct.rio_env`` method (#85)
- Improved ``XarrayDict`` representation and sorted keys (#81)
- Various minor fixes and improvements (#82)(#84)(#86)

v0.6.0b1 (2025-01-13)
=====================

* New ``get_file_obj()`` and ``to_xarray()`` methods, making ``get_data()`` deprecated (#79)
* s3 endpoint fix (#70)
* ``netcdf4`` and ``cfgrib`` added as dependencies (#69)
* Added python ``3.13`` and removed ``3.8`` support (#67)

v0.5.0 (2024-10-10)
===================

- Support zipped bands in s3 (#62)
- Regex fix in band selection using ``StacAssets`` driver (#61)
- [0.5.0b1] Adapt to ``eodag v3`` search API (#59)

v0.5.0b1 (2024-06-25)
=====================

- Adapt to ``eodag v3`` search API (#59)
- Drivers harmonized regex address retrieval mechanism (#56)
- Fixed ``Asset`` and ``AssetsDict`` import (#54)
- Tests: context imports cleanup (#53), removed unused method (#57)

v0.4.1 (2024-02-29)
===================

- Fixes s3 authentication using GDAL/rasterio environment variables (#50)

v0.4.0 (2024-02-19)
===================

- ``get_data`` directly available on ``product.assets`` (#46)
- Adds windows support (#9)
- Removes limited grpc support (#43)
- Adds python type hints (#45)
- Various minor fixes and improvements (#44)(#47)

v0.3.1 (2023-11-15)
===================

- Allows regex in band selection through ``StacAssets`` driver (#38)
- Removes support for ```python3.7`` and adds support for ``python3.12`` (#39)
- Various minor fixes and improvements (#37)

v0.3.0 (2023-03-17)
===================

- New Generic driver (#26)
- ``get_data()`` ``crs`` and ``resampling`` parameters are now facultative (#25)
- Support python versions from ``3.7`` to ``3.11`` (#34)
- ``pre-commit`` and dependencies updates (#33)

v0.2.1 (2021-08-11)
===================

- Specified minimal ``eodag`` version needed for binder (#22)

v0.2.0 (2021-07-30)
===================

- AWS credentials usage with rasterio (#19)
- Rioxarray usage to read data (#18)
- New StacAssets driver (#17)
- ``get_data()`` now accepts the same types of geometries as ``eodag.search()`` (#16)
- New notebook and readme example (#20)

v0.1.2 (2021-06-18)
===================

- DataArray shape flipped (#12, thanks @ClaudioCiociola)

v0.1.1 (2021-01-15)
===================

- get_data, drivers, and RPC server from eodag

v0.1.0 (2021-01-15)
===================

- First release
