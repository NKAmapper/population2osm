#!/usr/bin/env python
# -*- coding: utf8

# urban_population2osm
# Extracts urban settlements with population numbers from SSB and updates OSM.
# Produces OSM file ready for additional edits before upload.
# Input CSV on: https://www.ssb.no/en/befolkning/statistikker/beftett.


import json
import cgi
import sys
import time
import csv
import urllib
import urllib2
import re
from io import BytesIO
from xml.etree import ElementTree as ET


version = "0.2.0"

request_header = { "User-Agent": "osm-no/population2osm" }

ssb_table = "433415"  # for 2020 CSV table (2019: 407816)

update_date = "2020-01-01"  # Tag to OSM

source = "SSB - befolkning i tettstedet"  # Tag to OSM


# The dict below specifies how certain urban settlements will be devided into sub-areas
# Population assignment: 'all' - total population; 'part' - only population for sub-area (one line in SSB table)

area_splits = {
	'0022': {
		'3004': 'part', # Fredrikstad
		'3003': 'part', # Sarpsborg
	},
	'0801': {
		'0301':	'all',  # Oslo
		'3024': 'part',	# Bærum (Sandvika)
		'3025': 'part', # Asker
		'3030':	'part', # Lillestrøm
		'3029': 'part'  # Lørenskog
	},
	'3005': {
		'3807': 'part', # Skien
		'3806':	'part', # Porsgrunn
		'3813': 'part'  # Bamble (Stathelle)
	},
	'4522': {
		'1103': 'all',  # Stavanger
		'1108': 'part', # Sandnes
		'1124': 'part'  # Sola
	}
}


# Produce a tag for OSM file

def make_osm_line(key,value):

	global file

	if value:
		encoded_value = cgi.escape(value.encode('utf-8'),True)
		file.write ('    <tag k="' + key + '" v="' + encoded_value + '" />\n')


# Output message

def message (line):

	sys.stdout.write (line)
	sys.stdout.flush()


# Open file/api, try up to 5 times, each time with double sleep time

def try_urlopen (url):

	tries = 0
	while tries < 5:
		try:
			return urllib2.urlopen(url)

		except urllib2.HTTPError, e:
			if e.code in [429, 503, 504]:  # "Too many requests", "Service unavailable" or "Gateway timed out"
				if tries  == 0:
					message ("\n") 
				message ("\r\tRetry %i in %ss... " % (tries + 1, 5 * (2**tries)))
				time.sleep(5 * (2**tries))
				tries += 1
			else:
				message ("\n\nHTTP error %i: %s\n" % (e.code, e.reason))
				message ("%s\n" % url.get_full_url())
				sys.exit()

		except urllib2.URLError, e:  # Mostly "Connection reset by peer"
			if tries  == 0:
				message ("\n") 
			message ("\r\tRetry %i in %ss... " % (tries + 1, 5 * (2**tries)))
			time.sleep(5 * (2**tries))
			tries += 1
	
	message ("\n\nError: %s\n" % e.reason)
	message ("%s\n\n" % url.get_full_url())
	sys.exit()



# Geocoding with SSR

def ssr_search (query_text, query_municipality):

	query = "https://ws.geonorge.no/SKWS3Index/ssr/json/sok?navn=%s&epsgKode=4326&fylkeKommuneListe=%s&eksakteForst=true" \
				% (urllib.quote(query_text.replace("(","").replace(")","").encode('utf-8')), query_municipality)
	request = urllib2.Request(query, headers=request_header)
	file = try_urlopen(request)
	result = json.load(file)
	file.close()

	if "stedsnavn" in result:
		if isinstance(result['stedsnavn'], dict):  # Single result is not in a list
			result['stedsnavn'] = [ result['stedsnavn'] ]

		# Return the first acceptable result
		for place in result['stedsnavn']:
			if (place['navnetype'].lower().strip() in ssr_types) and \
					(ssr_types[ place['navnetype'].lower().strip() ] in ['Bebyggelse', 'OffentligAdministrasjon', 'Kultur']):
				result_type = place['navnetype'].strip()
				return (place['nord'], place['aust'], result_type)

		#2nd iteration: All place types
		for place in result['stedsnavn']:
			result_type = place['navnetype'].strip()
			return (place['nord'], place['aust'], result_type)
	
	return None


# Add or update tag of OSM element

def update_tag (element, key, value):

	tag = element.find("tag[@k='%s']" % key)
	if tag != None:
		if tag.attrib['v'] != value:
			tag.set("v", value)
		else:
			return False
	else:
		element.append(ET.Element("tag", k=key, v=value))

	element.set("action", "modify")
	return True



# Main program

if __name__ == '__main__':

	message ("\nUpdate population of urban settlements ('tettsteder') per %s\n\n" % update_date)

	# Load SSR name categories from Github

	ssr_filename = 'https://raw.githubusercontent.com/osmno/geocode2osm/master/navnetyper.json'
	file = urllib2.urlopen(ssr_filename)
	name_codes = json.load(file)
	file.close()

	ssr_types = {}
	for main_group in name_codes['navnetypeHovedgrupper']:
		for group in main_group['navnetypeGrupper']:
			for name_type in group['navnetyper']:
				ssr_types[ name_type['visningsnavn'].strip().lower() ] = main_group['navn']


	# Load existing urban areas from OSM

	message ("Load existing urban places from OSM ... ")

	query = '[out:xml][timeout:90];(area["name"="Norge"]["type"="boundary"];)->.a;(nwr["ref:ssb_tettsted"](area.a););(._;>;);out meta;'
	request = urllib2.Request("https://overpass-api.de/api/interpreter?data=" + urllib.quote(query), headers=request_header)
	file = urllib2.urlopen(request)
	osm_tree = ET.parse(file)
	osm_root = osm_tree.getroot()
	file.close()

	osm_settlements = {}
	osm_count = 0
	duplicate = False

	for settlement in osm_root:
		ref_tag = settlement.find("tag[@k='ref:ssb_tettsted']")
		if ref_tag != None:
			ref = ref_tag.attrib['v']
			if ref in osm_settlements:
				message ("\nDuplicate 'ref:ssb_tettsted': %s  " % ref)
				duplicate = True
			else:
				osm_settlements[ref] = settlement
				osm_count += 1

	message ("%s settlements\n" % osm_count)

	if duplicate:
		message ("Please remove duplicates from OSM before continuing\n")
		sys.exit()


	# Load SSB population data

	message ("Load SSB population data ... ")

	file = urllib2.urlopen("https://www.ssb.no/eksport/tabell.csv?key=%s" % ssb_table)
	table_string = file.read().replace("\r", "\n").replace("\xc2\xa0", "").decode("utf-8-sig").encode("utf-8")

	ssb_table = csv.DictReader(BytesIO(table_string), fieldnames=['settlement','municipality','population_total','population_municipality'], delimiter=";")

	ssb_settlements = {}
	ssb_count = 0
	row_count = 0

	for row in ssb_table:
		row_count += 1
		if row_count > 2:

			if row['settlement']:
				ref = row['settlement'][0:4]
				ssb_count += 1
				name = row['settlement'][5:].decode("utf-8").replace(" i alt", "")
				if "(" in name:
					name = name[0:name.find("(")].strip()
				ssb_settlements[ref] = {
					'name': name,
					'population': row['population_total'],
					'municipalities': []
				}

				if row['municipality']:
					municipality = {
						'ref': row['municipality'][0:4],
						'name': row['municipality'][5:].decode("utf-8"),
						'population': row['population_total']
					}
					ssb_settlements[ref]['municipalities'].append(municipality)

			else:
				municipality = {
					'ref': row['municipality'][0:4],
					'name': row['municipality'][5:].decode("utf-8"),
					'population': row['population_municipality']
				}
				ssb_settlements[ref]['municipalities'].append(municipality)		

	file.close()
	message ("%i urban settlements\n" % ssb_count)


	# Split settlements into subareas according to dict

	for settlement_ref in area_splits:
		if settlement_ref in ssb_settlements:

			settlement = ssb_settlements[settlement_ref]
			keep_settlement = False

			for municipality in settlement['municipalities']:
				if municipality['ref'] in area_splits[ settlement_ref ]:

					if area_splits[ settlement_ref ][ municipality['ref'] ] == "all":
						keep_settlement = True
					else:
						ref = settlement_ref + "-" + municipality['ref']
						ssb_settlements[ref] = {
							'name': municipality['name'],
							'population': municipality['population'],
							'municipalities': [ {
								'ref': municipality['ref'],
								'name': municipality['name'],
								'population': municipality['population']
							} ]
						}
						ssb_count += 1

			if not keep_settlement:
				del ssb_settlements[settlement_ref]
				ssb_count -= 1

		else:
			message ("Urban settlement %s in split table not used by SSB\n" % settlement_ref)

	for settlement_ref in osm_settlements:
		if settlement_ref not in ssb_settlements:
			message ("Urban settlement %s in OSM not used by SSB\n" % settlement_ref)


	# Produce data

	message ("\nProducing data...\n")

	node_id = -1000
	update_count = 0
	new_count = 0
	notfound_count = 0

	for settlement_ref, settlement in ssb_settlements.iteritems():
		if settlement_ref in osm_settlements:
			# Update settlement tags

			element = osm_settlements[settlement_ref]
			update1 = update_tag (element, "population", settlement['population'])
			update2 = update_tag (element, "population:date", update_date)
			update3 = update_tag (element, "source:population", source)

			if update1 or update2 or update3:
				update_count += 1

		else:
			# Geocode new settlement

			result = None
			only_municipality = False
		
			if "/" in settlement['name']:
				names = settlement['name'].split("/")
			else:
				names = settlement['name'].split("-")

			for municipality in settlement['municipalities']:
				for settlement_name in names:
					result = ssr_search(settlement_name, municipality['ref'])
					if result != None:
						municipality_name = municipality['name']
						break
				if result != None:
					break

			if result == None:
				for municipality in settlement['municipalities']:
					result = ssr_search(municipality['name'], municipality['ref'])
					if result != None:
						municipality_name = municipality['name']
						only_municipality = True
						break		

			if result != None:
				latitude = result[0]
				longitude = result[1]
				result_type = result[2]
				message ("%s %s -> %s, %s" % (settlement['name'], settlement['population'], result_type, municipality_name))
				if only_municipality:
					message (" -> LOCATION NOT FOUND")
					notfound_count += 1
				message ("\n")
			else:
				message ("%s %s -> LOCATION NOT FOUND\n" % (settlement['name'], settlement['population']))
				latitude = "0"
				longitude = "0"
				result_type = ""
				municipality_name = ""
				notfound_count += 1

			# Create new settlement node

			node_id -= 1
			node = ET.Element("node", id=str(node_id), action="modify", lat=latitude, lon=longitude)
			osm_root.append(node)
			node.append(ET.Element("tag", k="name", v=settlement['name']))
			node.append(ET.Element("tag", k="ref:ssb_tettsted", v=settlement_ref))
			node.append(ET.Element("tag", k="population", v=settlement['population']))
			node.append(ET.Element("tag", k="population:date", v=update_date))
			node.append(ET.Element("tag", k="source:population", v=source))
			node.append(ET.Element("tag", k="MUNICIPALITY", v=municipality_name))

			if len(settlement['municipalities']) > 1:
				sub_populations = []
				for municipality in settlement['municipalities']:
					sub_populations.append("%s (%s)" % (municipality['name'], municipality['population']))
				node.append(ET.Element("tag", k="SUBAREAS", v=";".join(sub_populations)))

			if result_type:
				node.append(ET.Element("tag", k="SSR", v=result_type))

			if only_municipality:
				node.append(ET.Element("tag", k="NOT_FOUND", v="yes"))

			new_count += 1


	# Produce OSM/XML file

	filename = "tettsted_%s.osm" % (update_date[:4])
	osm_root.set("generator", "population2osm v%s" % version)
	osm_root.set("upload", "false")
	osm_tree.write(filename, encoding="utf-8", method="xml", xml_declaration=True)

	message ("\n%i urban settlements saved in file '%s'\n" % (ssb_count, filename))
	message ("  Already correct: %i\n" % (ssb_count - update_count - new_count))
	message ("  Updated:         %i\n" % update_count)
	message ("  New:             %i\n" % new_count)
	message ("  Not used:        %i\n" % (osm_count - ssb_count + new_count))
	message ("  Check location:  %i\n\n" % notfound_count)

