"""Known-answer tests for mesh_crypto (FIPS-197, RFC 4493, Mesh Profile 1.0.1 sample data section 8)."""
import unittest

import mesh_crypto as mc

H = bytes.fromhex


class PrimitiveTests(unittest.TestCase):
    def test_aes_fips197(self):
        self.assertEqual(mc.aes(H("000102030405060708090a0b0c0d0e0f"), H("00112233445566778899aabbccddeeff")),
                         H("69c4e0d86a7b0430d8cdb78070b4c55a"))

    def test_cmac_rfc4493_empty_and_16_bytes(self):
        key = H("2b7e151628aed2a6abf7158809cf4f3c")
        self.assertEqual(mc.cmac(key, b""), H("bb1d6929e95937287fa37d129b756746"))
        self.assertEqual(mc.cmac(key, H("6bc1bee22e409f96e93d7e117393172a")), H("070a16b46b4d4144f79bdd9dd04a287c"))


class MeshKeyTests(unittest.TestCase):
    def test_s1(self):
        self.assertEqual(mc.s1(b"test"), H("b73cefbd641ef2ea598c2b6efb62f79c"))

    def test_k2_master(self):
        nid, enc, priv = mc.k2(H("f7a2a44f8e8a8029064f173ddc1e2b00"), b"\x00")
        self.assertEqual(nid, 0x7F)
        self.assertEqual(enc, H("9f589181a0f50de73c8070c7a6d27f46"))
        self.assertEqual(priv, H("4c715bd4a64b938f99b453351653124f"))

    def test_k4(self):
        self.assertEqual(mc.k4(H("3216d1509884b533248541792b877f98")), 0x38)


class NetworkPduTests(unittest.TestCase):
    """Mesh Profile 8.3.1 Message #1 (control message, CTL=1, 64-bit NetMIC)."""
    NETKEY = H("7dd7364cd842ad18c17c2b820c84c3d6")
    PDU = H("68eca487516765b5e5bfdacbaf6cb7fb6bff871f035444ce83a670df")
    IV = 0x12345678

    def test_decrypt_message_1(self):
        keys = mc.NetKeys(self.NETKEY)
        self.assertEqual(keys.nid, 0x68)
        m = mc.net_decrypt(self.PDU, keys, self.IV)
        self.assertIsNotNone(m)
        self.assertEqual((m.ctl, m.ttl, m.seq, m.src, m.dst), (1, 0, 1, 0x1201, 0xFFFD))
        self.assertEqual(m.transport, H("034b50057e400000010000"))

    def test_encrypt_message_1(self):
        keys = mc.NetKeys(self.NETKEY)
        pdu = mc.net_encrypt(keys, self.IV, ctl=1, ttl=0, seq=1, src=0x1201, dst=0xFFFD,
                             transport=H("034b50057e400000010000"))
        self.assertEqual(pdu, self.PDU)

    def test_wrong_key_rejected(self):
        keys = mc.NetKeys(H("00" * 16))
        self.assertIsNone(mc.net_decrypt(self.PDU, keys, self.IV))

    def test_proxy_config_round_trip(self):
        keys = mc.NetKeys(self.NETKEY)
        pdu = mc.net_encrypt(keys, 0, ctl=1, ttl=0, seq=7, src=0x7F00, dst=0x0000, transport=b"\x00\x01",
                             proxy=True)
        m = mc.net_decrypt(pdu, keys, 0, proxy=True)
        self.assertEqual((m.seq, m.src, m.dst, m.transport), (7, 0x7F00, 0x0000, b"\x00\x01"))
        self.assertIsNone(mc.net_decrypt(pdu, keys, 0, proxy=False))


class AccessTests(unittest.TestCase):
    def test_app_round_trip_unsegmented(self):
        appkey = H("0023456789abcdef0023456789abcdef")
        access = H("cfd707" "81" "01" "ce09" "8813" "05")
        upper = mc.app_encrypt(appkey, access, seq=0x10, src=0x0004, dst=0xC001, iv=0)
        self.assertEqual(mc.app_decrypt(appkey, upper, seq=0x10, src=0x0004, dst=0xC001, iv=0), access)
        self.assertIsNone(mc.app_decrypt(appkey, upper, seq=0x11, src=0x0004, dst=0xC001, iv=0))

    def test_parse_vendor_opcode(self):
        self.assertEqual(mc.parse_access(H("cfd7078b84040000")), ((0xCF, 0x07D7), H("8b84040000")))

    def test_seq_auth(self):
        self.assertEqual(mc.seq_auth(seq=0x2005, seq_zero=0x0003), 0x2003)
        self.assertEqual(mc.seq_auth(seq=0x2001, seq_zero=0x1FFF), 0x1FFF)


if __name__ == "__main__":
    unittest.main()
