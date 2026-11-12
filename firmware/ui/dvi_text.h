#pragma once
#include <stdint.h>

/* 640x480@60 DVI over HSTX (GPIO12-19), 8x16 font -> 80x30 text cells. */
#define DVI_COLS 80
#define DVI_ROWS 30

/* Attribute byte: high nibble = background, low nibble = foreground.
 * Each nibble indexes a 16-step intensity ramp of the active colour scheme
 * (0 = black, 15 = full brightness). */
#define DVI_ATTR(fg, bg) ((uint8_t)(((bg) << 4) | (fg)))
#define DVI_NORMAL  DVI_ATTR(11, 0)
#define DVI_BRIGHT  DVI_ATTR(15, 0)
#define DVI_DIM     DVI_ATTR(6, 0)
#define DVI_INVERSE DVI_ATTR(0, 11)

typedef enum { DVI_SCHEME_AMBER, DVI_SCHEME_GREEN, DVI_SCHEME_WHITE } dvi_scheme_t;

void dvi_init(dvi_scheme_t scheme);
void dvi_set_scheme(dvi_scheme_t scheme);
void dvi_clear(uint8_t attr);
void dvi_putc(int x, int y, uint8_t ch, uint8_t attr);
void dvi_puts(int x, int y, const char *s, uint8_t attr);
