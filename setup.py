from setuptools import find_packages, setup

setup(
    name="eodag_cube",
    version="0.1.0",
    description="This is eodag-cube project",
    url="https://github.com/CS-SI/eodag-cube",
    author="CS Group",
    author_email="support@geostorm.eu",
    license="MIT",
    packages=find_packages(exclude=["*.tests", "*.tests.*", "tests.*", "tests"]),
    install_requires=[
        "eodag >= 2.0b2",
        "numpy",
        "rasterio",
        "protobuf",
        "grpcio",
        "xarray",
    ],
    extras_require={
        "dev": [
            "flake8",
            "isort",
            "pre-commit",
            "pytest==5.0.1",  # pytest pined to v5.0.1 to avoid issue when run from VSCode
            "pytest-cov",
            "tox",
            "nose",
            "faker",
            "coverage",
            "moto",
            "twine",
            "wheel",
        ]
    },
    zip_safe=False,
    entry_points={"console_scripts": ["eodag_cube=eodag_cube.eodag_cube:main"]},
)
