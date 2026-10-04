"""Single description of the firmware projects; generates their MounRiver/Eclipse project files.

    python firmware/projects.py      # rewrite firmware/<project>/.project and .cproject

Each .cproject is the matching WCH SDK example's .cproject with our option lists substituted. Each .project
links the SDK folders and files the project compiles, in WCH's own PARENT-n-PROJECT_LOC form.
"""
import os
import re
import sys
from dataclasses import dataclass, field
from xml.sax.saxutils import escape

HERE = os.path.dirname(os.path.abspath(__file__))
SDK = r"C:\Embedded\WCH\SDK\CH585EVT\EVT\EXAM"
SDK_FROM_PROJECT = "PARENT-4-PROJECT_LOC/SDK/CH585EVT/EVT/EXAM"   # firmware/<project> -> C:\Embedded\WCH
MESH = "BLE/MESH"
OPT = "ilg.gnumcueclipse.managedbuild.cross.riscv.option."

PROJECT_XML = """<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<projectDescription>
\t<name>{name}</name>
\t<comment/>
\t<projects>
\t</projects>
\t<buildSpec>
\t\t<buildCommand>
\t\t\t<name>org.eclipse.cdt.managedbuilder.core.genmakebuilder</name>
\t\t\t<triggers>clean,full,incremental,</triggers>
\t\t\t<arguments>
\t\t\t</arguments>
\t\t</buildCommand>
\t\t<buildCommand>
\t\t\t<name>org.eclipse.cdt.managedbuilder.core.ScannerConfigBuilder</name>
\t\t\t<triggers>full,incremental,</triggers>
\t\t\t<arguments>
\t\t\t</arguments>
\t\t</buildCommand>
\t</buildSpec>
\t<natures>
\t\t<nature>org.eclipse.cdt.core.cnature</nature>
\t\t<nature>org.eclipse.cdt.managedbuilder.core.managedBuildNature</nature>
\t\t<nature>org.eclipse.cdt.managedbuilder.core.ScannerConfigNature</nature>
\t</natures>
\t<linkedResources>
{links}\t</linkedResources>
</projectDescription>
"""
LINK_XML = "\t\t<link>\n\t\t\t<name>{name}</name>\n\t\t\t<type>{type}</type>\n\t\t\t<locationURI>{uri}</locationURI>\n\t\t</link>\n"


@dataclass
class Project:
    folder: str          # firmware/<folder>
    name: str            # Eclipse project name
    template: str        # SDK example under BLE/MESH whose .cproject is the base
    links: list          # [(virtual name, SDK-relative path with '/')]; folder or file is read from the SDK
    lists: dict = field(default_factory=dict)   # .cproject list options to replace: key after OPT -> values
    sources: list = None                         # [(sourcePath name, excluding or None)]; None keeps the template's


def ws(path):
    """A project-relative path as MounRiver writes it in include and library lists."""
    return '"${workspace_loc:/${ProjName}/' + path + '}"'


def _check_sdk_reachable(folder):
    base = os.path.join(HERE, folder)
    for _ in range(4):
        base = os.path.dirname(base)
    if os.path.normcase(os.path.join(base, "SDK", "CH585EVT", "EVT", "EXAM")) != os.path.normcase(SDK):
        raise RuntimeError("PARENT-4-PROJECT_LOC from firmware/<project> does not reach the WCH SDK; "
                           r"the repository must be at C:\Embedded\WCH\projects\CH584F_MeshHub")


def project_xml(p):
    _check_sdk_reachable(p.folder)
    links = []
    for name, sdk_path in p.links:
        real = os.path.join(SDK, *sdk_path.split("/"))
        if not os.path.exists(real):
            raise FileNotFoundError(real)
        links.append(LINK_XML.format(name=name, type=2 if os.path.isdir(real) else 1,
                                     uri=f"{SDK_FROM_PROJECT}/{sdk_path}"))
    return PROJECT_XML.format(name=p.name, links="".join(links))


def set_list_option(text, key, values):
    pattern = re.compile(r'(<option\b[^>]*?superClass="' + re.escape(OPT + key) + r'"[^>]*?)(?:/>|>.*?</option>)', re.S)

    def repl(m):
        opening = re.sub(r'IS_VALUE_EMPTY="(true|false)"', f'IS_VALUE_EMPTY="{"false" if values else "true"}"',
                         m.group(1))
        items = "".join(f'\n\t\t\t\t\t\t\t\t\t<listOptionValue builtIn="false" value="{escape(v, {chr(34): "&quot;"})}"/>'
                        for v in values)
        return f"{opening}>{items}\n\t\t\t\t\t\t\t\t</option>"

    new, count = pattern.subn(repl, text)
    if count == 0:
        raise ValueError(f"option {key} not found in the template .cproject")
    return new


def set_source_entries(text, entries):
    body = "".join(
        "\t\t\t\t\t\t<entry " + (f'excluding="{exc}" ' if exc else "")
        + f'flags="VALUE_WORKSPACE_PATH|RESOLVED" kind="sourcePath" name="{name}"/>\n'
        for name, exc in entries)
    new, count = re.subn(r"<sourceEntries>.*?</sourceEntries>",
                         lambda m: "<sourceEntries>\n" + body + "\t\t\t\t\t</sourceEntries>", text, flags=re.S)
    if count == 0:
        raise ValueError("sourceEntries not found in the template .cproject")
    return new


def cproject_xml(p):
    with open(os.path.join(SDK, *MESH.split("/"), p.template, ".cproject"), encoding="utf-8") as f:
        text = f.read()
    for key, values in p.lists.items():
        text = set_list_option(text, key, values)
    if p.sources is not None:
        text = set_source_entries(text, p.sources)
    return text


def generate(p):
    folder = os.path.join(HERE, p.folder)
    os.makedirs(folder, exist_ok=True)
    files = {".project": project_xml(p), ".cproject": cproject_xml(p)}
    for name, text in files.items():
        with open(os.path.join(folder, name), "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
    return files


IAP_SDK = f"{MESH}/adv_vendor_self_provision_IAP"
JUMPIAP_SDK = f"{MESH}/adv_vendor_self_provision_JumpIAP"

IAP = Project(folder="iap", name="meshhub_iap", template="adv_vendor_self_provision_IAP",
              links=[("APP", f"{IAP_SDK}/APP"),
                     ("Startup", f"{IAP_SDK}/Startup"),
                     ("RVMSIS", "SRC/RVMSIS"),
                     ("StdPeriphDriver", "SRC/StdPeriphDriver")])

JUMPIAP = Project(folder="jumpiap", name="meshhub_jumpiap", template="adv_vendor_self_provision_JumpIAP",
                  links=[("APP", f"{JUMPIAP_SDK}/APP"),
                         ("Profile", f"{JUMPIAP_SDK}/Profile"),
                         ("Startup", f"{JUMPIAP_SDK}/Startup"),
                         ("HAL", "BLE/HAL"),
                         ("LIB", "BLE/LIB"),
                         ("RVMSIS", "SRC/RVMSIS"),
                         ("StdPeriphDriver", "SRC/StdPeriphDriver")])

NODE_SDK = f"{MESH}/adv_vendor_self_provision_with_peripheral"

NODE = Project(
    folder="node", name="meshhub_node", template="adv_vendor_self_provision_with_peripheral",
    links=[("Startup", f"{NODE_SDK}/Startup"),
           ("sdk_hal", "BLE/HAL"),
           ("LIB", "BLE/LIB"),
           ("MESH_LIB", f"{MESH}/MESH_LIB"),
           ("RVMSIS", "SRC/RVMSIS"),
           ("StdPeriphDriver", "SRC/StdPeriphDriver")],
    lists={
        "c.compiler.defs": ["DEBUG=0", "BLE_BUFF_MAX_LEN=251", "LIB_FLASH_BASE_ADDRESSS=0x0004E000", "CH58xBLE_ROM",
                            "BLE_MEMHEAP_SIZE=5632", "HAL_KEY=1", "CLK_OSC32K=0", "DCDC_ENABLE=1"],
        "assembler.defs": ["LIB_FLASH_BASE_ADDRESSS=0x0004E000"],
        "c.compiler.include.paths": [ws("hal/include"), ws("src"), ws("StdPeriphDriver/inc"), ws("RVMSIS"),
                                     ws("LIB"), ws("MESH_LIB")],
        "c.linker.libs": ["ISP585", "CH58xMESHROM"],
        "c.linker.paths": ['"../"', ws("MESH_LIB"), ws("LIB"), ws("StdPeriphDriver")],
    },
    sources=[("src", None), ("hal", None), ("sdk_hal", "KEY.c"), ("Startup", None), ("StdPeriphDriver", None),
             ("RVMSIS", None), ("LIB", None)])

PROJECTS = [JUMPIAP, NODE, IAP]


def main():
    for p in PROJECTS:
        generate(p)
        print(f"generated firmware/{p.folder}/.project and .cproject")
    return 0


if __name__ == "__main__":
    sys.exit(main())
