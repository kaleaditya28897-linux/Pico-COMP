/* HSTX DVI text-mode driver. Scanlines are rendered from a character buffer
 * in the DMA IRQ, so no framebuffer is needed (80x30x2 = 4.8 KB of RAM).
 * HSTX/DMA setup is derived from raspberrypi/pico-examples
 * hstx/dvi_out_hstx_encoder (Copyright (c) 2024 Raspberry Pi, BSD-3-Clause). */
#include <string.h>
#include "hardware/dma.h"
#include "hardware/gpio.h"
#include "hardware/irq.h"
#include "hardware/structs/bus_ctrl.h"
#include "hardware/structs/hstx_ctrl.h"
#include "hardware/structs/hstx_fifo.h"
#include "dvi_text.h"
#include "font8x16.h"

#define TMDS_CTRL_00 0x354u
#define TMDS_CTRL_01 0x0abu
#define TMDS_CTRL_10 0x154u
#define TMDS_CTRL_11 0x2abu

#define SYNC_V0_H0 (TMDS_CTRL_00 | (TMDS_CTRL_00 << 10) | (TMDS_CTRL_00 << 20))
#define SYNC_V0_H1 (TMDS_CTRL_01 | (TMDS_CTRL_00 << 10) | (TMDS_CTRL_00 << 20))
#define SYNC_V1_H0 (TMDS_CTRL_10 | (TMDS_CTRL_00 << 10) | (TMDS_CTRL_00 << 20))
#define SYNC_V1_H1 (TMDS_CTRL_11 | (TMDS_CTRL_00 << 10) | (TMDS_CTRL_00 << 20))

#define H_FRONT_PORCH 16
#define H_SYNC_WIDTH  96
#define H_BACK_PORCH  48
#define H_ACTIVE      640
#define V_FRONT_PORCH 10
#define V_SYNC_WIDTH  2
#define V_BACK_PORCH  33
#define V_ACTIVE      480
#define V_TOTAL (V_FRONT_PORCH + V_SYNC_WIDTH + V_BACK_PORCH + V_ACTIVE)

#define HSTX_CMD_RAW_REPEAT (0x1u << 12)
#define HSTX_CMD_TMDS       (0x2u << 12)
#define HSTX_CMD_NOP        (0xfu << 12)

static uint32_t vblank_vsync_off[] = {
    HSTX_CMD_RAW_REPEAT | H_FRONT_PORCH, SYNC_V1_H1,
    HSTX_CMD_RAW_REPEAT | H_SYNC_WIDTH, SYNC_V1_H0,
    HSTX_CMD_RAW_REPEAT | (H_BACK_PORCH + H_ACTIVE), SYNC_V1_H1,
    HSTX_CMD_NOP
};
static uint32_t vblank_vsync_on[] = {
    HSTX_CMD_RAW_REPEAT | H_FRONT_PORCH, SYNC_V0_H1,
    HSTX_CMD_RAW_REPEAT | H_SYNC_WIDTH, SYNC_V0_H0,
    HSTX_CMD_RAW_REPEAT | (H_BACK_PORCH + H_ACTIVE), SYNC_V0_H1,
    HSTX_CMD_NOP
};
static uint32_t vactive_line[] = {
    HSTX_CMD_RAW_REPEAT | H_FRONT_PORCH, SYNC_V1_H1, HSTX_CMD_NOP,
    HSTX_CMD_RAW_REPEAT | H_SYNC_WIDTH, SYNC_V1_H0, HSTX_CMD_NOP,
    HSTX_CMD_RAW_REPEAT | H_BACK_PORCH, SYNC_V1_H1,
    HSTX_CMD_TMDS | H_ACTIVE
};

typedef struct { uint8_t ch, attr; } cell_t;

static cell_t cells[DVI_ROWS][DVI_COLS];
static uint8_t palette[16];                          /* intensity ramp, RGB332 */
static uint32_t nibble_mask[16];                     /* 4 pixels: 0xff where set */
static uint32_t linebuf[2][H_ACTIVE / 4] __attribute__((aligned(4)));

#define DMACH_PING 0
#define DMACH_PONG 1

static bool dma_pong;
static uint v_scanline = 2;
static bool cmdlist_posted;

/* Same bit layout as the pico-examples RGB332 TMDS expander configuration. */
static uint8_t rgb332(uint8_t r, uint8_t g, uint8_t b) {
    return (r & 0xc0) >> 6 | (g & 0xe0) >> 3 | (b & 0xe0);
}

void dvi_set_scheme(dvi_scheme_t scheme) {
    static const uint8_t rgb[3][3] = {
        [DVI_SCHEME_AMBER] = {255, 176, 0},
        [DVI_SCHEME_GREEN] = {51, 255, 51},
        [DVI_SCHEME_WHITE] = {255, 255, 255},
    };
    for (int i = 0; i < 16; i++)
        palette[i] = rgb332(rgb[scheme][0] * i / 15, rgb[scheme][1] * i / 15,
                            rgb[scheme][2] * i / 15);
}

static void __not_in_flash_func(render_line)(uint y) {
    const cell_t *row = cells[y >> 4];
    const uint glyph_row = y & 15;
    uint32_t *out = linebuf[y & 1];
    for (int x = 0; x < DVI_COLS; x++) {
        uint8_t g = font8x16[row[x].ch][glyph_row];
        uint32_t fg = palette[row[x].attr & 15] * 0x01010101u;
        uint32_t bg = palette[row[x].attr >> 4] * 0x01010101u;
        uint32_t m0 = nibble_mask[g >> 4], m1 = nibble_mask[g & 15];
        *out++ = (fg & m0) | (bg & ~m0);
        *out++ = (fg & m1) | (bg & ~m1);
    }
}

static void __scratch_x("") dma_irq_handler(void) {
    uint ch_num = dma_pong ? DMACH_PONG : DMACH_PING;
    dma_channel_hw_t *ch = &dma_hw->ch[ch_num];
    dma_hw->intr = 1u << ch_num;
    dma_pong = !dma_pong;

    if (v_scanline >= V_FRONT_PORCH && v_scanline < V_FRONT_PORCH + V_SYNC_WIDTH) {
        ch->read_addr = (uintptr_t)vblank_vsync_on;
        ch->transfer_count = count_of(vblank_vsync_on);
    } else if (v_scanline < V_FRONT_PORCH + V_SYNC_WIDTH + V_BACK_PORCH) {
        ch->read_addr = (uintptr_t)vblank_vsync_off;
        ch->transfer_count = count_of(vblank_vsync_off);
    } else if (!cmdlist_posted) {
        ch->read_addr = (uintptr_t)vactive_line;
        ch->transfer_count = count_of(vactive_line);
        cmdlist_posted = true;
    } else {
        uint y = v_scanline - (V_TOTAL - V_ACTIVE);
        render_line(y);
        ch->read_addr = (uintptr_t)linebuf[y & 1];
        ch->transfer_count = H_ACTIVE / 4;
        cmdlist_posted = false;
    }
    if (!cmdlist_posted)
        v_scanline = (v_scanline + 1) % V_TOTAL;
}

void dvi_clear(uint8_t attr) {
    for (int y = 0; y < DVI_ROWS; y++)
        for (int x = 0; x < DVI_COLS; x++)
            cells[y][x] = (cell_t){' ', attr};
}

void dvi_putc(int x, int y, uint8_t ch, uint8_t attr) {
    if ((unsigned)x < DVI_COLS && (unsigned)y < DVI_ROWS)
        cells[y][x] = (cell_t){ch, attr};
}

void dvi_puts(int x, int y, const char *s, uint8_t attr) {
    for (; *s; s++, x++)
        dvi_putc(x, y, (uint8_t)*s, attr);
}

void dvi_init(dvi_scheme_t scheme) {
    for (int n = 0; n < 16; n++) {
        uint32_t m = 0;
        for (int i = 0; i < 4; i++)
            if (n & (8 >> i))
                m |= 0xffu << (8 * i);
        nibble_mask[n] = m;
    }
    dvi_set_scheme(scheme);
    dvi_clear(DVI_NORMAL);

    hstx_ctrl_hw->expand_tmds =
        2  << HSTX_CTRL_EXPAND_TMDS_L2_NBITS_LSB |
        0  << HSTX_CTRL_EXPAND_TMDS_L2_ROT_LSB   |
        2  << HSTX_CTRL_EXPAND_TMDS_L1_NBITS_LSB |
        29 << HSTX_CTRL_EXPAND_TMDS_L1_ROT_LSB   |
        1  << HSTX_CTRL_EXPAND_TMDS_L0_NBITS_LSB |
        26 << HSTX_CTRL_EXPAND_TMDS_L0_ROT_LSB;
    hstx_ctrl_hw->expand_shift =
        4 << HSTX_CTRL_EXPAND_SHIFT_ENC_N_SHIFTS_LSB |
        8 << HSTX_CTRL_EXPAND_SHIFT_ENC_SHIFT_LSB |
        1 << HSTX_CTRL_EXPAND_SHIFT_RAW_N_SHIFTS_LSB |
        0 << HSTX_CTRL_EXPAND_SHIFT_RAW_SHIFT_LSB;
    hstx_ctrl_hw->csr = 0;
    hstx_ctrl_hw->csr =
        HSTX_CTRL_CSR_EXPAND_EN_BITS |
        5u << HSTX_CTRL_CSR_CLKDIV_LSB |
        5u << HSTX_CTRL_CSR_N_SHIFTS_LSB |
        2u << HSTX_CTRL_CSR_SHIFT_LSB |
        HSTX_CTRL_CSR_EN_BITS;

    /* GP12 D0+/GP13 D0-, GP14 CK+/GP15 CK-, GP16 D2+/GP17 D2-, GP18 D1+/GP19 D1- */
    hstx_ctrl_hw->bit[2] = HSTX_CTRL_BIT0_CLK_BITS;
    hstx_ctrl_hw->bit[3] = HSTX_CTRL_BIT0_CLK_BITS | HSTX_CTRL_BIT0_INV_BITS;
    static const int lane_to_output_bit[3] = {0, 6, 4};
    for (uint lane = 0; lane < 3; ++lane) {
        int bit = lane_to_output_bit[lane];
        uint32_t sel = (lane * 10) << HSTX_CTRL_BIT0_SEL_P_LSB |
                       (lane * 10 + 1) << HSTX_CTRL_BIT0_SEL_N_LSB;
        hstx_ctrl_hw->bit[bit] = sel;
        hstx_ctrl_hw->bit[bit + 1] = sel | HSTX_CTRL_BIT0_INV_BITS;
    }
    for (int i = 12; i <= 19; ++i)
        gpio_set_function(i, 0);

    for (uint n = DMACH_PING; n <= DMACH_PONG; n++) {
        dma_channel_config c = dma_channel_get_default_config(n);
        channel_config_set_chain_to(&c, n == DMACH_PING ? DMACH_PONG : DMACH_PING);
        channel_config_set_dreq(&c, DREQ_HSTX);
        dma_channel_configure(n, &c, &hstx_fifo_hw->fifo, vblank_vsync_off,
                              count_of(vblank_vsync_off), false);
    }
    dma_hw->ints0 = (1u << DMACH_PING) | (1u << DMACH_PONG);
    dma_hw->inte0 = (1u << DMACH_PING) | (1u << DMACH_PONG);
    irq_set_exclusive_handler(DMA_IRQ_0, dma_irq_handler);
    irq_set_enabled(DMA_IRQ_0, true);

    bus_ctrl_hw->priority = BUSCTRL_BUS_PRIORITY_DMA_W_BITS | BUSCTRL_BUS_PRIORITY_DMA_R_BITS;
    dma_channel_start(DMACH_PING);
}
