"""Assemble the THROWAWAY Step-0 spike projects from the official WCH CH585 EVT SDK.

  node/     <- EVT/EXAM/BLE/MESH/adv_vendor_self_provision_with_peripheral
  iap/      <- EVT/EXAM/BLE/MESH/adv_vendor_self_provision_IAP
  jumpiap/  <- EVT/EXAM/BLE/MESH/adv_vendor_self_provision_JumpIAP

Linked SDK folders are copied in, then CH584 and WeAct-board edits are applied.
Every edit must match exactly once, otherwise the script stops.
"""
import argparse
import os
import re
import shutil
import sys

SDK = r"C:\Embedded\WCH\SDK\CH585EVT\EVT\EXAM"
MESH = os.path.join(SDK, "BLE", "MESH")
WEACT_HAL = r"C:\Embedded\WCH\WeActStudio.WCH-BLE-Core\Examples\CH584\ble\broadcaster\ble\HAL"
PROJECTS = {
    "node": ("adv_vendor_self_provision_with_peripheral", "spike_node"),
    "iap": ("adv_vendor_self_provision_IAP", "spike_iap"),
    "jumpiap": ("adv_vendor_self_provision_JumpIAP", "spike_jumpiap"),
}


def load(path):
    raw = open(path, "rb").read()
    return raw.decode("latin-1").replace("\r\n", "\n"), b"\r\n" in raw


def save(path, text, crlf):
    open(path, "wb").write((text.replace("\n", "\r\n") if crlf else text).encode("latin-1"))


def edit(path, pattern, repl, label, flags=0, expand=False):
    text, crlf = load(path)
    new, n = re.subn(pattern, (lambda m: m.expand(repl)) if expand else (lambda m: repl), text, flags=flags)
    if n != 1:
        sys.exit(f"ABORT [{path}] '{label}' matched {n} times (expected 1)")
    save(path, new, crlf)
    print(f"  ok  {os.path.basename(os.path.dirname(path))}/{os.path.basename(path)}: {label}")


def copy_project(sdk_name, dst, new_name):
    src = os.path.join(MESH, sdk_name)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("obj"))
    project_text, _ = load(os.path.join(src, ".project"))
    for link_name, uri in re.findall(r"<link>\s*<name>([^<]+)</name>\s*<type>2</type>\s*<locationURI>([^<]+)</locationURI>",
                                     project_text):
        m = re.match(r"PARENT-(\d+)-PROJECT_LOC/(.+)", uri)
        base = src
        for _ in range(int(m.group(1))):
            base = os.path.dirname(base)
        shutil.copytree(os.path.join(base, m.group(2)), os.path.join(dst, link_name))
    project = os.path.join(dst, ".project")
    edit(project, r"(<projectDescription>\s*<name>)[^<]+(</name>)", r"\g<1>" + new_name + r"\g<2>", "project name",
         expand=True)
    edit(project, r"[ \t]*<linkedResources>.*?</linkedResources>\n", "", "linked folders copied in", flags=re.S)


def assemble(dest, force=False):
    dirs = {key: os.path.join(dest, key) for key in PROJECTS}
    for key, d in dirs.items():
        if os.path.exists(d):
            if not force:
                sys.exit(f"ABORT: {d} exists (use --force to rebuild generated spike projects)")
            shutil.rmtree(d)
    os.makedirs(dest, exist_ok=True)
    for key, (sdk_name, new_name) in PROJECTS.items():
        print(f"{new_name}: copying {sdk_name}")
        copy_project(sdk_name, dirs[key], new_name)
    apply_board_edits(dirs)
    return dirs


def apply_board_edits(dirs):
    node, iap, jumpiap = dirs["node"], dirs["iap"], dirs["jumpiap"]
    for d in (node, iap):
        edit(os.path.join(d, "Ld", "Link.ld"), r"RAM \(xrw\) : ORIGIN = 0x20005000, LENGTH = 108K",
             "RAM (xrw) : ORIGIN = 0x20005000, LENGTH = 76K /* CH584: 96K RAM; WCH layout keeps 0x20000000-0x20004FFF for the ROM library */",
             "RAM 76K (CH584)")
    edit(os.path.join(jumpiap, "Ld", "Link.ld"), r"RAM \(xrw\) : ORIGIN = 0x20000000, LENGTH = 128K",
         "RAM (xrw) : ORIGIN = 0x20000000, LENGTH = 96K /* CH584 */", "RAM 96K (CH584)")
    edit(os.path.join(node, ".cproject"), r'(\t+)<listOptionValue builtIn="false" value="DEBUG=0"/>\n',
         r'\g<0>\g<1><listOptionValue builtIn="false" value="CLK_OSC32K=0"/>' + "\n"
         + r'\g<1><listOptionValue builtIn="false" value="DCDC_ENABLE=1"/>' + "\n",
         "defines CLK_OSC32K=0, DCDC_ENABLE=1", expand=True)
    edit(os.path.join(node, "APP", "app_main.c"), re.escape("    HSECFG_Capacitance(HSECap_18p);"),
         "#if(defined(DCDC_ENABLE)) && (DCDC_ENABLE == TRUE)\n    PWR_DCDCCfg(ENABLE);\n#endif\n"
         "    HSECFG_Capacitance(HSECap_10p); // WeAct CH584F core board value",
         "DC-DC call + HSE 10p")
    shutil.copyfile(os.path.join(WEACT_HAL, "KEY.c"), os.path.join(node, "HAL", "KEY.c"))
    shutil.copyfile(os.path.join(WEACT_HAL, "include", "KEY.h"), os.path.join(node, "HAL", "include", "KEY.h"))
    print("  ok  node/HAL: WeAct KEY.c/KEY.h (KEY2 removed)")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Assemble the throwaway Step-0 spike projects")
    ap.add_argument("--dest", default=os.path.dirname(os.path.abspath(__file__)))
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)
    assemble(a.dest, a.force)
    print("ASSEMBLED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
