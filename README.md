# ReQJS

Python library that contains the QuickJS regular expression library, that
according to its creator is fully compliant with the Javascript ES2023
specification.

## Library

The library contains only the regular expression engine, called "libregexp",
and does not contain the entire QuickJS JavaScript implementation.
The Pattern and Match objects are modeled after the Python stdlib re module.
