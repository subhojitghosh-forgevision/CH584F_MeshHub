import unittest

import check_image

ELF = r"C:\Embedded\WCH\projects\CH584F_BLE_LED\obj\CH584F_BLE_LED.elf"
HEX = r"C:\Embedded\WCH\projects\CH584F_BLE_LED\obj\CH584F_BLE_LED.hex"


class CheckImageTests(unittest.TestCase):
    def test_good_image_passes(self):
        self.assertEqual(check_image.check(HEX, 0x0, 0x70000, elf=ELF, stack_top=0x20018000), [])

    def test_wrong_stack_top_is_reported(self):
        errors = check_image.check(HEX, 0x0, 0x70000, elf=ELF, stack_top=0x20020000)
        self.assertEqual(len(errors), 1)
        self.assertIn("0x20018000", errors[0])

    def test_image_outside_flash_range_is_reported(self):
        errors = check_image.check(HEX, 0x1000, 0x27000)
        self.assertTrue(any("outside" in e for e in errors))

    def test_hex_only_check_works_without_elf(self):
        self.assertEqual(check_image.check(HEX, 0x0, 0x70000), [])

    def test_stack_top_without_elf_is_rejected(self):
        with self.assertRaises(ValueError):
            check_image.check(HEX, 0x0, 0x70000, stack_top=0x20020000)

    def test_cli_stack_top_without_elf_is_an_error_not_ok(self):
        with self.assertRaises(SystemExit) as cm:
            check_image.main(["--hex", HEX, "--flash", "0x0:0x70000", "--stack-top", "0x20020000"])
        self.assertNotEqual(cm.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
