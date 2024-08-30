#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from setuptools import setup, find_packages
from pathlib import Path
import sys
import os

VERSION = '1.0.0'

if sys.version_info < (3, 7):
    raise "must use python 3.7 or greater"

def relative(lst, base=''):
    return list(map(lambda x: base + os.path.basename(x), lst))

package_data = {
    'espDrone':  relative(glob('configs/*.json'), 'configs/') +  # noqa
                 relative(glob('configs/input/*.json'), 'configs/input/') +  # noqa
                 relative(glob('configs/log/*.json'), 'configs/log/') +  # noqa
                 relative(glob('resources/*'), 'resources/'),  # noqa
    '': ['README.md']
}

# read the contents of README.md file fo use in pypi description
directory = Path(__file__).parent
long_description = (directory / 'README.md').read_text()

# Initial parameters
setup(
    name='espDrone',
    description='HighGreat quadcopter cflib wrapper for the ESP-Drone',
    version=VERSION,
    author='HighGreat team',
    author_email='contact@highgreat@hg-fly.com',
    url='https://www.hg-hub.com',

    long_description=long_description,
    long_description_content_type='text/markdown',

    classifiers=[
        'License :: OSI Approved :: GNU General Public License v2 or later (GPLv2+)',  # noqa
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
    ],

    keywords='quadcopter crazyflie',

    package_dir={'': 'src'},
    packages=find_packages('src'),

    entry_points={
        'console_scripts': [
            'cfclient=cfclient.gui:main',
            'cfheadless=cfclient.headless:main',
            'cfloader=cfloader:main',
            'cfzmq=cfzmq:main'
        ],
    },

    install_requires=['cflib>=0.1.26',
                      'setuptools',
                      'appdirs~=1.4.0',
                      'numpy~=1.20'],

    # List of dev dependencies
    # You can install them by running
    # $ pip install -e .[dev]
    # extras_require={
    #     'dev': ['pre-commit',
    #             'cx_freeze==5.1.1 ; platform_system=="Windows"',
    #         'jinja2==2.10.3 ; platform_system=="Windows"'],
    # },

    package_data=package_data,
    data_files=data_files,
)