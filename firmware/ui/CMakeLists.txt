add_executable(comp_ui main.c dvi_text.c font8x16.c)
target_link_libraries(comp_ui pico_stdlib hardware_dma hardware_irq comp_common
    pico_bootsel_via_double_reset)   # double-tap the pinhole RESET -> USB update drive
# The UI MCU is an RP2350B (QFN-80, GPIO0-47: eMMC on GPIO30-36); the NET MCU stays RP2350A.
target_compile_definitions(comp_ui PRIVATE PICO_RP2350A=0)
pico_enable_stdio_usb(comp_ui 1)
pico_add_extra_outputs(comp_ui)
