import enum
import sys
from collections.abc import Callable, Generator, Iterator
from functools import cached_property
from operator import index
from typing import (
    TYPE_CHECKING,
    Any,
    Type,
    TypeAlias,
    TypeVar,
)

from . import _reqjs
from ._reqjs import Match, PatternError

__all__ = [
    "compile",
    "finditer",
    "search",
    "Match",
    "Pattern",
    "PatternError",
    "RegexFlag",
    "ASCII",
    "A",
    "NOFLAG",
    "I",
    "IGNORECASE",
    "M",
    "MULTILINE",
    "S",
    "DOTALL",
    "U",
    "UNICODE",
    "Y",
    "STICKY",
    "NAMED_GROUPS",
    "V",
    "UNICODE_SETS",
    "STICKY_END",
]


# The Any trick
# https://typing.python.org/en/latest/guides/writing_stubs.html#the-any-trick
MaybeNone: TypeAlias = Any


class RegexFlag(enum.IntFlag):
    """Regex options"""

    #: No flags at all
    NOFLAG = 0
    IGNORECASE = I = _reqjs.IGNORECASE  # noqa: E741
    MULTILINE = M = _reqjs.MULTILINE
    DOTALL = S = _reqjs.DOTALL
    UNICODE = U = _reqjs.UNICODE
    STICKY = Y = _reqjs.STICKY
    NAMED_GROUPS = _reqjs.NAMED_GROUPS
    UNICODE_SETS = V = _reqjs.UNICODE_SETS
    ASCII = A = _reqjs.ASCII
    STICKY_END = _reqjs.STICKY_END

    if sys.version_info < (3, 11):
        # global_enum in 3.11 will do something similar

        def __repr__(self) -> str:
            if self._name_ is not None:
                # single flag
                return f"{self.__module__}.{self._name_}"

            # combine multiple flags
            vals: list[str] = []
            val = self
            for flag in self.__class__:
                if not flag or flag not in val:
                    continue
                # add found flag
                vals.append(repr(flag))
                val = val ^ flag  # remove found flag from test value
                if not val:
                    break
            else:
                # numeric value left
                vals.append(str(val.value))
            return "|".join(vals)


if TYPE_CHECKING:
    NOFLAG = RegexFlag.NOFLAG
    I = RegexFlag.I  # noqa: E741
    IGNORECASE = RegexFlag.IGNORECASE
    M = RegexFlag.M
    MULTILINE = RegexFlag.MULTILINE
    S = RegexFlag.S
    DOTALL = RegexFlag.DOTALL
    U = RegexFlag.U
    UNICODE = RegexFlag.UNICODE
    Y = RegexFlag.Y
    STICKY = RegexFlag.STICKY
    NAMED_GROUPS = RegexFlag.NAMED_GROUPS
    V = RegexFlag.V
    UNICODE_SETS = RegexFlag.UNICODE_SETS
    A = RegexFlag.A
    ASCII = RegexFlag.ASCII
    STICKY_END = RegexFlag.STICKY_END


if sys.version_info < (3, 11):
    globals().update(RegexFlag.__members__)
else:
    RegexFlag = enum.global_enum(RegexFlag)  # type: ignore[misc]


def _findall_get_group(m: Match, group_idx: int) -> str:
    group = m.group(group_idx)
    if group:
        return group
    return ""


def _findall_get_groups(m: Match, num_groups: int) -> tuple[str, ...]:
    return tuple(
        _findall_get_group(m, idx) for idx in range(1, num_groups + 1)
    )


T = TypeVar("T")

_FlagsType = int | RegexFlag


_cache: dict[tuple[Type["Pattern"], str, int], "Pattern"] = {}  # LRU
_cache2: dict[tuple[Type["Pattern"], str, int], "Pattern"] = {}  # FIFO
_MAXCACHE = 512
_MAXCACHE2 = 256


class Pattern(_reqjs.Pattern):
    """A compiled regular expression.

    :param pattern: The regular expression pattern
    :param flags: The option flags

    Internally a cache is used, so chances are that a previously compiled
    instance is returned, instead of compiling the pattern.

    """

    def __new__(cls, pattern: str, flags: _FlagsType = NOFLAG) -> "Pattern":
        """Returns a compiled regular expression pattern"""

        # This caching mechanism is implemented with (slightly modified) code,
        # copied from the Python re module.
        # https://github.com/python/cpython/blob/1f25c333a280561e86cc0af69af307b53ddbaaac/Lib/re/__init__.py#L332
        if isinstance(flags, RegexFlag):
            flags = flags.value
        key = (cls, pattern, flags)
        try:
            # First try the FIFO cache
            return _cache2[key]
        except KeyError:
            pass

        # Proceed with LRU cache, item should be moved to the end if found.
        p = _cache.pop(key, None)
        if p is None:
            p = super().__new__(cls, pattern, flags)
            if len(_cache) >= _MAXCACHE:
                # Drop the least recently used item.
                try:
                    del _cache[next(iter(_cache))]
                except (
                    StopIteration,
                    RuntimeError,
                    KeyError,
                ):  # pragma: no cover
                    pass
        # Append to the end.
        _cache[key] = p

        # Also add item to FIFO cache
        if len(_cache2) >= _MAXCACHE2:
            # Drop the oldest item.
            try:
                del _cache2[next(iter(_cache2))]
            except (StopIteration, RuntimeError, KeyError):  # pragma: no cover
                pass
        _cache2[key] = p

        return p

    @cached_property
    def flags(self) -> RegexFlag:
        """The options flags of the :class:`Pattern`"""
        return RegexFlag(self._flags)

    def search(
        self,
        string: str,
        pos: int = 0,
        endpos: int = sys.maxsize,
    ) -> Match | None:
        return self._search(string, pos, endpos)

    def test(
        self,
        string: str,
        pos: int = 0,
        endpos: int = sys.maxsize,
    ) -> bool:
        """Checks if the pattern is found in the string

        :param string: The string to search in
        :param pos: The position in the string where to start searching
        :param endpos: The position in the string up to where searching takes
            place

        :return: `True` if there is a match, `False` otherwise
        :rtype: bool

        """
        return self._test(string, pos, endpos)

    def finditer(
        self, string: str, pos: int = 0, endpos: int = sys.maxsize
    ) -> Generator[Match, None, None]:
        """Yields matches"""
        match_obj = self._search(string, pos, endpos)
        while match_obj is not None:
            yield match_obj
            match_obj = match_obj._next()

    def findall(
        self, string: str, pos: int = 0, endpos: int = sys.maxsize
    ) -> list[str | tuple[str, ...]]:
        num_groups = self.groups
        group_func: Callable[[Match, int], str | tuple[str, ...]]
        if num_groups < 2:
            group_func = _findall_get_group
        else:
            group_func = _findall_get_groups

        return [
            group_func(m, num_groups)
            for m in self.finditer(string, pos, endpos)
        ]

    def _split(
        self,
        string: str,
        maxsplit: int,
        match_func: Callable[[Match], Iterator[T]],
    ) -> Generator[str | T, None, int]:
        maxsplit = index(maxsplit) or len(string)
        prev_end = 0
        splits = 0
        for splits, match_obj in enumerate(self.finditer(string)):
            if splits >= maxsplit:
                break
            yield string[prev_end : match_obj.start()]
            yield from match_func(match_obj)
            prev_end = match_obj.end()
        yield string[prev_end:]
        return splits

    def split(self, string: str, maxsplit: int = 0) -> list[str | MaybeNone]:
        def yield_captured(match_obj: Match) -> Iterator[str | MaybeNone]:
            for group_idx in range(1, self.groups + 1):
                yield match_obj.group(group_idx)

        return list(self._split(string, maxsplit, yield_captured))

    def _subn(
        self, repl: str | Callable[[Match], str], string: str, count: int = 0
    ) -> Generator[str, None, int]:
        if isinstance(repl, str):

            def yield_func(match_obj: Match) -> Iterator[str]:
                yield match_obj.expand(repl)
        else:

            def yield_func(match_obj: Match) -> Iterator[str]:
                yield repl(match_obj)

        return self._split(string, count, yield_func)

    def subn(
        self, repl: str | Callable[[Match], str], string: str, count: int = 0
    ) -> tuple[str, int]:

        subs_made = 0

        def yield_parts() -> Iterator[str]:
            nonlocal subs_made
            subs_made = yield from self._subn(repl, string, count)

        return "".join(yield_parts()), subs_made

    def sub(
        self, repl: str | Callable[[Match], str], string: str, count: int = 0
    ) -> str:
        return "".join(self._subn(repl, string, count))

    def __repr__(self) -> str:
        return (
            f"{self.__module__}.{self.__class__.__name__}"
            f"({repr(self.pattern)[:200]}"
            f"{'' if self.flags is UNICODE else f', {self.flags!r}'})"
        )


compile = Pattern
"""Alias of :py:class:`Pattern` analogous to the standard
:py:func:`re.compile`."""


def search(
    pattern: str,
    string: str,
    flags: _FlagsType = NOFLAG,
) -> Match | None:
    """Searches for a pattern in a string

    :param pattern: The regular expression pattern
    :param string: The string to search in
    :param flags: The options of the regular expression
    :return: A :py:class:`Match` object if the pattern is found, otherwise
        :py:data:`None`.
    :rtype: :py:class:`Match` | :py:data:`None`

    .. note::

        The functionality provided by :py:func:`re.match` can be emulated by
        calling :py:func:`search` with the :py:data:`STICKY` flag.

        Similarly, use :py:data:`STICKY` | :py:data:`STICKY_END` for
        :py:func:`re.fullmatch` functionality.

    """
    return Pattern(pattern, flags).search(string)


def test(
    pattern: str,
    string: str,
    flags: _FlagsType = NOFLAG,  # noqa: F821
) -> bool:
    """Checks if a pattern is found in a string

    :param pattern: The regular expression pattern
    :param string: The string to search in
    :param flags: The options of the regular expression
    :return: :external:py:data:`True` if there is a match, :py:data:`False`
        otherwise
    :rtype: bool

    Use this function if the resulting :py:class:`Match` is not required for
    further processing. It is slightly more efficient than using
    :py:func:`search`

    """
    return Pattern(pattern, flags).test(string)


def finditer(
    pattern: str, string: str, flags: _FlagsType = NOFLAG
) -> Generator[Match, None, None]:
    """A generator that yields non-overlapping matches

    :param pattern: The regular expression pattern
    :param string: The string to search in
    :param flags: The options of the regular expression
    :return: An :py:class:`~collections.abc.Generator` that yields
        :py:class:`Match` objects.
    """
    return Pattern(pattern, flags).finditer(string)


def findall(
    pattern: str,
    string: str,
    flags: _FlagsType = NOFLAG,
) -> list[str | tuple[str, ...]]:
    """
    Return all non-overlapping matches of *pattern* in *string*, as a list of
    strings or list of tuples of strings.

    :param pattern: The regular expression pattern
    :param string: The string to search in
    :param flags: The options of the regular expression
    :return: A list of strings or list of tuples of strings
    :rtype: list[str | tuple[str, ...]]

    The string is scanned left-to-right, and matches are returned in the order
    found. Empty matches are included in the result.

    The result depends on the number of capturing groups in the pattern. If
    none, return a list of strings matching the whole pattern.
    If there is exactly one group, return a list of strings matching that
    group. If multiple groups are present, return a list of tuples of strings
    matching the groups. Non-capturing groups do not affect the form of the
    result. ::

        >>> reqjs.findall(r'\\bf[a-z]*', 'which foot or hand fell fastest')
        ['foot', 'fell', 'fastest']
        >>> reqjs.findall(r'(\\w+)=(\\d+)', 'set width=20 and height=10')
        [('width', '20'), ('height', '10')]

    """
    return Pattern(pattern, flags).findall(string)


def split(
    pattern: str,
    string: str,
    *,
    maxsplit: int = 0,
    flags: _FlagsType = NOFLAG,
) -> list[str | MaybeNone]:
    """Split *string* by the occurrences of *pattern*.

    :param pattern: The regular expression pattern
    :param string: The string to split
    :param maxsplit: The maximum number of splits to perform
    :param flags: The options of the regular expression
    :return: A list of strings

    If capturing groups are used in pattern, then the content of all groups is
    also returned as part of the resulting list. Non-matching groups are
    represented as :py:data:`None`.
    If maxsplit is nonzero, at most maxsplit splits occur, and the remainder of
    the string is returned as the final element of the list. ::

        >>> reqjs.split(r'\\W+', 'Words, words, words.')
        ['Words', 'words', 'words', '']
        >>> reqjs.split(r'(\\W+)', 'Words, words, words.')
        ['Words', ', ', 'words', ', ', 'words', '.', '']
        >>> reqjs.split(r'\\W+', 'Words, words, words.', maxsplit=1)
        ['Words', 'words, words.']
        >>> reqjs.split('[a-f]+', '0a3B9', flags=reqjs.IGNORECASE)
        ['0', '3', '9']
        >>> reqjs.split(',( )?', 'yes,yes')
        ['yes', None, 'yes']

    If there are capturing groups in the separator and it matches at the start
    of the string, the result will start with an empty string. The same holds
    for the end of the string: ::

        >>> reqjs.split(r'(\\W+)', '...words, words...')
        ['', '...', 'words', ', ', 'words', '...', '']

    That way, separator components are always found at the same relative
    indices within the result list.

    """
    return Pattern(pattern, flags).split(string, maxsplit=maxsplit)


def sub(
    pattern: str,
    repl: str | Callable[[Match], str],
    string: str,
    *,
    count: int = 0,
    flags: _FlagsType = NOFLAG,
) -> str:
    """Search for non-overlapping matches of *pattern* in *string* and
    replace those using the replacement string or function. If no match is
    found, the original string is returned.

    :param pattern: The regular expression pattern
    :param repl: The replacement string or function
    :param string: The string to search in
    :param count: The maximum number of occurrences to replace, zero means no
        limit
    :param flags: The options of the regular expression
    :return: The *string* with applied substitutions

    If *repl* is a string, it is interpreted as a format string and
    :py:meth:`str.format` is called on it with all group values as *args* and
    all named group values as *kwargs*. This means that literal curly braces
    must be escaped by doubling: ``{{`` and ``}}``. When the replacement string
    does not contain any replacement fields it will be returned as is, for each
    match.

    If *repl* is a function, it is called for every match. The function takes a
    single :py:obj:`Match` argument, and returns the replacement string.

    """
    return Pattern(pattern, flags).sub(repl, string, count)


def purge() -> None:
    """Clear the regular expression caches"""
    _cache.clear()
    _cache2.clear()
