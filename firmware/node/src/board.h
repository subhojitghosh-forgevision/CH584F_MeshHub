#ifndef BOARD_H
#define BOARD_H

#include <stdbool.h>

void board_init(void);
void board_led_set(bool on);
void board_boot_blink(void);

#endif
