#pragma once
#include <stdint.h>

/* 256-glyph CP437 8x16 font, one byte per row, MSB = leftmost pixel. */
extern const uint8_t font8x16[256][16];
