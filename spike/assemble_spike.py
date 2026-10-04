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
import stat
import sys

SDK = r"C:\Embedded\WCH\SDK\CH585EVT\EVT\EXAM"
MESH = os.path.join(SDK, "BLE", "MESH")
WEACT_HAL = r"C:\Embedded\WCH\WeActStudio.WCH-BLE-Core\Examples\CH584\ble\broadcaster\ble\HAL"
PROJECTS = {
    "node": ("adv_vendor_self_provision_with_peripheral", "spike_node"),
    "iap": ("adv_vendor_self_provision_IAP", "spike_iap"),
    "jumpiap": ("adv_vendor_self_provision_JumpIAP", "spike_jumpiap"),
}


SPIKE_BLOCK = """/* ===== SPIKE (throwaway, Step 0) ===================================== */
#ifndef SPIKE_VERSION
#define SPIKE_VERSION        1
#endif
#define SPIKE_PUB_EVT        (1 << 8)
#define SPIKE_PUB_PERIOD     (1600 * 5)            // 5 s (TMOS tick = 0.625 ms)
#define SPIKE_READINGS_GROUP 0xC001

// Fixed static OOB for the spike only: 00112233445566778899AABBCCDDEEFF
static const uint8_t spike_static_oob[16] = {
    0x00, 0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77,
    0x88, 0x99, 0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF,
};

static void spike_led(BOOL on)
{
    GPIOB_ModeCfg(GPIO_Pin_6, GPIO_ModeOut_PP_5mA);
    on ? GPIOB_ResetBits(GPIO_Pin_6) : GPIOB_SetBits(GPIO_Pin_6);
}

static void spike_boot_blink(uint8_t count)
{
    uint8_t i;
    for(i = 0; i < count; i++)
    {
        spike_led(TRUE);
        DelayMs(200);
        spike_led(FALSE);
        DelayMs(300);
    }
}

// READING payload (spec 4.3): 0x01, temperature int16 0.01 C, humidity uint16 0.01 %RH, sequence
static void spike_publish(void)
{
    static uint8_t seq = 0;
    static int16_t temp = 2500;
    const uint16_t rh = 5000;
    uint8_t p[6];

    if(!bt_mesh_is_provisioned() || (vnd_models[0].keys[0] == BLE_MESH_KEY_UNUSED))
    {
        return;
    }
    temp = (temp >= 3000) ? 2000 : (int16_t)(temp + 10);
    p[0] = 0x01;
    p[1] = (uint8_t)(temp & 0xFF);
    p[2] = (uint8_t)((temp >> 8) & 0xFF);
    p[3] = (uint8_t)(rh & 0xFF);
    p[4] = (uint8_t)((rh >> 8) & 0xFF);
    p[5] = seq++;
    vendor_model_srv_send(SPIKE_READINGS_GROUP, p, sizeof(p));
}
/* ===================================================================== */

"""

SPIKE_EVENT = """    if(events & SPIKE_PUB_EVT)
    {
        spike_publish();
        tmos_start_task(App_TaskID, SPIKE_PUB_EVT, SPIKE_PUB_PERIOD);
        return (events ^ SPIKE_PUB_EVT);
    }

"""


def load(path):
    with open(path, "rb") as f:
        raw = f.read()
    return raw.decode("latin-1").replace("\r\n", "\n"), b"\r\n" in raw


def save(path, text, crlf):
    with open(path, "wb") as f:
        f.write((text.replace("\n", "\r\n") if crlf else text).encode("latin-1"))


def force_remove(func, path, exc):
    """rmtree error handler: clear the read-only attribute (set on some SDK files) and retry."""
    os.chmod(path, stat.S_IWRITE)
    func(path)


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
            shutil.rmtree(d, onexc=force_remove)
    os.makedirs(dest, exist_ok=True)
    for key, (sdk_name, new_name) in PROJECTS.items():
        print(f"{new_name}: copying {sdk_name}")
        copy_project(sdk_name, dirs[key], new_name)
    apply_board_edits(dirs)
    apply_spike_features(dirs["node"])
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


def apply_spike_features(node):
    cfg = os.path.join(node, "APP", "include", "app_mesh_config.h")
    edit(cfg, r"(#define CONFIG_BLE_MESH_PROXY\s+)0\b", r"\g<1>1", "PROXY 1", expand=True)
    edit(cfg, r"(#define CONFIG_BLE_MESH_PB_GATT\s+)0\b", r"\g<1>1", "PB_GATT 1", expand=True)
    edit(cfg, r"(#define CONFIG_MESH_UNSEG_LENGTH_DEF\s+)\(221\)", r"\g<1>(7)", "UNSEG_LENGTH 7", expand=True)
    edit(cfg, r"(#define CONFIG_MESH_RX_SDU_DEF\s+)\(192\)", r"\g<1>(256)", "RX_SDU 256", expand=True)

    app = os.path.join(node, "APP", "app.c")
    edit(app, re.escape("static const struct bt_mesh_prov app_prov = {"),
         SPIKE_BLOCK + "static const struct bt_mesh_prov app_prov = {", "spike block")
    edit(app, re.escape("    .uuid = dev_uuid,\n    .link_open = link_open,"),
         "    .uuid = dev_uuid,\n"
         "    .static_val = spike_static_oob, // SPIKE: fixed test value; production reads the factory page\n"
         "    .static_val_len = sizeof(spike_static_oob),\n"
         "    .link_open = link_open,", "static OOB in prov struct")
    edit(app, re.escape("    GAPRole_PeripheralInit();\n    Peripheral_Init();\n"),
         "    spike_boot_blink(SPIKE_VERSION); // SPIKE: custom WCH peripheral not started; the phone uses the mesh proxy\n",
         "no custom peripheral, boot blink")
    edit(app, re.escape("    HAL_KeyInit();\n    HalKeyConfig(keyPress);\n}"),
         "    HAL_KeyInit();\n    HalKeyConfig(keyPress);\n"
         "    tmos_start_task(App_TaskID, SPIKE_PUB_EVT, SPIKE_PUB_PERIOD);\n}", "start publish timer")
    edit(app, re.escape("    // Discard unknown events\n    return 0;\n}"),
         SPIKE_EVENT + "    // Discard unknown events\n    return 0;\n}", "publish event handler")
    # WCH's handler only passes MSG (0xCF) to App_trans_model_reveived; spec 4.2 sends unicast commands as WRT (0xCC)
    edit(app, r"(OP_VENDOR_MESSAGE_TRANSPARENT_WRT\)\n    \{\n(?:[ \t]*//[^\n]*\n)*[ \t]*APP_DBG\(\"len %d, data 0x%02x from 0x%04x\", "
              r"val->vendor_model_srv_Event\.write\.len,\n[ \t]*val->vendor_model_srv_Event\.write\.pdata\[0\],\n"
              r"[ \t]*val->vendor_model_srv_Event\.write\.addr\);\n)",
         r"\g<1>        App_trans_model_reveived(val->vendor_model_srv_Event.write.pdata, val->vendor_model_srv_Event.write.len," + "\n"
         + r"            val->vendor_model_srv_Event.write.addr); // SPIKE: unicast commands arrive as acknowledged WRT (spec 4.2)" + "\n",
         "route WRT to command handler", expand=True)

    per = os.path.join(node, "APP", "peripheral.c")
    for header in ("void peripheralChar4Notify(uint8_t *pValue, uint16_t len)\n{\n",
                   "void Peripheral_AdvertData_Privisioned(uint8_t privisioned)\n{\n",
                   "void Peripheral_TerminateLink(void)\n{\n"):
        edit(per, re.escape(header), header + "    return; // SPIKE: custom peripheral not started\n",
             "guard " + header.split("(")[0].split()[-1])

    # WCH's update-capable example never advertises as unprovisioned (it self-provisions from its own phone app).
    # Call prov_enable() where adv_proxy does: at startup when unprovisioned, after a failed link, after a reset.
    enable = "prov_enable(); // SPIKE: advertise as unprovisioned (PB-ADV beacon + PB-GATT), as adv_proxy does"
    edit(app, re.escape('        Peripheral_AdvertData_Privisioned(FALSE);\n    }\n\n    APP_DBG("Mesh initialized");'),
         '        Peripheral_AdvertData_Privisioned(FALSE);\n        ' + enable + '\n    }\n\n    APP_DBG("Mesh initialized");',
         "prov_enable at startup")
    edit(app, re.escape('    if(reason != CLOSE_REASON_SUCCESS)\n        APP_DBG("reason %x", reason);\n}'),
         '    if(reason != CLOSE_REASON_SUCCESS)\n        APP_DBG("reason %x", reason);\n'
         '    if(!bt_mesh_is_provisioned())\n    {\n        ' + enable + '\n    }\n}',
         "prov_enable after failed link")
    edit(app, re.escape('    APP_DBG("Waiting for privisioning data");\n#if(CONFIG_BLE_MESH_LOW_POWER)\n    bt_mesh_lpn_set(FALSE);'),
         '    ' + enable + '\n    APP_DBG("Waiting for privisioning data");\n#if(CONFIG_BLE_MESH_LOW_POWER)\n    bt_mesh_lpn_set(FALSE);',
         "prov_enable after reset")
    edit(os.path.join(node, "APP", "include", "app_trans_process.h"), re.escape("#define LED_PIN    GPIO_Pin_18"),
         "#define LED_PIN    GPIO_Pin_6 // SPIKE: WeAct CH584F LED (PB6, active low); on = provisioned",
         "LED_PIN = PB6")


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
