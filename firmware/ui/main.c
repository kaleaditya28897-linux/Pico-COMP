#include <stdio.h>
#include "pico/stdlib.h"
#include "dvi_text.h"
#include "link.h"

int main(void) {
    stdio_init_all();
    dvi_init(DVI_SCHEME_AMBER);

    dvi_puts(0, 0, " PICO-COMP  Model 100 for the 21st century ", DVI_INVERSE);
    dvi_puts(2, 3, "Pico-COMP ready.", DVI_BRIGHT);
    dvi_puts(2, 5, "1) TEXT   2) TODO   3) SCHEDULER   4) BASIC", DVI_NORMAL);
    dvi_puts(2, 7, "CP437: \xb0\xb1\xb2\xdb \xda\xc4\xc4\xbf \xb3  \xb3 \xc0\xc4\xc4\xd9", DVI_DIM);
    for (int i = 0; i < 16; i++)
        dvi_puts(2 + i * 3, 10, "\xdb\xdb", DVI_ATTR(i, 0));

    for (;;) {
        printf("comp_ui alive\n");
        sleep_ms(1000);
    }
}
