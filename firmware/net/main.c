#include <stdio.h>
#include "pico/stdlib.h"
#include "link.h"

int main(void) {
    stdio_init_all();
    for (;;) {
        printf("comp_net alive\n");
        sleep_ms(1000);
    }
}
