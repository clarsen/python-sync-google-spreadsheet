========
Overview
========

.. start-badges

.. list-table::
    :stub-columns: 1

    * - docs
      - |docs|
    * - tests
      - | |travis| |requires|
        | |codecov|
        | |landscape|
..    * - package
      - | |version| |wheel| |supported-versions| |supported-implementations|
        | |commits-since|

.. |docs| image:: https://readthedocs.org/projects/python-sync-google-spreadsheet/badge/?style=flat
    :target: https://readthedocs.org/projects/python-sync-google-spreadsheet
    :alt: Documentation Status

.. |travis| image:: https://travis-ci.org/clarsen/python-sync-google-spreadsheet.svg?branch=master
    :alt: Travis-CI Build Status
    :target: https://travis-ci.org/clarsen/python-sync-google-spreadsheet

.. |requires| image:: https://requires.io/github/clarsen/python-sync-google-spreadsheet/requirements.svg?branch=master
    :alt: Requirements Status
    :target: https://requires.io/github/clarsen/python-sync-google-spreadsheet/requirements/?branch=master

.. |codecov| image:: https://codecov.io/github/clarsen/python-sync-google-spreadsheet/coverage.svg?branch=master
    :alt: Coverage Status
    :target: https://codecov.io/github/clarsen/python-sync-google-spreadsheet

.. |landscape| image:: https://landscape.io/github/clarsen/python-sync-google-spreadsheet/master/landscape.svg?style=flat
    :target: https://landscape.io/github/clarsen/python-sync-google-spreadsheet/master
    :alt: Code Quality Status

.. .. |version| image:: https://img.shields.io/pypi/v/sync-google-spreadsheet.svg
    :alt: PyPI Package latest release
    :target: https://pypi.python.org/pypi/sync-google-spreadsheet

.. .. |commits-since| image:: https://img.shields.io/github/commits-since/clarsen/python-sync-google-spreadsheet/v0.0.1.svg
    :alt: Commits since latest release
    :target: https://github.com/clarsen/python-sync-google-spreadsheet/compare/v0.0.1...master

.. .. |wheel| image:: https://img.shields.io/pypi/wheel/sync-google-spreadsheet.svg
    :alt: PyPI Wheel
    :target: https://pypi.python.org/pypi/sync-google-spreadsheet

.. .. |supported-versions| image:: https://img.shields.io/pypi/pyversions/sync-google-spreadsheet.svg
    :alt: Supported versions
    :target: https://pypi.python.org/pypi/sync-google-spreadsheet

.. .. |supported-implementations| image:: https://img.shields.io/pypi/implementation/sync-google-spreadsheet.svg
    :alt: Supported implementations
    :target: https://pypi.python.org/pypi/sync-google-spreadsheet


.. end-badges

A library and driver to do additions or updates to Google spreadsheet given a stream of data

* Free software: MIT license

Installation
============

::

    pip install sync-google-spreadsheet


Examples
========

Download ``chromedriver`` for your system `from here <https://sites.google.com/a/chromium.org/chromedriver/downloads>`_.
And put it in ``./assets`` folder.

Update spreadsheet of sleep tracking data from Beddit and Resmed (myAir)
------------------------------------------------------------------------
::

    pip install gspread oauth2client pandas beddit-python selenium PyYAML
    python examples/update_sleep.py

Update and append to spreadsheet of exercise data from Peloton
--------------------------------------------------------------
::

    pip install gspread oauth2client pandas selenium PyYAML
    rm -rf tmp; mkdir tmp
    python examples/update_peloton.py


Update and append to spreadsheet of finance data from Schwab and Chase credit card data
---------------------------------------------------------------------------------------
This currently doesn't use selenium to scrape site and download.

::

  pip install gspread oauth2client PyYAML
  rm -rf tmp; mkdir tmp
  # download csv export of transaction data to tmp
  python examples/update_finance.py

Documentation
=============

https://python-sync-google-spreadsheet.readthedocs.io/

Development
===========

To run the all tests run::

    tox

Note, to combine the coverage data from all the tox environments run:

.. list-table::
    :widths: 10 90
    :stub-columns: 1

    - - Windows
      - ::

            set PYTEST_ADDOPTS=--cov-append
            tox

    - - Other
      - ::

            PYTEST_ADDOPTS=--cov-append tox

Known issues
============

Sometimes there are two transactions on the same day from the same vendor for
the same amount.  The sheet adapter doesn't handle the key uniqueness check in
that case for the example update_finance script.
