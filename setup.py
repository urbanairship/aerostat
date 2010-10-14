#!/usr/bin/env python

from setuptools import setup
from setuptools import find_packages
from aerostat import __version__ as version

setup(
    name='aerostat',
    version=version,
    author='Gavin McQuillan',
    author_email='gavin@urbanairship.com',
    url='http://urbanairship.com',
    description='Cloud algorithmic name service',
    long_description='Algorithmically set hostnames on cloud servers.',
    packages=find_packages(),
    package_dir={'aerostat':'aerostat'},
    include_package_data=True,
    entry_points={
        'console_scripts':['aerostat=aerostat.aerostat:main',
                           'aerostatd=aerostat.aerostat_server:main']
    },
    install_requires=[
        'boto',
        'jinja2',
        'pymongo',
        'PyYAML',
        'GitPython',
    ],
    zip_safe=False,
)
