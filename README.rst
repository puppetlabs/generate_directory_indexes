Apache-style Directory Index Generator
=======================

This script generates Apache-style directory indexes as static HTML files. The primary use case is indexing files in an AWS S3 bucket so that they can be navigated like files served by an Apache web server.

Usage:

./generate_directory_indexes.py --help                                                                                     ~/development/generate_directory_indexes
usage: generate_directory_indexes.py [-h] [--noop] [--verbose] path

positional arguments:
  path           Path to index and write indexes to

optional arguments:
  -h, --help     show this help message and exit
  --noop         Only print files to be created without writing them to disk
  --verbose, -v  Verbose output. Repeat (up to -vvv) for more verbosity
