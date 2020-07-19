#!/usr/bin/python3

import csv
import datetime
import math
import operator
import os
import threading
import time

# Map center in decimal degree format (sign is cardinality).
# This default is more or less the center of Phoenix (at Sky Harbor/PHX airport).
LATITUDE = 33.435
LONGITUDE = -112.00833334

# Change as needed.
DIRE_WOLF_CSV_LOG_FILE_PATH = '/home/pi/aprs.log'
NAVIT_POI_FILE_PATH = '/home/pi/.navit/aprs_poi.txt'
NAVIT_POI_ACTIVE_ICON_FILE_PATH = '/home/pi/dire_wolf_to_navit/icons/gprs_active.png'
NAVIT_POI_INACTIVE_ICON_FILE_PATH = '/home/pi/dire_wolf_to_navit/icons/gprs_inactive.png'

# How often to transfer data from Dire Wolf to dictionary to Navit.
DIRE_WOLF_TO_NAVIT_REFRESH_RATE_IN_SECONDS = 30

# If set to False, then provide some other means to eventually clear the log so that it doesn't grow indefinitely.
# For example, logrotate or a cron job...
# Anachron replaces standard cron and is better for systems that don't run continuously, as it can "catch up" to the current date.
# sudo apt-get update && sudo apt-get -y install anacron && time sudo apt-get clean
# crontab -e
# Once a day...
# 0 0 * * * /usr/bin/truncate -s 0 /home/pi/aprs.log
CLEAR_DIRE_WOLF_CSV_LOG_FILE_AFTER_READING = True

# We always show the source field, but the comment field is optional.
SHOW_COMMENT_FIELD = True

# Note that the actual rate of Navit's screen refresh also depends on Navit's refresh="#" config.
NAVIT_REFRESH_RATE_IN_SECONDS = 0.05

# How long before APRS entries in POI_DICTIONARY become inactive?
MINUTES_UNTIL_APRS_INACTIVE = 5

# How long before APRS entries in POI_DICTIONARY are removed?
MINUTES_UNTIL_APRS_REMOVED = 60

# You would only update these if Dire Wolf changed them.
DIRE_WOLF_CSV_FIELD_NAMES = ['chan', 'utime', 'isotime', 'source', 'heard', 'level', 'error', 'dti', 'name', 'symbol', 'latitude', 'longitude', 'speed', 'course', 'altitude', 'frequency', 'offset', 'tone', 'system', 'status', 'telemetry', 'comment']

# Used to manage duplicates and stale entries.
POI_DICTIONARY = {};

#
def iso_string_valid(iso_string):

	try:

		# fromisoformat() can't handle Z, so we have to swap it for its equivalent.
		datetime.datetime.fromisoformat(iso_string.replace('Z', '+00:00'))

	except: return False

	return True

#
def latitude_string_valid(latitude_string):

	try:

		return float(latitude_string) > -90 and float(latitude_string) < 90

	except: return False

#
def longitude_string_valid(longitude_string):

	try:

		return float(longitude_string) > -180 and float(longitude_string) < 180

	except: return False

# NMEA sentence checksum.
def get_checksum(sentence):

	#
	checksum = chr(0)

	#
	for c in sentence:

		#
		checksum = chr(ord(checksum) ^ ord(c))

	return '{0:02X}'.format(ord(checksum))

# NMEA format: ddmm.mmmmmm,c
# It's unclear how much precision is OK, but I'm capping it at six.
def convert_latitude_to_nmea_format(decimal_degree_latitude):

	#
	unsigned_decimal_degree = abs(decimal_degree_latitude)
	degrees = float(math.floor(unsigned_decimal_degree))
	minutes = unsigned_decimal_degree - degrees

	#
	cardinal = 'S' if decimal_degree_latitude < 0 else 'N'

	return '{0}{1:09.6f},{2}'.format(int(degrees), minutes * 60.0, cardinal)

# NMEA format: dddmm.mmmmmm,c
# It's unclear how much precision is OK, but I'm capping it at six.
def convert_longitude_to_nmea_format(decimal_degree_longitude):

	#
	unsigned_decimal_degree = abs(decimal_degree_longitude)
	degrees = float(math.floor(unsigned_decimal_degree))
	minutes = unsigned_decimal_degree - degrees

	#
	cardinal = 'W' if decimal_degree_longitude < 0 else 'E'

	return '{0}{1:09.6f},{2}'.format(int(degrees), minutes * 60.0, cardinal)

#
def get_mock_gps_location_in_nmea_gpgga_format():

	# Current time in NMEA GPGGA format.
	current_time = datetime.datetime.now().strftime('%H%M%S')

	#
	nmea_latitude = convert_latitude_to_nmea_format(LATITUDE)
	nmea_longitude = convert_longitude_to_nmea_format(LONGITUDE)

	# NMEA GPGGA format (without the checksum).
	nmea = f'GPGGA,{current_time},{nmea_latitude},{nmea_longitude},1,12,1.0,0.0,M,0.0,M,,'

	#
	checksum = get_checksum(nmea)

	return f'${nmea}*{checksum}'

#
def refresh_navit_poi_file_from_dictionary():

	# w+ means the file is created if it does not exist, otherwise it is truncated. The stream is positioned at the beginning of the file.
	with open(NAVIT_POI_FILE_PATH, 'w+', encoding = 'utf-8', errors = 'replace') as navit_poi_file:

		# Sorting by isotime is not necessary, but makes the navit_poi_file easier to follow and troubleshoot if necessary.
		sorted_poi_dictionary = sorted(POI_DICTIONARY.values(), key = lambda entry: entry['isotime'], reverse = True)

		#
		for entry in sorted_poi_dictionary:

			# The isotime field is in UTC. But fromisoformat() can't handle Z, so we have to swap it for its equivalent.
			then = datetime.datetime.fromisoformat(entry['isotime'].replace('Z', '+00:00'))

			# Get now in UTC. So we compare apples to apples. But datetime is idiotically timezone naive. So we have to set tzinfo manually!
			now = datetime.datetime.utcnow().replace(tzinfo = datetime.timezone.utc)

			# Simplify boolean for ternary.
			is_inactive = MINUTES_UNTIL_APRS_INACTIVE is not None and then + datetime.timedelta(minutes = MINUTES_UNTIL_APRS_INACTIVE) < now

			#
			icon_file_path = NAVIT_POI_INACTIVE_ICON_FILE_PATH if is_inactive else NAVIT_POI_ACTIVE_ICON_FILE_PATH

			# Simplify boolean for ternary.
			comment_is_not_empty = len(entry['comment'].strip()) > 0

			# This will either be an empty string, or a source, or a source with a comment (separated by an m-dash).
			comment = ' — ' + entry['comment'] if (SHOW_COMMENT_FIELD is True and comment_is_not_empty) else ''

			# Example: mg: -112.005000 33.261000 isotime="1212-12-12T12:12:12Z" type="poi_custom0" icon_src="/home/pi/dire_wolf_to_navit/icons/gprs_active.png" label="PHX"
			# The isotime attribute is ignored by Navit; it's only there to make navit_poi_file easier to follow and troubleshoot if necessary.
			navit_poi_file.write('mg: {0} {1} isotime="{2}" type="poi_custom0" icon_src="{3}" label="{4}"\n'.format(entry['longitude'], entry['latitude'], entry['isotime'], icon_file_path, entry['source'] + comment))

#
def refresh_dictionary_from_dire_wolf_csv_log_file():

	#
	if not os.path.exists(DIRE_WOLF_CSV_LOG_FILE_PATH): return

	#
	with open(DIRE_WOLF_CSV_LOG_FILE_PATH, 'r', newline = '', encoding = 'utf-8', errors = 'replace') as csv_file:

		#
		csv_reader = csv.DictReader(csv_file, fieldnames = DIRE_WOLF_CSV_FIELD_NAMES)

		#
		for row in csv_reader:

			# Simplify conditional.
			valid_source = row.get('source') is not None and row.get('source') != 'source' and not row.get('source').isspace()
			valid_latitude = row.get('latitude') is not None and latitude_string_valid(row.get('latitude'))
			valid_longitude = row.get('longitude') is not None and longitude_string_valid(row.get('latitude'))
			valid_isotime = row.get('isotime') is not None and iso_string_valid(row.get('isotime'))
			all_valid = valid_source and valid_latitude and valid_longitude and valid_isotime

			# Validate required fields.
			if not all_valid: continue

			#
			entry = {
				'isotime': row['isotime'],
				'source': row['source'],
				'latitude': row['latitude'],
				'longitude': row['longitude'],
				'comment': row['comment'].strip() if ('comment' in row and row['comment'] is not None) else ''
			}

			#
			POI_DICTIONARY[row['source']] = entry

	#
	if CLEAR_DIRE_WOLF_CSV_LOG_FILE_AFTER_READING is True:

		# Clear the file of content.
		with open(DIRE_WOLF_CSV_LOG_FILE_PATH, 'w', encoding = 'utf-8'): pass

#
def remove_stale_entries_from_dictionary():

	#
	for key in list(POI_DICTIONARY.keys()):

		#
		entry = POI_DICTIONARY[key]

		# The isotime field is in UTC. But fromisoformat() can't handle Z, so we have to swap it for its equivalent.
		then = datetime.datetime.fromisoformat(entry['isotime'].replace('Z', '+00:00'))

		# Get now in UTC. So we compare apples to apples. But datetime is idiotically timezone naive. So we have to set tzinfo manually!
		now = datetime.datetime.utcnow().replace(tzinfo = datetime.timezone.utc)

		#
		if MINUTES_UNTIL_APRS_REMOVED is not None and then + datetime.timedelta(minutes = MINUTES_UNTIL_APRS_REMOVED) < now:

			#
			del POI_DICTIONARY[key]

# This runs in its own thread.
def dire_wolf_to_navit():

	# Loop forever.
	while (not time.sleep(DIRE_WOLF_TO_NAVIT_REFRESH_RATE_IN_SECONDS)):

		#
		refresh_dictionary_from_dire_wolf_csv_log_file()
		remove_stale_entries_from_dictionary()
		refresh_navit_poi_file_from_dictionary()

if __name__ == "__main__":

	# thread.daemon = True ensures the thread dies when the app does.
	thread = threading.Thread(target = dire_wolf_to_navit)
	thread.daemon = True
	thread.start()

	# This loop, in combination with Navit config such as...
	# 	<vehicle ... source="pipe:/home/pi/dire_wolf_to_navit/src/dire_wolf_to_navit.py" follow="1">
	# ...is what forces Navit to reread the POI file referenced by NAVIT_POI_FILE_PATH and refresh the screen.
	# The "source" and "follow" attributes are critical.
	# The downside to this technique is that the user will not be able to scroll around the map for long, 
	# as the "follow" attribute will recenter the map on this app's LATITUDE and LONGITUDE config.
	# Why mock the location? Why not just use a GPS? Because slight changes in GPS readings cause the map to shift undesirably.
	# Note the following Navit config is required to actually center on the location without an offset...
	# 	<navit ... radius="0">
	while (not time.sleep(NAVIT_REFRESH_RATE_IN_SECONDS)):

		# This output gets piped into Navit.
		print(get_mock_gps_location_in_nmea_gpgga_format())
