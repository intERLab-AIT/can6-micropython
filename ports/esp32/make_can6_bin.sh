make BOARD=CANARIN_V6

esptool.py --chip esp32s3 merge_bin -o build-CANARIN_V6/can6-test.bin --flash_mode dio --flash_size 8MB --flash_freq 80m 0x0 build-CANARIN_V6/bootloader/bootloader.bin 0x8000 build-CANARIN_V6/partition_table/partition-table.bin 0x10000 build-CANARIN_V6/micropython.bin

echo
echo
echo "Unified firmware build-CANARIN_V6/can6-test.bin ready!"
echo
echo "Use the following command to flash..."
echo "esptool.py --chip esp32s3  -b 460800 write_flash 0x0 build-CANARIN_V6/can6-test.bin"

