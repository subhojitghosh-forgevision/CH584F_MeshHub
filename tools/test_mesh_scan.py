import unittest

import mesh_scan


class DescribeTests(unittest.TestCase):
    def test_unprovisioned_device(self):
        data = {mesh_scan.PROV.upper(): bytes.fromhex("4d6573684875622d4d312d7465737421" "0000")}
        self.assertEqual(mesh_scan.describe(data),
                         ["UNPROVISIONED 0x1827: device UUID 4d6573684875622d4d312d7465737421 OOB info 0000"])

    def test_provisioned_proxy(self):
        data = {mesh_scan.PROXY: bytes.fromhex("00" "5a9a06c58f8949d3")}
        self.assertEqual(mesh_scan.describe(data), ["PROXY 0x1828: Network ID 5a9a06c58f8949d3"])

    def test_other_devices_give_nothing(self):
        self.assertEqual(mesh_scan.describe({"0000180f-0000-1000-8000-00805f9b34fb": b"\x64"}), [])


if __name__ == "__main__":
    unittest.main()
