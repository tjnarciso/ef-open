#!/usr/bin/env python

from setuptools import setup

setup(
    name='ef-open',
    version='0.1.1',
    packages=['efopen'],
    install_requires=[
        "boto3",
        "PyYAML"
    ],
    entry_points={
        'console_scripts': [
            'ef-cf=efopen.ef_cf:main',
            'ef-check-config=efopen.ef_check_config:main',
            'ef-generate=efopen.ef_generate:main',
            'ef-instanceinit=efopen.ef_instanceinit:main',
            'ef-password=efopen.ef_password:main',
            'ef-resolve-config=efopen.ef_resolve_config:main',
            'ef-version=efopen.ef_version:main'
        ],
    },
    url='https://github.com/crunchyroll/ef-open',
    license="Apache License 2.0",
    author='Ellation, Inc.',
    author_email='ops@ellation.com',
    description='CloudFormation Tools by Ellation'
)