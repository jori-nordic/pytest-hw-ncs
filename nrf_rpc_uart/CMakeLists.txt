zephyr_include_directories(include)

zephyr_library()

zephyr_library_sources_ifdef(CONFIG_NRF_RPC_UART src/nrf_rpc_uart.c)
