from unittest import TestCase

import reqjs


class ModuleCase(TestCase):
    def test_flag_repr(self):
        self.assertEqual(
            repr(reqjs.IGNORECASE | reqjs.UNICODE),
            "reqjs.IGNORECASE|reqjs.UNICODE",
        )
