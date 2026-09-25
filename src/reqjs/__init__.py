import enum
import sys
from collections.abc import Callable, Generator, Iterator
from functools import cached_property
from operator import index
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    Type,
    TypeAlias,
    TypeVar,
)

if TYPE_CHECKING:
    # Prevent runtime dependency on typing_extensions
    if sys.version_info < (3, 11):
        from typing_extensions import Self
    else:
        from typing import Self


from . import _reqjs
from ._reqjs import Match, PatternError

__all__ = [
    "compile",
    "finditer",
    "match",
    "search",
    "Match",
    "Pattern",
    "PatternError",
    "RegexFlag",
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
                vals.append(format(val, "#x"))
            return "|".join(vals)


NOFLAG: RegexFlag
I: RegexFlag  # noqa: E741
IGNORECASE: RegexFlag
M: RegexFlag
MULTILINE: RegexFlag
S: RegexFlag
DOTALL: RegexFlag
U: RegexFlag
UNICODE: RegexFlag
Y: RegexFlag
STICKY: RegexFlag
NAMED_GROUPS: RegexFlag
V: RegexFlag
UNICODE_SETS: RegexFlag


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


class Pattern(_reqjs.Pattern):
    """A compiled regular expression.

    :param pattern: The regular expression pattern
    :param flags: The option flags

    Internally a cache is used, so chances are that a previously compiled
    instance is returned, instead of compiling the pattern.

    """

    _cache: ClassVar[dict[tuple[Type["Self"], str, int], "Self"]] = {}  # LRU
    _cache2: ClassVar[dict[tuple[Type["Self"], str, int], "Self"]] = {}  # FIFO
    _MAXCACHE = 512
    _MAXCACHE2 = 256

    def __new__(
        cls, pattern: str, flags: _FlagsType = RegexFlag.UNICODE
    ) -> "Self":
        """Returns a compiled regular expression pattern"""

        # This caching mechanism is implemented with (slightly modified) code,
        # copied from the Python re module.
        # https://github.com/python/cpython/blob/1f25c333a280561e86cc0af69af307b53ddbaaac/Lib/re/__init__.py#L332
        if isinstance(flags, RegexFlag):
            flags = flags.value
        key = (cls, pattern, flags)
        try:
            # First try the FIFO cache
            return cls._cache2[key]
        except KeyError:
            pass

        # Proceed with LRU cache, item should be moved to the end if found.
        p = cls._cache.pop(key, None)
        if p is None:
            p = super().__new__(cls, pattern, flags)
            if len(cls._cache) >= cls._MAXCACHE:
                # Drop the least recently used item.
                try:
                    del cls._cache[next(iter(cls._cache))]
                except (StopIteration, RuntimeError, KeyError):
                    pass
        # Append to the end.
        cls._cache[key] = p

        # Also add item to FIFO cache
        if len(cls._cache2) >= cls._MAXCACHE2:
            # Drop the oldest item.
            try:
                del cls._cache2[next(iter(cls._cache2))]
            except (StopIteration, RuntimeError, KeyError):
                pass
        cls._cache2[key] = p

        return p

    @cached_property
    def flags(self) -> RegexFlag:  # pyright: ignore[reportIncompatibleMethodOverride]
        """The options flags of the :class:`Pattern`"""
        return RegexFlag(super().flags)

    def prefixmatch(
        self,
        string: str,
        pos: int = 0,
        endpos: int = sys.maxsize,
    ) -> Match | None:
        match_obj = super().search(string, pos, endpos)
        if match_obj is None or match_obj.start() != match_obj.pos:
            return None
        return match_obj

    def fullmatch(
        self,
        string: str,
        pos: int = 0,
        endpos: int = sys.maxsize,
    ) -> Match | None:
        match_obj = super().search(string, pos, endpos)
        if (
            match_obj is None
            or match_obj.start() != match_obj.pos
            or match_obj.end() != match_obj.endpos
        ):
            return None
        return match_obj

    match = prefixmatch

    def search(
        self,
        string: str,
        pos: int = 0,
        endpos: int = sys.maxsize,
    ) -> Match | None:
        return super().search(string, pos, endpos)

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
        return super().test(string, pos, endpos)

    def finditer(
        self, string: str, pos: int = 0, endpos: int = sys.maxsize
    ) -> Iterator[Match]:
        """Yields matches"""
        match_obj = super().search(string, pos, endpos)
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
        maxsplit = index(maxsplit)
        if maxsplit < 0:
            yield string
            return 0
        prev_end = 0
        splits = 0
        match_obj = self.search(string)
        while match_obj is not None and (maxsplit == 0 or splits < maxsplit):
            yield string[prev_end : match_obj.start()]
            yield from match_func(match_obj)
            prev_end = match_obj.end()
            splits += 1
            match_obj = match_obj._next()
        yield string[prev_end:]
        return splits

    def split(self, string: str, maxsplit: int = 0) -> list[str | MaybeNone]:
        def yield_captured(match_obj: Match) -> Iterator[str | MaybeNone]:
            for group_idx in range(1, self.groups + 1):
                yield match_obj.group(group_idx)

        return list(self._split(string, maxsplit, yield_captured))

    def subn(
        self, repl: str | Callable[[Match], str], string: str, count: int = 0
    ) -> tuple[str, int]:
        if isinstance(repl, str):

            def yield_func(match_obj: Match) -> Iterator[str]:
                yield match_obj.expand(repl)
        else:

            def yield_func(match_obj: Match) -> Iterator[str]:
                yield repl(match_obj)

        subs_made = 0

        def yield_parts() -> Iterator[str]:
            nonlocal subs_made
            subs_made = yield from self._split(string, count, yield_func)

        result = "".join(yield_parts())
        return result, subs_made

    def sub(
        self, repl: str | Callable[[Match], str], string: str, count: int = 0
    ) -> str:
        return self.subn(repl, string, count)[0]

    @classmethod
    def _purge(cls) -> None:
        cls._cache.clear()
        cls._cache2.clear()

    def __repr__(self) -> str:
        if self.flags is RegexFlag.UNICODE:
            return (
                f"{self.__module__}.{self.__class__.__name__}"
                f"({self.pattern!r})"
            )
        return (
            f"{self.__module__}.{self.__class__.__name__}"
            f"({self.pattern!r}, {self.flags!r})"
        )


compile = Pattern
"""Alias of :py:class:`Pattern` analogous to the standard
:py:func:`re.compile`."""


def search(
    pattern: str,
    string: str,
    flags: _FlagsType = RegexFlag.UNICODE,
) -> Match | None:
    """Searches for a pattern in a string

    :param pattern: The regular expression pattern
    :param string: The string to search in
    :param flags: The options of the regular expression
    :return: A :py:class:`Match` object if the pattern is found, otherwise
        :py:data:`None`.
    :rtype: :py:class:`Match` | :py:data:`None`

    """
    return Pattern(pattern, flags).search(string)


def test(
    pattern: str,
    string: str,
    flags: _FlagsType = RegexFlag.UNICODE,  # noqa: F821
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
    pattern: str, string: str, flags: _FlagsType = RegexFlag.UNICODE
) -> Iterator[Match]:
    """A generator that yields non-overlapping matches

    :param pattern: The regular expression pattern
    :param string: The string to search in
    :param flags: The options of the regular expression
    :return: An :py:class:`~collections.abc.Iterator` that yields :py:class:`Match` objects.
    :rtype: :py:class:`~collections.abc.Iterator`\\[:py:class:`Match`]
    """
    return Pattern(pattern, flags).finditer(string)


def prefixmatch(
    pattern: str,
    string: str,
    flags: _FlagsType = RegexFlag.UNICODE | RegexFlag.STICKY,
) -> Match | None:
    """Searches for a pattern at the beginning of a string

    The :py:attr:`STICKY` flag will always be set, to make the search more
    efficient,

    :param pattern: The regular expression pattern
    :param string: The string to search in
    :param flags: The options of the regular expression
    :return: A :py:class:`Match` object if the pattern is found at the
        beginning of the string, or :py:data:`None` otherwise.
    :rtype: :py:class:`Match` | :py:data:`None`

    """
    flags = RegexFlag.STICKY | flags  # noqa: F821
    return Pattern(pattern, flags).search(string)


def fullmatch(
    pattern: str,
    string: str,
    flags: _FlagsType = RegexFlag.UNICODE | RegexFlag.STICKY,
) -> Match | None:
    """Return a :py:class:`Match` object if the *whole* string matches the
    pattern.

    The :py:attr:`STICKY` flag will always be set, to make the search more
    efficient,

    :param pattern: The regular expression pattern
    :param string: The string to search in
    :param flags: The options of the regular expression
    :return: A :py:class:`Match` object if the *whole* string matches, or
        :py:data:`None` otherwise.
    :rtype: :py:class:`Match` | :py:data:`None`

    """
    flags = RegexFlag.STICKY | flags  # noqa: F821
    return Pattern(pattern, flags).fullmatch(string)


def findall(
    pattern: str,
    string: str,
    flags: _FlagsType = RegexFlag.UNICODE,
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


#:
#:.. deprecated:: 0.1
#:    Following Python 3.15, :py:func:`match` has been soft-deprecated in
#:    favor of :py:func:`prefixmatch`, which is more explicitly descriptive.
#:
match = prefixmatch


def split(
    pattern: str,
    string: str,
    *,
    maxsplit: int = 0,
    flags: _FlagsType = RegexFlag.UNICODE,
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
    flags: _FlagsType = RegexFlag.UNICODE,
) -> str:
    return Pattern(pattern, flags).sub(repl, string, count)


def purge() -> None:
    """Clear the regular expression caches"""
    Pattern._purge()  # pyright: ignore[reportPrivateUsage]
