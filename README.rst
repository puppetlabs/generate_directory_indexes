Apache-style Directory Index Generator
=======================

This script generates Apache-style directory indexes as static HTML
files. The primary use case is indexing files in an AWS S3 bucket so
that they can be navigated like files served by an Apache web server.

Usage:

generate_directory_indexes.py [--help|-h]

generate_directory_indexes.py [--file-metadata FILE_METADATA]
                                     [--metadata-delimiter METADATA_DELIMITER]
                                     [--noop] [--verbose]
                                     path

positional arguments:
  path                  Top directory for writing index files.

optional arguments:
  --file-metadata FILE_METADATA, -f FILE_METADATA
                        A file containing data describing the tree to index.
  --metadata-delimiter METADATA_DELIMITER, -m METADATA_DELIMITER
                        Character which seperates fields in the file metadata.
                        Default is a semicolon.
  --noop, -n            Only print files to be created without writing them to
                        disk
  --verbose, -v         Verbose output. Repeat (up to -vvv) for more verbosity
  --help, -h            show this help message and exit


Developing
=======================

1. Make sure you're familiar with Python setuptools/distutils
2. Create a ~/.pypirc file if you don't already have one. Add the 
   "artifactory" repo to the pypirc. Use your username.

::

  [distutils]
  index-servers =
    artifactory

  [artifactory]
  repository: https://artifactory.delivery.puppetlabs.net/artifactory/api/pypi/pypi
  username: my.username

3. From your project root, run the following command to upload the package.
   Make sure the setup script works

::

  python setup.py sdist upload -r artifactory

4. To resolve packages using pip, add the following to ~/.pip/pip.conf

::

  [global]
  index-url = https://artifactory.delivery.puppetlabs.net/artifactory/api/pypi/pypi/simple
