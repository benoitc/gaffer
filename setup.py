# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import os
import sys

from setuptools import setup, find_packages, Extension

py_version = sys.version_info[:2]

if py_version < (2, 7):
    raise RuntimeError('On Python 2, Gaffer requires Python 2.7 or better')


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
with open(os.path.join(os.path.dirname(__file__), 'README.md')) as f:
    long_description = f.read()

DATA_FILES = [
        ('gaffer', ["LICENSE", "MANIFEST.in", "NOTICE", "README.md",
                        "THANKS", "UNLICENSE", "TODO.rst"])
        ]


setup(name='gaffer',
      version="0.5.1",
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
          'pyuv>=0.8.3',
          'six',
          'psutil',
          'tornado==2.4.1',
          'colorama',
          'setproctitle'
      ],
      data_files = DATA_FILES,
      entry_points="""

      [console_scripts]
      gafferd=gaffer.gafferd.main:run
      gaffer=gaffer.cli.main:main
      gaffer_lookupd=gaffer.lookupd.main:main
      """)
