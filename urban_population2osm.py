#!/usr/bin/env python3
# -*- coding: utf8

# urban_population2osm
# Extracts urban settlements with population numbers from SSB and updates OSM.
# Produces OSM file ready for additional edits before upload, filename 'tettsted_<year>.osm'
# Input CSV on: https://www.ssb.no/en/befolkning/statistikker/beftett.
# Usage: urban_population2osm.py <year> <CSV filename>


import json
import html
import sys
import csv
import urllib.request, urllib.parse, urllib.error
from io import StringIO, TextIOWrapper
from xml.etree import ElementTree as ET


version = "0.3.0"

request_header = { "User-Agent": "osm-no/population2osm" }

# SSB tables used before 2021
ssb_table = {
	'2019': '407816',
	'2020': '433415'
}

update_date = "-01-01"  # Tag to OSM

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
		encoded_value = html.escape(value).strip()
		file.write ('    <tag k="' + key + '" v="' + encoded_value + '" />\n')



# Output message

def message (line):

	sys.stdout.write (line)
	sys.stdout.flush()



# Geocoding with SSR
# Search is within given municipality number

def ssr_search (query_text, query_municipality):

	query = "https://ws.geonorge.no/stedsnavn/v1/navn?sok=%s&knr=%s&utkoordsys=4258&treffPerSide=10&side=1" \
				% (urllib.parse.quote(query_text.replace("(","").replace(")","")), query_municipality)

	request = urllib.request.Request(query, headers=request_header)
	file = urllib.request.urlopen(request)
	result = json.load(file)
	file.close()

	if result['navn']:

		# Return the first acceptable result
		for place in result['navn']:
			if (place['navneobjekttype'].lower().strip() in ssr_types) and \
					(ssr_types[ place['navneobjekttype'].lower().strip() ] in ['Bebyggelse', 'OffentligAdministrasjon', 'Kultur']):
				result_type = place['navneobjekttype'].strip()
				return (place['representasjonspunkt']['nord'], place['representasjonspunkt']['øst'], result_type)

		# All place types considered if no match above
		place = result['navn'][0]
		result_type = place['navneobjekttype'].strip()
		return (place['representasjonspunkt']['nord'], place['representasjonspunkt']['øst'], result_type)
	
	return None



# Add or update tag of OSM element
# Return True if tag was modified

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

	message ("\n*** Urban settlements ('tettsteder') population update ***\n")

	if len(sys.argv) == 3:
		update_year = sys.argv[1]
		update_date = update_year + update_date
		csv_filename = sys.argv[2]
	else:
		sys.exit("*** Please enter parameters 1) update year and 2) CSV file name from SSB\n")

	message ("Update date: %s\n" % update_date)


	# Load SSR name categories from Github

	ssr_filename = 'https://raw.githubusercontent.com/osmno/geocode2osm/master/navnetyper.json'
	file = urllib.request.urlopen(ssr_filename)
	name_codes = json.load(file)
	file.close()

	ssr_types = {}
	for main_group in name_codes['navnetypeHovedgrupper']:
		for group in main_group['navnetypeGrupper']:
			for name_type in group['navnetyper']:
				ssr_types[ name_type['visningsnavn'].strip().lower() ] = main_group['navn']


	# Load existing urban areas from OSM

	message ("\nLoad existing urban places from OSM ... ")

	query = '[out:xml][timeout:90];(area["name"="Norge"]["type"="boundary"];)->.a;(nwr["ref:ssb_tettsted"](area.a););(._;>;);out meta;'
	request = urllib.request.Request("https://overpass-api.de/api/interpreter?data=" + urllib.parse.quote(query), headers=request_header)
	file = urllib.request.urlopen(request)
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
				message ("\n\tDuplicate 'ref:ssb_tettsted': %s  " % ref)
				duplicate = True
			else:
				osm_settlements[ref] = settlement
				osm_count += 1

	message ("%s settlements\n" % osm_count)

	if duplicate:
		sys.exit ("\n*** Please remove duplicates from OSM before continuing\n")


	# Load SSB population data

	message ("\nLoad SSB population data ... ")

#	Earlier code used for 2019/2020:
#	file = urllib.request.urlopen("https://www.ssb.no/eksport/tabell.csv?key=%s" % ssb_table[ update_year ])
#	table_string = TextIOWrapper(file, "utf-8").read().replace("\r", "\n").replace("\xa0", "")

	file = open(csv_filename)
	table_string = file.read()

	ssb_table = csv.DictReader(StringIO(table_string), fieldnames=['settlement','municipality','population_total','population_municipality'], delimiter=";")

	ssb_settlements = {}
	ssb_count = 0
	row_count = 0

	for row in ssb_table:
		row_count += 1
		if row_count > 2:

			if row['settlement']:
				ref = row['settlement'][0:4]
				ssb_count += 1
				name = row['settlement'][5:].replace(" i alt", "")
				if "(" in name:
					name = name[0:name.find("(")].strip()
				ssb_settlements[ref] = {
					'name': name,
					'population': row['population_total'].replace(" ",""),
					'municipalities': []
				}

				if row['municipality']:
					municipality = {
						'ref': row['municipality'][0:4],
						'name': row['municipality'][5:],
						'population': row['population_total'].replace(" ", "")
					}
					ssb_settlements[ref]['municipalities'].append(municipality)

			else:
				municipality = {
					'ref': row['municipality'][0:4],
					'name': row['municipality'][5:],
					'population': row['population_municipality'].replace(" ", "")
				}
				ssb_settlements[ref]['municipalities'].append(municipality)	

	file.close()
	message ("%i urban settlements\n" % ssb_count)


	# Split settlements into subareas according to dict

	message ("\nMatch SSB and OSM settlements ...\n")

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
			message ("\tUrban settlement %s in split table not used by SSB\n" % settlement_ref)

	for settlement_ref in osm_settlements:
		if settlement_ref not in ssb_settlements:
			message ("\tUrban settlement %s in OSM not used by SSB\n" % settlement_ref)


	# Produce data

	message ("\nProducing data...\n")

	node_id = -1000
	update_count = 0
	new_count = 0
	notfound_count = 0

	for settlement_ref, settlement in iter(ssb_settlements.items()):
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
					result = ssr_search(municipality['name'] + "*", municipality['ref'])
					if result != None:
						municipality_name = municipality['name']
						only_municipality = True
						break		

			if result != None:
				latitude = str(result[0])
				longitude = str(result[1])
				result_type = result[2]
				message ("\t%s [%s] -> %s, %s" % (settlement['name'], settlement['population'], result_type, municipality_name))
				if only_municipality:
					message (" -> *** LOCATION NOT FOUND")
					notfound_count += 1
				message ("\n")
			else:
				message ("\t%s [%s] -> *** LOCATION NOT FOUND\n" % (settlement['name'], settlement['population']))
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

	filename = "tettsted_%s.osm" % update_year
	osm_root.set("generator", "population2osm v%s" % version)
	osm_root.set("upload", "false")
	osm_tree.write(filename, encoding="utf-8", method="xml", xml_declaration=True)

	message ("\nSaving ... %i urban settlements saved in file '%s'\n" % (ssb_count, filename))
	message ("\tAlready correct: %i\n" % (ssb_count - update_count - new_count))
	message ("\tUpdated:         %i\n" % update_count)
	message ("\tNew:             %i\n" % new_count)
	message ("\tNot used:        %i\n" % (osm_count - ssb_count + new_count))
	message ("\tCheck location:  %i\n\n" % notfound_count)
