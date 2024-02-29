Release history
---------------

0.4.1 (2024-02-29)
++++++++++++++++++

- Fixes s3 authentication using GDAL/rasterio environment variables (#50)

0.4.0 (2024-02-19)
++++++++++++++++++

- `get_data` directly available on `product.assets` (#46)
- Adds windows support (#9)
- Removes limited grpc support (#43)
- Adds python type hints (#45)
- Various minor fixes and improvements (#44)(#47)

0.3.1 (2023-11-15)
++++++++++++++++++

- Allows regex in band selection through `StacAssets` driver (#38)
- Removes support for `python3.7`` and adds support for `python3.12` (#39)
- Various minor fixes and improvements (#37)

0.3.0 (2023-03-17)
++++++++++++++++++

- New Generic driver (#26)
- `get_data()` `crs` and `resampling` parameters are now facultative (#25)
- Support python versions from `3.7` to `3.11` (#34)
- `pre-commit` and dependencies updates (#33)

0.2.1 (2021-08-11)
++++++++++++++++++

- Specified minimal `eodag` version needed for binder (#22)

0.2.0 (2021-07-30)
++++++++++++++++++

- AWS credentials usage with rasterio (#19)
- Rioxarray usage to read data (#18)
- New StacAssets driver (#17)
- `get_data()` now accepts the same types of geometries as `eodag.search()` (#16)
- New notebook and readme example (#20)

0.1.2 (2021-06-18)
++++++++++++++++++

- DataArray shape flipped (#12, thanks @ClaudioCiociola)

0.1.1 (2021-01-15)
++++++++++++++++++

- get_data, drivers, and RPC server from eodag

0.1.0 (2021-01-15)
++++++++++++++++++

- First release
