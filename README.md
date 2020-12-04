# eodag-cube

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

## VSCode Python environment initialisation

* Select previously created Python virtual environment as Python interpreter: `CTRL+SHIFT+p` and type "interpreter"
* Configure Python test runner: `CTRL+SHIFT+p` then type "configure test" and choose Pytest
* Formatting with black: `CTRL+SHIFT+i` then choose "black" button into VSCode popup
* Linting with flake8: `CTRL+SHIFT+i` then choose "select linter" then select flake8

After that, Python tests tab appears and you can run tests.

## Credits

This package was created with Cookiecutter and the [geostorm/cookiecutter-python](https://bitbucket.org/geostorm/cookiecutter-python) project template.
