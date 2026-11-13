#ifndef COMP_PINS_H
#define COMP_PINS_H

/* GPIO map of the main board (hardware/mainboard/gen_pcb.py is the source of truth).
 *
 * Firmware updates: one .uf2 on the UI MCU (USB-C, BOOTSEL drive mode via an "update" hotkey,
 * reset_usb_boot(), or a double tap of the pinhole RESET button). The UI image carries the NET MCU
 * image and writes it over SWD (UI_PIN_NET_SWCLK/SWDIO) when the NET version differs. The NET MCU's
 * own USB is on internal connector J14 (factory / recovery flashing). */

/* ---- UI MCU (U1) ---- */
#define UI_PIN_EXP_0_3   0   /* expansion header J13 pins 3-6 = GPIO0-3 */
#define UI_PIN_PRN_TX    4   /* printer UART1 TX (UART0 is the MCU link) */
#define UI_PIN_PRN_RX    5   /* printer UART1 RX */
#define UI_PIN_PRN_CTS   6   /* printer UART1 CTS */
#define UI_PIN_PRN_RTS   7   /* printer UART1 RTS */
#define UI_PIN_EXP_8_9   8   /* expansion header J13 pins 7-8 = GPIO8-9 (I2C0); pins 9/10 = GND/3V3 */
#define UI_PIN_NET_SWCLK 10  /* UI drives the NET MCU's SWD port: the UI firmware reflashes the NET MCU */
#define UI_PIN_NET_SWDIO 11
#define UI_PIN_TMDS_FIRST 12 /* HSTX: D0 12/13, CK 14/15, D2 16/17, D1 18/19 (see dvi_text.c) */
#define UI_PIN_SD_MISO   20  /* SPI0 */
#define UI_PIN_SD_CS     21
#define UI_PIN_SD_SCK    22
#define UI_PIN_SD_MOSI   23
#define UI_PIN_SD_DET    24  /* card detect switch to GND, needs pull-up */
#define UI_PIN_LED       25
#define UI_PIN_BUZZER    26  /* piezo via 100R: drive with PWM (~4 kHz resonance) */
#define UI_PIN_PANEL_EN  27  /* TPS22917 panel 5 V switch, high = on (100k pull-down) */
#define UI_PIN_LINK_TX   28  /* UART0 TX to NET RX 29 */
#define UI_PIN_LINK_RX   29

/* ---- NET MCU (U2) ---- */
#define NET_PIN_ROW_FIRST 0  /* ROW0-5 = GPIO0-5: drive low one at a time */
#define NET_PIN_COL_FIRST 6  /* COL0-13 = GPIO6-19: inputs with pull-ups (diode anode on the column side) */
#define NET_PIN_I2C_SDA  20  /* I2C0 to BQ25798 (address 0x6B) */
#define NET_PIN_I2C_SCL  21
#define NET_PIN_CHG_INT  22  /* BQ25798 INT, open drain, active low */
#define NET_PIN_WL_ON    23  /* RM2 WL_ON + BT_ON */
#define NET_PIN_WL_DATA  24  /* RM2 gSPI data (DIN direct, DOUT via 470R, IRQ via 10k) */
#define NET_PIN_WL_CS    25
#define NET_PIN_WL_CLK   26  /* differs from the Pico 2 W (29): override CYW43_DEFAULT_PIN_WL_CLOCK */
#define NET_PIN_CHG_STAT 27  /* BQ25798 STAT */
#define NET_PIN_LINK_TX  28  /* to UI RX 29 */
#define NET_PIN_LINK_RX  29

#endif
