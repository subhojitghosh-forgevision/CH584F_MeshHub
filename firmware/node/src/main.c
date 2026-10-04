/* MeshHub node start-up (spec step 1, section 4). Based on WCH's adv_vendor_self_provision_with_peripheral
 * app_main.c, with the board settings from the Step 0 spike (DC-DC call, 10 pF crystal capacitors). */
#include "CONFIG.h"
#include "MESH_LIB.h"
#include "HAL.h"
#include "app_mesh_config.h"
#include "board.h"
#include "mesh_node.h"

_Static_assert(CHIP_ID == ID_CH584, "hal/include/CONFIG.h must target the CH584");
_Static_assert(BLE_SNV == FALSE, "BLE SNV must be off: DataFlash 0x7000 is the OTA ImageFlag");
_Static_assert(DCDC_ENABLE == TRUE, "the project must define DCDC_ENABLE=1");

__attribute__((aligned(4))) uint32_t MEM_BUF[BLE_MEMHEAP_SIZE / 4];

__HIGH_CODE
__attribute__((noinline))
void Main_Circulation(void)
{
    while(1)
    {
        TMOS_SystemProcess();
    }
}

static uint8_t mesh_lib_init(void)
{
    uint8_t ret;

    if(tmos_memcmp(VER_MESH_LIB, VER_MESH_FILE, strlen(VER_MESH_FILE)) == FALSE)
    {
        PRINT("mesh head file error...\n");
        while(1);
    }
    ret = RF_RoleInit();
    hal_rf_tx_wait_enable(ENABLE);
    ret = GAPRole_PeripheralInit(); /* the proxy and PB-GATT need the peripheral role */
    MeshTimer_Init();
    MeshDeamon_Init();
    ble_sm_alg_ecc_init();
    return ret;
}

int main(void)
{
    PWR_DCDCCfg(ENABLE);            /* DCDC_ENABLE alone does nothing (Step 0 spike) */
    HSECFG_Capacitance(HSECap_10p); /* WeAct CH584F core board crystal */
    SetSysClock(SYSCLK_FREQ);
#ifdef DEBUG
    GPIOA_SetBits(GPIO_Pin_14);
    GPIOPinRemap(ENABLE, RB_PIN_UART0);
    GPIOA_ModeCfg(GPIO_Pin_15, GPIO_ModeIN_PU);
    GPIOA_ModeCfg(GPIO_Pin_14, GPIO_ModeOut_PP_5mA);
    UART0_DefInit();
#endif
    board_init();
    board_boot_blink();
    PRINT("%s\n", VER_LIB);
    PRINT("%s\n", VER_MESH_LIB);
    CH58x_BLEInit();
    HAL_Init();
    mesh_lib_init();
    mesh_node_init();
    Main_Circulation();
}
