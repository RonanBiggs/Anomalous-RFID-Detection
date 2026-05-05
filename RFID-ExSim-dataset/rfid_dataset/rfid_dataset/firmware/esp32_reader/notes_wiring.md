# WIRING ESP32 ↔ MFRC522 (x2 configuration)

## Reader A
| MFRC522 Pin | ESP32 (Reader A) | Description |
|--------------|-----------------|--------------|
| SDA (SS)     | GPIO5           | Slave Select |
| SCK          | GPIO12          | SPI Clock |
| MOSI         | GPIO14          | SPI MOSI |
| MISO         | GPIO27          | SPI MISO |
| RST          | GPIO25          | Reset |
| 3.3V         | 3.3V            | Alimentation |
| GND          | GND             | Masse |

## Reader B
| MFRC522 Pin | ESP32 (Reader B) | Description |
|--------------|-----------------|--------------|
| SDA (SS)     | GPIO17          | Slave Select |
| SCK          | GPIO18          | SPI Clock |
| MOSI         | GPIO23          | SPI MOSI |
| MISO         | GPIO19          | SPI MISO |
| RST          | GPIO16          | Reset |
| 3.3V         | 3.3V            | Alimentation |
| GND          | GND             | Masse |
