import setuptools

with open("README.rst", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="hassfeld",
    version="0.3.12-alpha3",
    description="Integration of Raumfeld into Home Assistant",
    long_description=long_description,
    long_description_content_type="text/x-rst",
    url="https://github.com/B5r1oJ0A9G/hassfeld",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.5',
    install_requires=[
        "aiohttp",
        "async_upnp_client>=0.27",
        "requests",
        "xmltodict",
    ]
)
