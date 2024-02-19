import os

from setuptools import find_packages, setup

BASEDIR = os.path.dirname(os.path.abspath(os.path.realpath(__file__)))

metadata = {}
with open(os.path.join(BASEDIR, "eodag_cube", "__init__.py"), "r") as f:
    exec(f.read(), metadata)

with open(os.path.join(BASEDIR, "README.rst"), "r") as f:
    readme = f.read()

setup(
    name=metadata["__title__"],
    version=metadata["__version__"],
    description=metadata["__description__"],
    long_description=readme,
    author=metadata["__author__"],
    author_email=metadata["__author_email__"],
    url=metadata["__url__"],
    license=metadata["__license__"],
    packages=find_packages(exclude=("*.tests", "*.tests.*", "tests.*", "tests")),
    package_data={"": ["LICENSE", "NOTICE"], "eodag_cube": ["py.typed"]},
    include_package_data=True,
    install_requires=[
        "eodag >= 2.12.0",
        "numpy",
        "rasterio",
        "xarray",
        "rioxarray",
    ],
    extras_require={
        "dev": [
            "flake8",
            "isort",
            "pre-commit",
            "pytest",
            "pytest-cov",
            "tox",
            "nose",
            "faker",
            "coverage",
            "moto >= 5",
            "twine",
            "wheel",
        ]
    },
    zip_safe=False,
    classifiers=[
        "Development Status :: 1 - Planning",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "Natural Language :: English",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: Implementation :: CPython",
        "Topic :: Scientific/Engineering :: GIS",
    ],
)
