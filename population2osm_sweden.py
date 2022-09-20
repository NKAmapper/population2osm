#!/usr/bin/env python3
# -*- coding: utf8

# population2osm
# Extracts most recent quarterly population numbers from SCB and produces OSM file for import/update of Swedish municipalities, counties and country
# Usage: population2osm_sweden.py (no arguments)


import sys
import json
import urllib.parse
import urllib.request
from xml.etree import ElementTree as ET


version = "0.4.0"

request_header = { "User-Agent": "NKAmapper/population2osm" }



# Output message

def message (line):

	sys.stdout.write (line)
	sys.stdout.flush()



# Load SCB data for administrative entities (municipality, county or country)
# Parameter api_ref is the predefined SCB query at https://catalog.skl.se/rowstore/dataset/
# Returns dict with entity name and population + record date of population numbers

def load_municipalities():

	# Load predefined data from SCB api

	url = "https://catalog.skl.se/rowstore/dataset/b80d412c-9a81-4de3-a62c-724192295677?_limit=400"
	request = urllib.request.Request(url, headers=request_header)
	file = urllib.request.urlopen(request)
	data = json.load(file)
	file.close()

	# Determine record date of population numbers

	for key in data['results'][0].keys():
		if "folkmängd" in key:
			population_key = key
			date = "%i-01-01" % (int(key[-4:]) + 1)

	# Build dict with entity names and population

	entities = {
		'0': {
			'name': "Sweden",
			'population': 0
		}
	}

	for municipality in data['results']:
		population = int(municipality[ population_key ].replace(" ", ""))
		entities[ municipality['kommunkod'] ] = {
			'name': municipality['kommun'],
			'population': population
		}
		if municipality['länskod'] not in entities:
			entities[ municipality['länskod'] ] = {
				'name': municipality['län'],
				'population': 0
			}
		entities[ municipality['länskod'] ]['population'] += population
		entities[ '0' ]['population'] += population

	return entities, date



# Main program

if __name__ == '__main__':

	message ("\nAnnual update population of Swedish municipalities, counties and country\n\n")

	# Load all SCB population data

	entities, date = load_municipalities()
	message ("Population date: %s\n" % date)
	message ("Sweden population: %s\n" % entities['0']['population'])

	message ("Counties:\n")
	counties = 0
	for county_id, county in iter(entities.items()):
		if len(county_id) == 2:
			counties += 1
			message ("\t%-30s %7i\n" % (county['name'], county['population']))
	message ("%i counties\n" % counties)

	message ("Municipalities:\n")
	municipalities = 0
	for municipality_id, municipality in iter(entities.items()):
		if len(municipality_id) == 4:
			municipalities += 1
			message ("\t%-30s %7i\n" % (municipality['name'], municipality['population']))
	message ("%i municipalites\n" % municipalities)

	updates = 0


	# Load country from OSM
	# tree_osm/root_osm will contain the updated XML for final output

	message ("\nLoading country from OSM...\n")

	query = '[out:xml][timeout:200];(relation["name"="Sverige"]["type"="boundary"]["admin_level"="2"];);out meta;'
	request = urllib.request.Request("https://overpass-api.de/api/interpreter?data=" + urllib.parse.quote(query), headers=request_header)
	file = urllib.request.urlopen(request)
	tree_osm = ET.parse(file)
	root_osm = tree_osm.getroot()
	file.close()

	# Update country population

	relation = root_osm.find("relation")
	population_tag = relation.find("tag[@k='population']")
	if population_tag != None:
		population = population_tag.attrib['v']
		if population != str(country['0']['population']):
			population_tag.set("v", str(entities['0']['population']))
			relation.set("action", "modify")
			updates += 1

	else:
		relation.append(ET.Element("tag", k="population", v=str(entities['0']['population'])))
		relation.set("action", "modify")
		updates += 1

	# Add record date

	date_tag = relation.find("tag[@k='population:date']")
	if date_tag != None:
		old_date = date_tag.attrib['v']
		if old_date != date:
			date_tag.set("v", date)
			relation.set("action", "modify")
	else:
		relation.append(ET.Element("tag", k="population:date", v=date))
		relation.set("action", "modify")		


	# Load all counties from OSM

	message ("\nLoading counties from OSM...\n")

	query = '[out:xml][timeout:200];(area["name"="Sverige"]["type"="boundary"];)->.a;(relation["admin_level"="4"](area.a););out meta;'
	request = urllib.request.Request("https://overpass-api.de/api/interpreter?data=" + urllib.parse.quote(query), headers=request_header)
	file = urllib.request.urlopen(request)
	tree = ET.parse(file)
	root = tree.getroot()
	file.close()

	# Loop counties and update population

	for relation in root.iter("relation"):
		ref_tag = relation.find("tag[@k='ref:se:scb']")
		if ref_tag != None:
			ref = ref_tag.attrib['v']
			if ref in entities:

				population_tag = relation.find("tag[@k='population']")
				if population_tag != None:
					population = population_tag.attrib['v']
					if population != str(entities[ref]['population']):
						population_tag.set("v", str(counties[ref]['population']))
						relation.set("action", "modify")
						updates += 1
				else:
					relation.append(ET.Element("tag", k="population", v=str(entities[ref]['population'])))
					relation.set("action", "modify")
					updates += 1

				date_tag = relation.find("tag[@k='population:date']")
				if date_tag != None:
					old_date = date_tag.attrib['v']
					if old_date != date:
						date_tag.set("v", date)
						relation.set("action", "modify")
				else:
					relation.append(ET.Element("tag", k="population:date", v=date))
					relation.set("action", "modify")

				del entities[ref]
			else:
				message ("County ref %s not found in population data\n" % ref)

		root_osm.append(relation)

	for ref, county in iter(entities.items()):
		if len(ref) == 2:
			message ("County %s %s not found in OSM\n" % (ref, county['name']))


	# Load all municipalities from OSM

	message ("\nLoading municipalities from OSM...\n")

	query = '[out:xml][timeout:200];(area["name"="Sverige"]["type"="boundary"];)->.a;(relation["admin_level"="7"](area.a););out meta;'
	request = urllib.request.Request("https://overpass-api.de/api/interpreter?data=" + urllib.parse.quote(query), headers=request_header)
	file = urllib.request.urlopen(request)
	tree = ET.parse(file)
	root = tree.getroot()
	file.close()

	# Loop municipalities and update population

	for relation in root.iter("relation"):
		ref_tag = relation.find("tag[@k='ref']")
		if ref_tag != None:
			ref = ref_tag.attrib['v']
			if ref in entities:

				population_tag = relation.find("tag[@k='population']")
				if population_tag != None:
					population = population_tag.attrib['v']
					if population != str(entities[ref]['population']):
						population_tag.set("v", str(entities[ref]['population']))
						relation.set("action", "modify")
						updates += 1
				else:
					relation.append(ET.Element("tag", k="population", v=str(entities[ref]['population'])))
					relation.set("action", "modify")
					updates += 1

				date_tag = relation.find("tag[@k='population:date']")
				if date_tag != None:
					old_date = date_tag.attrib['v']
					if old_date != date:
						date_tag.set("v", date)
						relation.set("action", "modify")
				else:
					relation.append(ET.Element("tag", k="population:date", v=date))
					relation.set("action", "modify")

				del entities[ref]
			else:
				message ("Municipality ref %s not found in population data\n" % ref)

		root_osm.append(relation)

	for ref, municipality in iter(entities.items()):
		if len(ref) == 4:
			message ("Municipality %s %s not found in OSM\n" % (ref, municipality['name']))


	# Produce output file

	filename = "Sweden_population.osm"

	message ("\nUpdated %i population tags\n" % updates)
	message ("Saving file '%s'\n\n" % filename)

	root_osm.set("generator", "population2osm v%s" % version)
	root_osm.set("upload", "false")
	tree_osm.write(filename, encoding='utf-8', method='xml', xml_declaration=True)
