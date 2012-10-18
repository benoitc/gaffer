# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import os
import sys

from setuptools import setup, find_packages, Extension

py_version = sys.version_info[:2]

if py_version < (2, 6):
    raise RuntimeError('On Python 2, Gaffer requires Python 2.6 or better')


CLASSIFIERS = [
    'Development Status :: 4 - Beta',
    'Environment :: Web Environment',
    'Intended Audience :: Developers',
    'License :: OSI Approved :: MIT License',
    'Operating System :: POSIX',
    'Programming Language :: Python',
    'Programming Language :: Python :: 2',
    'Programming Language :: Python :: 2.6',
    'Programming Language :: Python :: 2.7',
    'Programming Language :: Python :: 3',
    'Programming Language :: Python :: 3.0',
    'Programming Language :: Python :: 3.1',
    'Programming Language :: Python :: 3.2',
    'Topic :: System :: Boot',
    'Topic :: System :: Monitoring',
    'Topic :: System :: Systems Administration',
    'Topic :: Software Development :: Libraries']


# read long description
with open(os.path.join(os.path.dirname(__file__), 'README.rst')) as f:
    long_description = f.read()

DATA_FILES = [
        ('gaffer', ["LICENSE", "MANIFEST.in", "NOTICE", "README.rst",
                        "THANKS", "UNLICENSE"])
        ]


setup(name='gaffer',
      version="0.3.0",
      description = 'simple system process manager',
      long_description = long_description,
      classifiers = CLASSIFIERS,
      license = 'BSD',
      url = 'http://github.com/benoitc/gaffer',
      author = 'Benoit Chesneau',
      author_email = 'benoitc@e-engura.org',
      packages=find_packages(),
      ext_modules = [
            Extension("gaffer.sync", ["gaffer/sync.c"])
      ],
      install_requires = [
          'pyuv',
          'six',
          'psutil',
          'tornado',
          'colorama',
          'setproctitle'
      ],
      data_files = DATA_FILES,
      entry_points="""

      [console_scripts]
      gafferd=gaffer.node.gafferd:run
      gafferctl=gaffer.node.gafferctl:run
      gaffer=gaffer.pm.main:main
      """)
