add_executable(comp_net main.c)
target_link_libraries(comp_net pico_stdlib comp_common)
pico_enable_stdio_usb(comp_net 1)
pico_add_extra_outputs(comp_net)
