import unittest

import binance_data_engine


class PackageSmokeTest(unittest.TestCase):
    def test_package_exposes_version(self):
        self.assertTrue(binance_data_engine.__version__)


if __name__ == "__main__":
    unittest.main()
