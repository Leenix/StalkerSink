import datetime
from threading import Thread
from serial.serialutil import SerialException
import serial
import struct
import logging
from ThingspeakChannel import *
from Queue import Queue
import time

__author__ = 'Leenix'

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

processor_queue = Queue()
upload_queue = Queue()

try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE)

except SerialException:
    logger.critical("Serial port cannot be opened :(")


def read_xbee():
    """
    Read the next byte from the XBee
    Escapes are performed for API=2

    :rtype : char
    :return: Received byte from the Xbee
    """
    c = ord(ser.read())

    # If the received character is an escape flag, the next character needs to be escaped
    if c == XBEE_ESCAPE_CHAR:
        c = ord(ser.read())
        c ^= 0x20

    return int(c)


def read_xbee_packet():
    """
    Read the data payload in from the XBee.
    This method is ugly as sin, but the python XBee library doesn't seem to support
    some of the newer packet types.

    :return: Data string of the packet in hex format.
    """

    # Wait for a start-of-frame character
    c = ser.read()
    while c != XBEE_START_FRAME_CHAR:
        c = ser.read()

    # Length
    length = read_xbee() * 256
    length += read_xbee()
    logger.debug("Length: {}".format(length))
    remaining_packet_bytes = length

    # Frame Type
    frame_type = format(read_xbee(), '02X')
    logger.debug("Frame Type: {}".format(frame_type))
    remaining_packet_bytes -= 1


    # Address
    address = ""
    for x in range(0, 8):
        address += format(read_xbee(), '02X')
        remaining_packet_bytes -= 1

    logger.debug("Address: {}".format(address))

    short_address = ""
    for x in range(0, 2):
        short_address += format(read_xbee(), '02X')
        remaining_packet_bytes -= 1

    logger.debug("Short Address: {}".format(short_address))

    # Receive Options
    receive_options = format(read_xbee(), '02X')
    remaining_packet_bytes -= 1
    logger.debug("Receive Options: {}".format(receive_options))

    # Data
    data = ""
    while remaining_packet_bytes > 0:
        c = chr(read_xbee())
        data += c
        remaining_packet_bytes -= 1

    logger.debug("Received packet: {}".format(data))
    logger.debug("Packet length: {}".format(len(data)))

    # Checksum
    checksum = hex(read_xbee())
    logger.debug("Checksum: {}".format(checksum))

    return data


def total_seconds(deltatime):
    """
    Convert the date into the total number of seconds since the epoch
    :param deltatime: Date object to be converted
    :return: Total number of seconds from epoch to date.
    """
    return (deltatime.microseconds + (deltatime.seconds + deltatime.days * 24 * 3600) * 10 ** 6) / 10 ** 6


def process_stalker_packet(data):
    """
    Convert the raw Stalker packet into a readable format.

    :param data: Stalker packet as raw byte string
    :return: Data in dictionary format
    """

    offset = total_seconds((datetime.datetime(2000, 1, 1, 0, 0, 0, 0) - datetime.datetime(1970, 1, 1, 0, 0, 0, 0)))

    station_id, ts, air_temp, wall_temp, surface_temp, case_temp, humidity, lux, sound, current, \
    battery_percent = struct.unpack(">BIHHHHHHHHBx", data)
    ts_time = datetime.datetime.utcfromtimestamp(ts + offset).strftime("%Y-%m-%d %H:%M")

    new_entry = {
        'id': UNIT_CLASS + str(station_id),
        'timestamp': ts_time,
        'air_temp': float(air_temp) / 100,
        'wall_temp': float(wall_temp) / 100,
        'surface_temp': float(surface_temp) / 100,
        'case_temp': float(case_temp) / 100,
        'humidity': float(humidity) / 100,
        'illuminance': lux,
        'sound': sound,
        'current': current,
        'battery': battery_percent
    }

    logger.info("Received Data: {}".format(new_entry))
    return new_entry


def write_entry_to_file(entry):
    try:
        f = open(OUTPUT_FILENAME, 'ab')
        f.write(str(entry))
        f.write('\n')
        f.close()

    except SystemError:
        logger.error("File cannot be opened. It may be read-only")


def read_loop():
    """
    Serial reading loop.
    Gather incoming packets by monitoring the serial stream.
    The raw transactions are placed in the processor queue.

    !Blocking method - should not be run in the main thread
    :return:
    """
    while True:
        data_string = read_xbee_packet()
        processor_queue.put(data_string)


def process_loop():
    """
    Processing loop for raw data packets in the process queue.
    Packets are transformed into a readable dictionary format and placed in the upload queue.
    The readable result of the transform is also backed up to a file.

    !Blocking method - should not be run in the main thread
    :return:
    """
    while True:
        raw_entry = processor_queue.get()
        processed_entry = process_stalker_packet(raw_entry)
        processor_queue.task_done()

        write_entry_to_file(processed_entry)
        upload_queue.put(processed_entry)


def upload_loop():
    """
    Uploads packets in the upload queue to Thingspeak.
    Packets can only be uploaded every 15 seconds due to Thingspeak restrictions.
    !Blocking method - should not be run in the main thread


    :return:
    """
    while True:
        processed_entry = upload_queue.get()
        thingspeak_packet = ThingspeakChannel.map_entry(processed_entry)
        ThingspeakChannel.update(thingspeak_packet)
        upload_queue.task_done()

        time.sleep(15)


if __name__ == '__main__':

    read_thread = Thread(target=read_loop, name="reader")
    process_thread = Thread(target=process_loop, name="processor")
    upload_thread = Thread(target=upload_loop, name="uploader")

    read_thread.start()
    process_thread.start()
    upload_thread.start()

    while True:
        try:
            pass

        except KeyboardInterrupt:
            break

    ser.close()



