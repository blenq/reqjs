from unittest import TestCase

import reqjs


class TestUTF16(TestCase):
    def test_utf16(self) -> None:
        p = reqjs.compile("h")
        m = p.search("€e")
        self.assertIsNone(m)
        m = p.search("€h")
        self.assertIsNotNone(m)


class TestOutsideBMP(TestCase):
    def test_outside_bmp_string(self) -> None:
        p = reqjs.compile("h")
        m = p.search("𐐷h")
        assert m is not None
        self.assertEqual(m.span(), (1, 2))

    def test_outside_bmp_offset(self) -> None:
        p = reqjs.compile("h")
        m = p.search("𐐷1234h", 2)
        assert m is not None
        self.assertEqual(m.pos, 2)
        self.assertEqual(m.endpos, 6)
        self.assertEqual(m.group(), "h")
        self.assertEqual(m.span(), (5, 6))
        m = p.search("𐐷1234hmoremore", 2, 8)
        assert m is not None
        self.assertEqual(m.pos, 2)
        self.assertEqual(m.endpos, 8)
        self.assertEqual(m.group(), "h")
        self.assertEqual(m.span(), (5, 6))
        self.assertEqual(m.group(), "h")

    def test_end(self) -> None:
        p = reqjs.compile("h$")
        m = p.search("𐐷testh")
        assert m is not None
        self.assertEqual(m.span(), (5, 6))
        self.assertEqual(m.group(), "h")
        self.assertEqual(m.end(), 6)
        self.assertEqual(m.end(0), 6)

    def test_nested(self) -> None:
        p = reqjs.compile("hi(.i(𐐷hell𐐷)(wow)?(hi)+)")
        m = p.search("start_hi𐐷i𐐷hell𐐷hihi_no")
        assert m is not None
        self.assertEqual(m.span(), (6, 20))
        self.assertEqual(m.group(), "hi𐐷i𐐷hell𐐷hihi")
        self.assertEqual(m.span(1), (8, 20))
        self.assertEqual(m.end(1), 20)
        self.assertEqual(m.group(1), "𐐷i𐐷hell𐐷hihi")
        self.assertEqual(m.span(2), (10, 16))
        self.assertEqual(m.group(2), "𐐷hell𐐷")
        self.assertEqual(m.span(3), (-1, -1))
        self.assertIsNone(m.group(3))
        self.assertEqual(m.span(4), (18, 20))
        self.assertEqual(m.group(4), "hi")

    def test_find_iter(self) -> None:
        res = [m.group() for m in reqjs.finditer("𐐷h", "hello 𐐷hi 𐐷hello ")]
        self.assertEqual(res, ["𐐷h", "𐐷h"])

    def test_no_unicode_flag(self) -> None:
        p = reqjs.compile("hé(?<g𐐷>€l)𐐷lo", reqjs.NOFLAG)
        m = p.search("hi 𐐷 hé€l𐐷lo hi")
        self.assertIsNotNone(m)
        self.assertEqual(m.group(), "hé€l𐐷lo")
        self.assertEqual(m.group("g𐐷"), "€l")
