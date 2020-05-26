#!/usr/bin/env python
# -*- coding: utf8

# population2osm
# Extracts most recent quarterly population numbers from SSB and produces OSM file for import/update of Norwegian municipalities, counties and country
# Usage: population2osm (no parameters)


import sys
import json
import urllib
import urllib2
from xml.etree import ElementTree as ET


version = "0.3.0"

request_header = { "User-Agent": "osm-no/population2osm" }

quarter_dates = {
	'1': '-04-01',
	'2': '-07-01',
	'3': '-10-01',
	'4': '-01-01'
}



# Output message

def message (line):

	sys.stdout.write (line)
	sys.stdout.flush()



# Load SSB data for administrative entities (municipality, county or country)
# Parameter api_ref is the predefined SSB query at https://data.ssb.no/api/v0/dataset/
# Returns dict with entity name and population + record date of population numbers

def load_ssb (api_ref):

	# Load predefined data from SSB api

	request = urllib2.Request("http://data.ssb.no/api/v0/dataset/%s.json?lang=no" % api_ref, headers=request_header)
	file = urllib2.urlopen(request)
	ssb_data = json.load(file)
	file.close()

	# Determine index in list of population values from SSB

	entity_index = ssb_data['dataset']['dimension']['Region']['category']['index']
	data_entries = len(ssb_data['dataset']['dimension']['ContentsCode']['category']['index'])
	data_position = ssb_data['dataset']['dimension']['ContentsCode']['category']['index']['Folketallet11']

	# Build dict with entity names and population

	entities = {}

	for entity_id, entity_position in entity_index.iteritems():
		entities[entity_id] = {
			'name': ssb_data['dataset']['dimension']['Region']['category']['label'][entity_id],
			'population': str(ssb_data['dataset']['value'][ entity_position * data_entries + data_position ])
		}

	# Determine record date of population numbers

	quarter = ssb_data['dataset']['dimension']['Tid']['category']['index'].keys()[0]  # Format: 2020K1
	
	if quarter[-1] == "4":
		date = str(int(quarter[:4]) + 1)
	else:
		date = quarter[:4]
	date += quarter_dates[ quarter[-1] ]  # Add month and day

	return entities, date



# Main program

if __name__ == '__main__':

	message ("\nQuarterly update population of Norwegian municipalities, counties and country\n\n")

	# Load all SSB population data

	country, country_date = load_ssb('1104')
	message ("Norway population: %s\n" % country['0']['population'])

	counties, county_date = load_ssb('1102')
	message ("%i counties\n" % len(counties))
	del counties['03']  # Oslo updated as municipality
	if "21" in counties:
		del counties['21']  # Svalbard not updated

	municipalities, municipality_date = load_ssb('1108')
	message ("%i municipalites\n" % len(municipalities))

	message ("Population date: %s\n" % ", ".join(sorted(set([municipality_date, county_date, country_date]))))

	updates = 0


	# Load country from OSM
	# tree_osm/root_osm will contain the updated XML for final output
	# Note: There are two Norway relations in OSM. The full relation for the Kingdom of Norway including Svalbard is being updated.

	message ("\nLoading country from OSM...\n")

	query = '[out:xml][timeout:90];(relation["name"="Norge"]["type"="boundary"]["admin_level"="2"];);out meta;'
	request = urllib2.Request("https://overpass-api.de/api/interpreter?data=" + urllib.quote(query), headers=request_header)
	file = urllib2.urlopen(request)
	tree_osm = ET.parse(file)
	root_osm = tree_osm.getroot()
	file.close()

	# Update country population

	relation = root_osm.find("relation")
	population_tag = relation.find("tag[@k='population']")
	if population_tag != None:
		population = population_tag.attrib['v']
		if population != country['0']['population']:
			population_tag.set("v", country['0']['population'])
			relation.set("action", "modify")
			updates += 1

	else:
		relation.append(ET.Element("tag", k="population", v=country['0']['population']))
		relation.set("action", "modify")
		updates += 1

	# Add record date

	date_tag = relation.find("tag[@k='population:date']")
	if date_tag != None:
		old_date = date_tag.attrib['v']
		if old_date != country_date:
			date_tag.set("v", country_date)
			relation.set("action", "modify")
	else:
		relation.append(ET.Element("tag", k="population:date", v=country_date))
		relation.set("action", "modify")		


	# Load all counties from OSM

	message ("\nLoading counties from OSM...\n")

	query = '[out:xml][timeout:90];(area["name"="Norge"]["type"="boundary"];)->.a;(relation["place"="county"](area.a););out meta;'
	request = urllib2.Request("https://overpass-api.de/api/interpreter?data=" + urllib.quote(query), headers=request_header)
	file = urllib2.urlopen(request)
	tree = ET.parse(file)
	root = tree.getroot()
	file.close()

	# Loop counties and update population

	for relation in root.iter("relation"):
		ref_tag = relation.find("tag[@k='ref']")
		if ref_tag != None:
			ref = ref_tag.attrib['v']
			if ref in counties:

				population_tag = relation.find("tag[@k='population']")
				if population_tag != None:
					population = population_tag.attrib['v']
					if population != counties[ref]['population']:
						population_tag.set("v", counties[ref]['population'])
						relation.set("action", "modify")
						updates += 1
				else:
					relation.append(ET.Element("tag", k="population", v=counties[ref]['population']))
					relation.set("action", "modify")
					updates += 1

				date_tag = relation.find("tag[@k='population:date']")
				if date_tag != None:
					old_date = date_tag.attrib['v']
					if old_date != county_date:
						date_tag.set("v", county_date)
						relation.set("action", "modify")
				else:
					relation.append(ET.Element("tag", k="population:date", v=county_date))
					relation.set("action", "modify")

				del counties[ref]
			else:
				message ("County ref %s not found in SSB table\n" % ref)

		root_osm.append(relation)

	for ref, county in counties.iteritems():
		message ("County %s %s not found in OSM\n" % (ref, county['name']))


	# Load all municipalities from OSM

	message ("\nLoading municipalities from OSM...\n")

	query = '[out:xml][timeout:90];(area["name"="Norge"]["type"="boundary"];)->.a;(relation["place"="municipality"](area.a););out meta;'
	request = urllib2.Request("https://overpass-api.de/api/interpreter?data=" + urllib.quote(query), headers=request_header)
	file = urllib2.urlopen(request)
	tree = ET.parse(file)
	root = tree.getroot()
	file.close()

	# Loop municipalities and update population

	for relation in root.iter("relation"):
		ref_tag = relation.find("tag[@k='ref']")
		if ref_tag != None:
			ref = ref_tag.attrib['v']
			if ref in municipalities:

				population_tag = relation.find("tag[@k='population']")
				if population_tag != None:
					population = population_tag.attrib['v']
					if population != municipalities[ref]['population']:
						population_tag.set("v", municipalities[ref]['population'])
						relation.set("action", "modify")
						updates += 1
				else:
					relation.append(ET.Element("tag", k="population", v=municipalities[ref]['population']))
					relation.set("action", "modify")
					updates += 1

				date_tag = relation.find("tag[@k='population:date']")
				if date_tag != None:
					old_date = date_tag.attrib['v']
					if old_date != municipality_date:
						date_tag.set("v", municipality_date)
						relation.set("action", "modify")
				else:
					relation.append(ET.Element("tag", k="population:date", v=municipality_date))
					relation.set("action", "modify")

				del municipalities[ref]
			else:
				message ("Municipality ref %s not found in SSB table\n" % ref)

		root_osm.append(relation)

	for ref, municipality in municipalities.iteritems():
		message ("Municipality %s %s not found in OSM\n" % (ref, municipality['name']))


	# Produce output file

	filename = "Update_population.osm"

	message ("\nUpdated %i population tags\n" % updates)
	message ("Saving file '%s'\n\n" % filename)

	root_osm.set("generator", "population2osm v%s" % version)
	root_osm.set("upload", "false")
	tree_osm.write(filename, encoding='utf-8', method='xml', xml_declaration=True)
