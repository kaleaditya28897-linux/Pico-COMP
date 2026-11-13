/*
 * Board header for the Pico-COMP main board (both MCUs). Based on boards/pico2.h, minus the Pico 2's
 * SMPS/VBUS/VSYS/LED pins, which are different signals here (see firmware/common/pins.h).
 * The RP2350 package is set per target: UI = RP2350B (PICO_RP2350A=0 in firmware/ui/CMakeLists.txt),
 * NET = RP2350A (default below). Both MCUs boot from a 16 MB W25Q128JV.
 */
// -----------------------------------------------------
// NOTE: THIS HEADER IS ALSO INCLUDED BY ASSEMBLER SO
//       SHOULD ONLY CONSIST OF PREPROCESSOR DIRECTIVES
// -----------------------------------------------------
#ifndef _BOARDS_PICO_COMP_H
#define _BOARDS_PICO_COMP_H

pico_board_cmake_set(PICO_PLATFORM, rp2350)

#define PICO_COMP

// --- RP2350 VARIANT (per target) ---
#ifndef PICO_RP2350A
#define PICO_RP2350A 1
#endif

// --- UART: the inter-MCU link (UART0 on GPIO28/29 on both MCUs) ---
#ifndef PICO_DEFAULT_UART
#define PICO_DEFAULT_UART 0
#endif
#ifndef PICO_DEFAULT_UART_TX_PIN
#define PICO_DEFAULT_UART_TX_PIN 28
#endif
#ifndef PICO_DEFAULT_UART_RX_PIN
#define PICO_DEFAULT_UART_RX_PIN 29
#endif

// --- I2C: NET MCU charger / USB-C controller bus ---
#ifndef PICO_DEFAULT_I2C
#define PICO_DEFAULT_I2C 0
#endif
#ifndef PICO_DEFAULT_I2C_SDA_PIN
#define PICO_DEFAULT_I2C_SDA_PIN 20
#endif
#ifndef PICO_DEFAULT_I2C_SCL_PIN
#define PICO_DEFAULT_I2C_SCL_PIN 21
#endif

// --- SPI: UI MCU microSD (SPI0) ---
#ifndef PICO_DEFAULT_SPI
#define PICO_DEFAULT_SPI 0
#endif
#ifndef PICO_DEFAULT_SPI_RX_PIN
#define PICO_DEFAULT_SPI_RX_PIN 20
#endif
#ifndef PICO_DEFAULT_SPI_CSN_PIN
#define PICO_DEFAULT_SPI_CSN_PIN 21
#endif
#ifndef PICO_DEFAULT_SPI_SCK_PIN
#define PICO_DEFAULT_SPI_SCK_PIN 22
#endif
#ifndef PICO_DEFAULT_SPI_TX_PIN
#define PICO_DEFAULT_SPI_TX_PIN 23
#endif

// no PICO_DEFAULT_LED_PIN: GPIO25 is the UI LED but the NET MCU's Wi-Fi chip select

// --- FLASH: W25Q128JV, 16 MB ---
#define PICO_BOOT_STAGE2_CHOOSE_W25Q080 1
#ifndef PICO_FLASH_SPI_CLKDIV
#define PICO_FLASH_SPI_CLKDIV 2
#endif
pico_board_cmake_set_default(PICO_FLASH_SIZE_BYTES, (16 * 1024 * 1024))
#ifndef PICO_FLASH_SIZE_BYTES
#define PICO_FLASH_SIZE_BYTES (16 * 1024 * 1024)
#endif

pico_board_cmake_set_default(PICO_RP2350_A2_SUPPORTED, 1)
#ifndef PICO_RP2350_A2_SUPPORTED
#define PICO_RP2350_A2_SUPPORTED 1
#endif

#endif
