===============
Release history
===============

v0.9.1 (2026-10-19)
===================

Bug Fixes
---------

* Avoid downloading file bodies during HTTP header detection (`#137`_, `8986b52`_)

* Filter local assets before opening datasets (`#139`_, `aee4460`_)

* Prevent AWS authentication race in concurrent asset reads (`#145`_, `b16d35e`_)

* Read downloaded product directories without download fallback (`#143`_, `984ae6c`_)

* Scope XarrayDict file handles per instance (`#136`_, `70a98cf`_)

* Support concurrent access to S3 ZIP raster assets (`#135`_, `8a71cd9`_)

* Use fresh file handles for backend retries (`#138`_, `f621fa2`_)

* Use unsigned rasterio AWS session when no credentials are found (`#144`_, `cd98f73`_)

Performance Improvements
------------------------

* Make asset-opening concurrency configurable (`#141`_, `bdfca19`_)

Testing
-------

* Benchmark dataset opening and data loading separately (`#140`_, `4846947`_)

* Use locally served JP2 for HTTP benchmarks (`#142`_, `8b749df`_)

.. _#135: https://github.com/CS-SI/eodag-cube/pull/135
.. _#136: https://github.com/CS-SI/eodag-cube/pull/136
.. _#137: https://github.com/CS-SI/eodag-cube/pull/137
.. _#138: https://github.com/CS-SI/eodag-cube/pull/138
.. _#139: https://github.com/CS-SI/eodag-cube/pull/139
.. _#140: https://github.com/CS-SI/eodag-cube/pull/140
.. _#141: https://github.com/CS-SI/eodag-cube/pull/141
.. _#142: https://github.com/CS-SI/eodag-cube/pull/142
.. _#143: https://github.com/CS-SI/eodag-cube/pull/143
.. _#144: https://github.com/CS-SI/eodag-cube/pull/144
.. _#145: https://github.com/CS-SI/eodag-cube/pull/145
.. _4846947: https://github.com/CS-SI/eodag-cube/commit/4846947c977443ff9501aff77b83376e63c45f5f
.. _70a98cf: https://github.com/CS-SI/eodag-cube/commit/70a98cfddcc4be2853f76abefa628058f39ec05a
.. _8986b52: https://github.com/CS-SI/eodag-cube/commit/8986b52cfb148243818e588de5374123b06e202d
.. _8a71cd9: https://github.com/CS-SI/eodag-cube/commit/8a71cd9fcf196d0e57d6aa1815feb5dd7dd3fa92
.. _8b749df: https://github.com/CS-SI/eodag-cube/commit/8b749df750d01ebf0e69d267c50750e10e8dedcb
.. _984ae6c: https://github.com/CS-SI/eodag-cube/commit/984ae6cd0d431bbf5281f9c6cc7cfed06319219b
.. _aee4460: https://github.com/CS-SI/eodag-cube/commit/aee44601932d8c36a030bfaf8d2102cd8f845b6d
.. _b16d35e: https://github.com/CS-SI/eodag-cube/commit/b16d35efec60f311756e688976d4aa3cd8456e82
.. _bdfca19: https://github.com/CS-SI/eodag-cube/commit/bdfca195483e860bca47e2258fc9b52affc62da1
.. _cd98f73: https://github.com/CS-SI/eodag-cube/commit/cd98f73f631771a1d0f1cd5b50d7d62cf5d457a4
.. _f621fa2: https://github.com/CS-SI/eodag-cube/commit/f621fa2d88ce3e2a661df5e6bce674ac7b433683


v0.9.0 (2026-09-10)
===================

Features
--------

* Make xarray download fallback opt-in (`#131`_, `efce393`_)

Refactoring
-----------

* Removed no-more-used _get_storage_options (`#132`_, `5d12391`_)

.. _#131: https://github.com/CS-SI/eodag-cube/pull/131
.. _#132: https://github.com/CS-SI/eodag-cube/pull/132
.. _5d12391: https://github.com/CS-SI/eodag-cube/commit/5d12391b6864fdf0219802333b4003731bfa4dc5
.. _efce393: https://github.com/CS-SI/eodag-cube/commit/efce393f9cd1623b0b4627b8da394c54c03af687


v0.8.0 (2026-08-20)
===================

Features
--------

* Harmonize assets update with eodag-core (`#128`_, `75b3688`_)

Refactoring
-----------

* Use get_storage_option from eodag (`#129`_, `4626e1d`_)

Chores
------

* Asset.product typing fix (`#127`_, `7f03f8a`_)

.. _#127: https://github.com/CS-SI/eodag-cube/pull/127
.. _#128: https://github.com/CS-SI/eodag-cube/pull/128
.. _#129: https://github.com/CS-SI/eodag-cube/pull/129
.. _4626e1d: https://github.com/CS-SI/eodag-cube/commit/4626e1df88252f795ff26989acc12f3a0203c9a6
.. _75b3688: https://github.com/CS-SI/eodag-cube/commit/75b36886371c68911bafeb3428bf1b796a425e47
.. _7f03f8a: https://github.com/CS-SI/eodag-cube/commit/7f03f8a74fad2dd1911ae9d2228ec6ffcc62a4f5


v0.7.1 (2026-06-10)
===================

Performance Improvements
------------------------

* Optimized imports and initializations (`#123`_, `f50ac7b`_)

Build System
------------

* Add python3.14 support (`#124`_, `f6a881a`_)

Continuous Integration
----------------------

* Benchmark for perf regression checks (`#122`_, `5b1201a`_)

Testing
-------

* Removed tests warnings (`#125`_, `4a674d2`_)

.. _#122: https://github.com/CS-SI/eodag-cube/pull/122
.. _#123: https://github.com/CS-SI/eodag-cube/pull/123
.. _#124: https://github.com/CS-SI/eodag-cube/pull/124
.. _#125: https://github.com/CS-SI/eodag-cube/pull/125
.. _4a674d2: https://github.com/CS-SI/eodag-cube/commit/4a674d25507dd80d2f838264e42cdbe30b0632b2
.. _5b1201a: https://github.com/CS-SI/eodag-cube/commit/5b1201aed059d70f171cbbb29847c9760e1afb38
.. _f50ac7b: https://github.com/CS-SI/eodag-cube/commit/f50ac7b752a01e53173e101a4916a8d4379e07e1
.. _f6a881a: https://github.com/CS-SI/eodag-cube/commit/f6a881aca89b8f4332e059e9cdee0a97c9639c68


v0.7.0 (2026-03-16)
===================

Major changes since last stable (`v0.6.3 <CHANGES.rst#v0-6-3-2025-10-20>`_)
---------------------------------------------------------------------------

Features
^^^^^^^^

* Add augment_from_xarray for EOProduct (`#113`_, `5581b79`_)

Refactoring
^^^^^^^^^^^

* Eodag v4 usage and remove deprecated get_data (`#109`_, `42b4841`_)

v0.7.0b1 (2026-02-02)
=====================

Features
--------

* Add augment_from_xarray for EOProduct (`#113`_, `5581b79`_)

Bug Fixes
---------

* Augmented metadata formatting (`#117`_, `463690e`_)

Continuous Integration
----------------------

* Check-toml and pre-commit replaced with faster prek (`#115`_, `2b1ec8b`_)

Refactoring
-----------

* Build stac metadata methods (`#118`_, `a80fb59`_)

.. _#113: https://github.com/CS-SI/eodag-cube/pull/113
.. _#115: https://github.com/CS-SI/eodag-cube/pull/115
.. _#117: https://github.com/CS-SI/eodag-cube/pull/117
.. _#118: https://github.com/CS-SI/eodag-cube/pull/118
.. _2b1ec8b: https://github.com/CS-SI/eodag-cube/commit/2b1ec8b2959511cca196879fed89faaab83d04e7
.. _463690e: https://github.com/CS-SI/eodag-cube/commit/463690e6f121a5e3b2d712e580832af4a44cbc0a
.. _5581b79: https://github.com/CS-SI/eodag-cube/commit/5581b79d2a9fa1f22cdce30a97e158ff6388a528
.. _a80fb59: https://github.com/CS-SI/eodag-cube/commit/a80fb5975a339e5253227f8db2ed4966b7fb472a


v0.7.0a1 (2025-10-20)
=====================

Refactoring
-----------

* Eodag v4 usage and remove deprecated ``get_data`` (`#109`_, `42b4841`_)

.. _#109: https://github.com/CS-SI/eodag-cube/pull/109
.. _42b4841: https://github.com/CS-SI/eodag-cube/commit/42b4841492f76320c05c03dec8fca6fa3ba38cf8


v0.6.3 (2025-10-20)
===================

Bug Fixes
---------

* ``get_file_obj`` without auth and http (`#107`_, `44c0240`_)

.. _#107: https://github.com/CS-SI/eodag-cube/pull/107
.. _44c0240: https://github.com/CS-SI/eodag-cube/commit/44c02408dab86e64a23b11c75e5aab8aa45104c4


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
