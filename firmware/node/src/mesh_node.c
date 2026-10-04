/* Bluetooth mesh set-up, M1 skeleton (spec step 1, sections 4 and 7.6).
 * Composition: Config Server and Health Server. The WCH vendor server is added in M4.
 * Unprovisioned: unprovisioned beacon and PB-GATT advertising with a fixed test UUID.
 * M2 replaces the test UUID with the factory page's UUID and adds static OOB and the provisioning window.
 * Init sequence as in WCH's adv_proxy and adv_vendor_self_provision_with_peripheral examples. */
#include "CONFIG.h"
#include "MESH_LIB.h"
#include "HAL.h"
#include "app_mesh_config.h"
#include "mesh_node.h"

/* ASCII "MeshHub-M1-test!" */
const uint8_t MESH_NODE_TEST_UUID[16] = {0x4D, 0x65, 0x73, 0x68, 0x48, 0x75, 0x62, 0x2D,
                                         0x4D, 0x31, 0x2D, 0x74, 0x65, 0x73, 0x74, 0x21};

static uint8_t MESH_MEM[1024 * 3] = {0};
extern const ble_mesh_cfg_t app_mesh_cfg;
extern const struct device  app_dev;

static uint8_t dev_uuid[16];
static uint8_t mac_addr[6];

static void cfg_srv_rsp_handler(const cfg_srv_status_t *val);
static void link_open(bt_mesh_prov_bearer_t bearer);
static void link_close(bt_mesh_prov_bearer_t bearer, uint8_t reason);
static void prov_complete(uint16_t net_idx, uint16_t addr, uint8_t flags, uint32_t iv_index);
static void prov_reset(void);

static struct bt_mesh_cfg_srv cfg_srv = {
    .relay = BLE_MESH_RELAY_ENABLED,
    .beacon = BLE_MESH_BEACON_ENABLED,
#if(CONFIG_BLE_MESH_PROXY)
    .gatt_proxy = BLE_MESH_GATT_PROXY_ENABLED,
#endif
    .default_ttl = 5,
    .net_transmit = BLE_MESH_TRANSMIT(7, 10),
    .relay_retransmit = BLE_MESH_TRANSMIT(7, 10),
    .handler = cfg_srv_rsp_handler,
};

static struct bt_mesh_health_srv health_srv;
BLE_MESH_HEALTH_PUB_DEFINE(health_pub, 8);

uint16_t cfg_srv_keys[CONFIG_MESH_MOD_KEY_COUNT_DEF] = {BLE_MESH_KEY_UNUSED};
uint16_t cfg_srv_groups[CONFIG_MESH_MOD_GROUP_COUNT_DEF] = {BLE_MESH_ADDR_UNASSIGNED};
uint16_t health_srv_keys[CONFIG_MESH_MOD_KEY_COUNT_DEF] = {BLE_MESH_KEY_UNUSED};
uint16_t health_srv_groups[CONFIG_MESH_MOD_GROUP_COUNT_DEF] = {BLE_MESH_ADDR_UNASSIGNED};

static struct bt_mesh_model root_models[] = {
    BLE_MESH_MODEL_CFG_SRV(cfg_srv_keys, cfg_srv_groups, &cfg_srv),
    BLE_MESH_MODEL_HEALTH_SRV(health_srv_keys, health_srv_groups, &health_srv, &health_pub),
};

static struct bt_mesh_elem elements[] = {
    {
        .loc = (0),
        .model_count = ARRAY_SIZE(root_models),
        .models = (root_models),
    }
};

const struct bt_mesh_comp app_comp = {
    .cid = 0x07D7, /* WCH */
    .elem = elements,
    .elem_count = ARRAY_SIZE(elements),
};

static const struct bt_mesh_prov app_prov = {
    .uuid = dev_uuid,
    .link_open = link_open,
    .link_close = link_close,
    .complete = prov_complete,
    .reset = prov_reset,
};

static void prov_enable(void)
{
    if(bt_mesh_is_provisioned())
    {
        return;
    }
    bt_mesh_scan_enable();
    bt_mesh_beacon_enable();
    if(CONFIG_BLE_MESH_PB_GATT)
    {
        bt_mesh_proxy_prov_enable();
    }
}

static void cfg_srv_rsp_handler(const cfg_srv_status_t *val)
{
    APP_DBG("config status %d", val->cfgHdr.status);
}

static void link_open(bt_mesh_prov_bearer_t bearer)
{
    APP_DBG("bearer %d", bearer);
}

static void link_close(bt_mesh_prov_bearer_t bearer, uint8_t reason)
{
    APP_DBG("reason %x", reason);
    if(!bt_mesh_is_provisioned())
    {
        prov_enable();
    }
}

static void prov_complete(uint16_t net_idx, uint16_t addr, uint8_t flags, uint32_t iv_index)
{
    APP_DBG("provisioned, address 0x%04x", addr);
}

static void prov_reset(void)
{
    prov_enable();
}

void mesh_node_init(void)
{
    int        err;
    mem_info_t info;

    info.base_addr = MESH_MEM;
    info.mem_len = ARRAY_SIZE(MESH_MEM);
    GetMACAddress(mac_addr);
    tmos_memcpy(dev_uuid, MESH_NODE_TEST_UUID, sizeof(dev_uuid));

    err = bt_mesh_cfg_set(&app_mesh_cfg, &app_dev, mac_addr, &info);
    if(err)
    {
        APP_DBG("Unable set configuration (err:%d)", err);
        return;
    }
    hal_rf_init();
    err = bt_mesh_comp_register(&app_comp);
    bt_mesh_relay_init();
    bt_mesh_proxy_beacon_init_register((void *)bt_mesh_proxy_beacon_init);
    gatts_notify_register(bt_mesh_gatts_notify);
    proxy_gatt_enable_register(bt_mesh_proxy_gatt_enable);
    proxy_prov_enable_register(bt_mesh_proxy_prov_enable);
    bt_mesh_proxy_init();
    bt_mesh_prov_retransmit_init();
    err = bt_mesh_prov_init(&app_prov);
    bt_mesh_mod_init();
    bt_mesh_net_init();
    bt_mesh_trans_init();
    bt_mesh_beacon_init();
    bt_mesh_adv_init();
    bt_mesh_conn_adv_init();
    bt_mesh_settings_init();
    bt_mesh_adapt_init();
    if(err)
    {
        APP_DBG("Initializing mesh failed (err %d)", err);
        return;
    }
    settings_load();
    if(!bt_mesh_is_provisioned())
    {
        prov_enable();
    }
}
