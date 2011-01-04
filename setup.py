#!/usr/bin/env python

from setuptools import setup
from setuptools import find_packages

# To set __version__
__version__ = 'unknown'
execfile('aerostat/_version.py')

setup(
    name='aerostat',
    version=__version__,
    author='Gavin McQuillan',
    author_email='gavin@urbanairship.com',
    url='http://github.com/urbanairship/aerostat',
    description='Cloud naming service',
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
