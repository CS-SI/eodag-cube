# eodag-cube

This project is the data-access part of [eodag](https://github.com/CS-SI/eodag)
## Setup

```sh
make git install
source .venv/bin/activate
make test  # for testing with the virtual env Python version
tox  # for testing with every configured Python versions
```

See `tox.ini` file for configuration of tested Python versions.

## Usage

### Adding some dependencies

Update `install_requires` section of `setup.py` file to add a dependency.

Then run `pip install --upgrade .`

## LICENSE

EODAG is licensed under Apache License v2.0.
See LICENSE file for details.


## AUTHORS

EODAG is developed by `CS GROUP - France <https://www.c-s.fr>`_.


## CREDITS

EODAG is built on top of amazingly useful open source projects. See NOTICE file for details about those projects and
their licenses.
Thank you to all the authors of these projects !
