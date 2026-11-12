add_executable(comp_ui main.c dvi_text.c font8x16.c)
target_link_libraries(comp_ui pico_stdlib hardware_dma hardware_irq comp_common)
pico_enable_stdio_usb(comp_ui 1)
pico_add_extra_outputs(comp_ui)
