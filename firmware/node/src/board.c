/* WeAct CH584F core board: LED on PB6, active low. */
#include "CONFIG.h"
#include "board.h"

#define BOARD_LED_PIN GPIO_Pin_6

void board_init(void)
{
    GPIOB_SetBits(BOARD_LED_PIN);
    GPIOB_ModeCfg(BOARD_LED_PIN, GPIO_ModeOut_PP_5mA);
}

void board_led_set(bool on)
{
    if(on)
    {
        GPIOB_ResetBits(BOARD_LED_PIN);
    }
    else
    {
        GPIOB_SetBits(BOARD_LED_PIN);
    }
}

void board_boot_blink(void)
{
    board_led_set(true);
    mDelaymS(100);
    board_led_set(false);
}
