#ifndef COMP_LINK_H
#define COMP_LINK_H

#include <stdint.h>

/* Inter-MCU UART protocol: [0xA5][type][len][payload...][crc8] */
#define LINK_SYNC 0xA5
#define LINK_MAX_PAYLOAD 64

typedef enum {
    MSG_KEY_EVENT = 0x01,   /* NET -> UI: payload = key_event_t */
    MSG_BATTERY = 0x02,     /* NET -> UI: payload = battery_t */
    MSG_NET_STATUS = 0x03,  /* NET -> UI: Wi-Fi state */
    MSG_NET_DATA = 0x04,    /* both ways: app-level network payload */
} link_msg_t;

typedef struct {
    uint8_t keycode;
    uint8_t pressed;  /* 1 = down, 0 = up */
} key_event_t;

typedef struct {
    uint16_t millivolts;
    uint8_t percent;
    uint8_t charging;
} battery_t;

#endif
