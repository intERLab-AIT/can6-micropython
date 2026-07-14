make BOARD=CANARIN_V5 
esptool.py --chip esp32 merge_bin  -o build-CANARIN_V5/can5-test.bin  --flash_mode dio  --flash_size 4MB  --flash_freq 40m   0x1000 build-CANARIN_V5/bootloader/bootloader.bin   0x8000 build-CANARIN_V5/partition_table/partition-table.bin   0x10000 build-CANARIN_V5/micropython.bin

echo
echo
echo "Unified firmware build-CANARIN_V5/can5-test.bin ready!"
echo
echo "Use the following command to flash..."
echo "esptool.py -b 460800 write_flash 0x0 build-CANARIN_V5/can5-test.bin"

