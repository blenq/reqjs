import re
import weakref
from unittest import TestCase

import reqjs


class PatternCase(TestCase):
    def test_props(self) -> None:
        p = reqjs.Pattern("(hi)", reqjs.NAMED_GROUPS)
        self.assertIs(p.flags, reqjs.NOFLAG)
        self.assertEqual(p.pattern, "(hi)")
        self.assertEqual(p.groups, 1)
        self.assertEqual(p.groupindex, {})
        p = reqjs.Pattern("(?<hi>hi)(?<hello>hello)")
        self.assertEqual(p.groupindex, {"hi": 1, "hello": 2})
        self.assertTrue(reqjs.NAMED_GROUPS in p.flags)

    def test_equal(self) -> None:
        p1 = reqjs.compile("hi")
        self.assertEqual(p1, p1)
        reqjs.purge()
        p2 = reqjs.compile("hi")
        self.assertEqual(p1, p2)

    def test_not_equal(self) -> None:
        p1 = reqjs.compile("hi")
        p2 = reqjs.compile("hello")
        reqjs.purge()
        p3 = reqjs.compile("hi")
        self.assertFalse(p1 != p3)
        self.assertNotEqual(p1, p2)
        self.assertNotEqual(p1, 34)

    def test_not_equal_flags(self) -> None:
        p1 = reqjs.compile("hi")
        p2 = reqjs.compile("hi", reqjs.RegexFlag.NOFLAG)
        self.assertNotEqual(p1, p2)

    def test_flag(self) -> None:
        p = reqjs.compile("hi")
        self.assertIs(reqjs.RegexFlag(p.flags), reqjs.UNICODE)
        p = reqjs.compile("hi", reqjs.NAMED_GROUPS)
        self.assertIs(reqjs.RegexFlag(p.flags), reqjs.NOFLAG)

    def test_match_attrs(self) -> None:
        p = reqjs.compile("hi")
        m = p.search("_hi_")
        assert m is not None
        self.assertEqual(m.string, "_hi_")
        self.assertEqual(m.re, p)

    def test_group(self) -> None:
        p = reqjs.compile(
            "(\\d+(?<farewell>goodbye))\\s*(?<maybe>really)?(?<greeting>hello)"
        )
        m = p.search("Wow 23goodbye  hello hi")
        assert m is not None
        self.assertEqual(m.group(), "23goodbye  hello")
        self.assertEqual(m.group(0), "23goodbye  hello")
        self.assertEqual(m.group(1), "23goodbye")
        self.assertEqual(m.group(2), "goodbye")
        self.assertIsNone(m.group(3))
        self.assertEqual(m.group(4), "hello")
        self.assertEqual(m.group("farewell"), "goodbye")
        self.assertEqual(m.group("greeting"), "hello")
        self.assertIsNone(m.group("maybe"))
        self.assertEqual(m.group(2, "farewell"), ("goodbye", "goodbye"))
        with self.assertRaises(IndexError):
            m.group("key")
        with self.assertRaises(IndexError):
            m.group(-2)
        with self.assertRaises(IndexError):
            m.group(6)
        with self.assertRaises(IndexError):
            m.group(2, "key")
        with self.assertRaises(IndexError):
            m.group(None)

    def test_get_item(self) -> None:
        p = reqjs.compile(
            "(\\d+(?<farewell>goodbye))\\s*(?<maybe>really)?(?<greeting>hello)"
        )
        m = p.search("Wow 23goodbye  hello hi")
        assert m is not None
        self.assertEqual(m[0], "23goodbye  hello")
        self.assertEqual(m["farewell"], "goodbye")
        with self.assertRaises(IndexError):
            m[2, "farewell"]
        with self.assertRaises(IndexError):
            m["key"]
        with self.assertRaises(IndexError):
            m[-2]

    def test_offset(self) -> None:
        p = reqjs.compile("hi")
        m = p.search("hi__hi", 2)
        assert m is not None
        self.assertEqual(m.group(), "hi")
        self.assertEqual(m.span(), (4, 6))

    def test_constructor(self) -> None:
        p = reqjs.Pattern("hi")
        self.assertIsNotNone(p.search("yo hi yo"))

    def test_search_func(self) -> None:
        self.assertIsNotNone(reqjs.search("hi", "yo hi yo"))

    def test_pattern_find_iter(self) -> None:
        p = reqjs.Pattern("h[io]")
        res = [m.group() for m in p.finditer("hello hi hello ho hello")]
        self.assertEqual(res, ["hi", "ho"])

    def test_find_iter(self) -> None:
        res = [
            m.group()
            for m in reqjs.finditer("h[io]", "hello hi hello ho hello")
        ]
        self.assertEqual(res, ["hi", "ho"])

    def test_pattern_match(self) -> None:
        p = reqjs.Pattern("hi")
        m = p.match("hello")
        self.assertIsNone(m)
        m = p.match("hello hi hello")
        self.assertIsNone(m)
        m = p.match("hello hi hello", 6)
        self.assertIsNotNone(m)

    def test_match(self) -> None:
        m = reqjs.match("hi", "hello")
        self.assertIsNone(m)
        m = reqjs.match("hi", "hello hi hello")
        self.assertIsNone(m)
        m = reqjs.match("hi", "hi there")
        self.assertIsNotNone(m)
        assert m is not None
        self.assertIn(reqjs.STICKY, m.re.flags)

    def test_pattern_groups(self) -> None:
        p = reqjs.Pattern("hi (hello(\\d+)) (wow) ")
        self.assertEqual(p.groups, 3)
        p = reqjs.Pattern("hi")
        self.assertEqual(p.groups, 0)

    def test_pattern_findall(self) -> None:
        p = reqjs.Pattern("h[io]")
        res = p.findall("hello hi hello ho hello")
        self.assertEqual(res, ["hi", "ho"])
        p = reqjs.Pattern("(h[io])")
        res = p.findall("hello hi hello ho hello")
        self.assertEqual(res, ["hi", "ho"])
        p = reqjs.Pattern("(hi) (ho)")
        res = p.findall("hello hi ho hello hi ho hello")
        self.assertEqual(res, [("hi", "ho"), ("hi", "ho")])
        res = p.findall("hello hi ho hello hi ho hello", 7)
        self.assertEqual(res, [("hi", "ho")])
        res = p.findall("hello hi ho hello hi ho hello", 7, 10)
        self.assertEqual(res, [])

        p = reqjs.Pattern("(hi)(wow)?")
        self.assertEqual(p.findall("hi"), [("hi", "")])

        p = reqjs.Pattern("(hi)?")
        self.assertEqual(p.findall("wow"), ["", "", "", ""])

        p = reqjs.Pattern(r"^|\w+")
        res = p.findall("two words")
        self.assertEqual(res, ["", "wo", "words"])

    def test_findall(self) -> None:
        res = reqjs.findall("h[io]", "hello hi hello ho hello")
        self.assertEqual(res, ["hi", "ho"])
        res = reqjs.findall(r"^|\w+", "two words")
        self.assertEqual(res, ["", "wo", "words"])

    def test_pattern_test(self) -> None:
        p = reqjs.Pattern("hi")
        self.assertIs(p.test("hello"), False)
        self.assertIs(p.test("  hi  "), True)

        with self.assertRaises(TypeError):
            p.test(38)

    def test_split(self) -> None:
        res = reqjs.split("Q", "hello")
        self.assertEqual(res, ["hello"])

        res = reqjs.split(r"\W+", "Words, words, words.")
        self.assertEqual(res, ["Words", "words", "words", ""])
        p = reqjs.Pattern(r"(\W+)")
        res = p.split("Words, words, words.")
        self.assertEqual(["Words", ", ", "words", ", ", "words", ".", ""], res)
        res = reqjs.split(r"\W+", "Words, words, words.", maxsplit=1)
        self.assertEqual(["Words", "words, words."], res)
        res = reqjs.split(r"(\W+)", "...words, words...")
        self.assertEqual(["", "...", "words", ", ", "words", "...", ""], res)

        res = reqjs.split(r"(\W*)", "...words...")
        self.assertEqual(
            [
                "",
                "...",
                "",
                "",
                "w",
                "",
                "o",
                "",
                "r",
                "",
                "d",
                "",
                "s",
                "...",
                "",
                "",
                "",
            ],
            res,
        )

        res = reqjs.split("(h(h)?)", "whw")
        self.assertEqual(["w", "h", None, "w"], res)

    def test_expand(self) -> None:
        m = reqjs.search("((?<val>h)i(?<non>q)?)", "hello hi hello")
        assert m is not None
        self.assertEqual(m.expand("s {} s"), "s hi s")
        self.assertEqual(m.expand(template="s {} s"), "s hi s")
        self.assertEqual(m.expand("s {0} s"), "s hi s")
        self.assertEqual(m.expand("s {1} s"), "s hi s")
        self.assertEqual(m.expand("s {2} s"), "s h s")
        self.assertEqual(m.expand("s {val} s"), "s h s")
        self.assertEqual(m.expand("s {non} s"), "s  s")

    def test_sub(self) -> None:
        res = reqjs.sub("hi", "hello", "ok hi, wow hi")
        self.assertEqual(res, "ok hello, wow hello")

    def test_cache(self):
        p1 = reqjs.Pattern("hi")
        p2 = reqjs.Pattern("hi")
        self.assertIs(p1, p2)  # p2 is the cached p1 object

        # with cleared cache
        reqjs.purge()
        p3 = reqjs.Pattern("hi")
        self.assertIsNot(p1, p3)  # p3 is a distinct newly created object
        self.assertEqual(p1, p3)  # but it is equal to p1

        # overflow cache
        max_cache = reqjs.Pattern._MAXCACHE
        p1 = reqjs.Pattern("hi")
        for i in range(max_cache + 1):
            reqjs.Pattern(f"hi{i}")
        p2 = reqjs.Pattern("hi")
        self.assertIsNot(p1, p2)  # p1 and p2 are distinct objects

    def test_pattern_hash(self):
        p1 = reqjs.Pattern("hi")
        reqjs.purge()
        p2 = reqjs.Pattern("hi")

        # distinct objects, which are equal, so hashes must be equal too
        self.assertIsNot(p1, p2)
        self.assertEqual(p1, p2)
        self.assertFalse(p1 != p2)
        self.assertEqual(hash(p1), hash(p2))

    def test_test(self):
        self.assertIs(reqjs.test("hi", " hi "), True)
        self.assertIs(reqjs.test("hi", " hello "), False)

    def test_pattern_fullmatch(self):
        p = reqjs.Pattern(r"\w{2}")
        self.assertIsNone(p.fullmatch(" hi "))
        self.assertIsNone(p.fullmatch("hi "))
        self.assertIsInstance(p.fullmatch("hi"), reqjs.Match)

    def test_fullmatch(self):
        self.assertIsNone(reqjs.fullmatch(r"\w{2}", " hi "))
        self.assertIsNone(reqjs.fullmatch(r"\w{2}", "hi "))
        m = reqjs.fullmatch(r"\w{2}", "hi")
        self.assertIsInstance(m, reqjs.Match)
        self.assertIs(m.re.flags, reqjs.UNICODE | reqjs.STICKY)

    def test_invalid_flags(self):
        reqjs.Pattern(r"\w{2}")
        with self.assertRaises(ValueError) as exc_ctx:
            reqjs.Pattern(r"\w{2}", reqjs.UNICODE | reqjs.UNICODE_SETS)
        self.assertEqual(
            exc_ctx.exception.args[0], "Invalid regular expression flags"
        )


class TestAnalogy(TestCase):
    def test_pattern_weakref(self):
        for mod in re, reqjs:
            with self.subTest(mod=mod):
                p = mod.compile(r"\w{2}")
                ref = weakref.ref(p)
                self.assertIs(ref(), p)

    def test_match_weakref(self):
        for mod in re, reqjs:
            with self.subTest(mod=mod):
                m = mod.search(r"\w{2}", "hi")
                self.assertIsNotNone(m)
                with self.assertRaises(TypeError):
                    weakref.ref(m)

    def test_pattern_repr(self):

        p = re.compile("\\w{2}")
        self.assertEqual(repr(p), r"re.compile('\\w{2}')")

        p = re.compile("\\w{2}", re.ASCII | re.IGNORECASE)
        self.assertEqual(
            repr(p), r"re.compile('\\w{2}', re.IGNORECASE|re.ASCII)"
        )

        p = reqjs.compile("\\w{2}")
        self.assertEqual(repr(p), r"reqjs.Pattern('\\w{2}')")

        p = reqjs.compile("\\w{2}", reqjs.STICKY | reqjs.IGNORECASE)
        self.assertEqual(
            repr(p), r"reqjs.Pattern('\\w{2}', reqjs.IGNORECASE|reqjs.STICKY)"
        )
