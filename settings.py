__author__ = 'Leenix'

UNIT_CLASS = "stalker"
SERIAL_PORT = "COM6"
BAUD_RATE = 57600

OUTPUT_FILENAME = "logOutput.csv"

XBEE_ESCAPE_CHAR = 0x7D
XBEE_START_FRAME_CHAR = '\x7E'

KEY_MAP = {
    "air_temp": "field1",
    "wall_temp": "field2",
    "surface_temp": "field3",
    "case_temp": "field4",
    "humidity": "field5",
    "illuminance": "field6",
    "sound": "field7",
    "battery": "field8"
}

CHANNEL_MAP = {
    "stalker8": "GKNS6EINCZ9T5YOU",
}
