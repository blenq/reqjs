ReQJS usage
===========

The `reqjs` module provides regular expression functionality, using the
`QuickJS <https://bellard.org/quickjs/quickjs.html#RegExp>`_
regular expression engine. It conforms to the ES2025 specification. It does
only expose the regular expression engine, not the JavaScript RegExp object.
The Python interface, documented here, is inspired by the standard Python
:py:mod:`re module<re>`, but it is not a drop-in replacement.

This documentation does not provide information about the ECMAScript
Regex pattern format. This has been done extensively by others, for example
`MDN <https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Regular_expressions>`_.


Module Contents
---------------

.. py:module:: reqjs

Flags
^^^^^

Various flags can be set to adjust the matching algorithm of a pattern. The
flags are implemented as an :py:class:`enum.IntFlag` class :py:class:`RegexFlag`.


.. class:: RegexFlag

   An :class:`enum.IntFlag` class containing the regex options listed below.


.. py:data:: NOFLAG

    No flags at all

.. py:data:: I
             IGNORECASE

    Perform case-insensitive matching


.. py:data:: M
             MULTILINE

    Makes `^` and `$` match the start and end of each line instead of those of
    the entire string.


.. py:data:: S
             DOTALL

    Allows `.` to match newline characters.


.. py:data:: U
             UNICODE

    Treat a pattern as a sequence of Unicode code points.


.. py:data:: Y
             STICKY

    Perform a "sticky" search that matches only at the current position and
    does not attempt to match behind that position.


.. py:data:: NAMED_GROUPS

    This flag reports if the pattern contains named groups. Setting it has
    no effect.


.. py:data:: V
             UNICODE_SETS

    An upgrade to the :py:data:`UNICODE` flag that that enables more Unicode-related
    features.


Functions
^^^^^^^^^

.. autofunction:: compile

.. autofunction:: search

.. autofunction:: test

.. autofunction:: prefixmatch(pattern: str, string: str, flags: int = reqjs.UNICODE | reqjs.STICKY) -> Match | None:

.. autofunction:: match

.. autofunction:: fullmatch

.. autofunction:: split

.. autofunction:: findall

.. autofunction:: finditer


Regular Expression objects
^^^^^^^^^^^^^^^^^^^^^^^^^^

.. autoclass:: Pattern
    :members:


.. automodule:: reqjs
    :no-index:
    :members:
    :undoc-members:
    :exclude-members: RegexFlag, Match, search, match, Pattern, compile, finditer
    :member-order: bysource




.. autoclass:: Match
    :members:
    :undoc-members:
    :exclude-members: start, end

    .. automethod:: start(group: int | str = 0) -> int
    .. automethod:: end(group: int | str = 0) -> int
