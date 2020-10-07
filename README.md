# population2osm

## 1) population2osm
Extracts most recent quarterly population numbers from SSB and updates OSM file.

### Usage

<code>python population2osm.py</code> (no parameter)


### Notes

* This program will:
  * Load the most recent quarterly population numbers from SSB.
  * Load the country, county and munucipality relations for Norway from OSM.
  * Update the _population_ and _population:date_ tags of the relations.
  * Produce a _Update_population.osm_ file ready for upload to OSM through JOSM.
  
* There are two country relations in OSM for Norway. This program is updating the [full country relation](https://www.openstreetmap.org/relation/2978650) for the Kingdom of Norway, including Svalbard (not the other Norway mainland relation).

* SSB also updates the quarterly population numbers between quarters. The program may be run at any time to pick up any such corrections.

* The following predefined SSB queries are used:
  * Full country: [Population change. Whole country, latest quarter](https://data.ssb.no/api/v0/dataset/1104?lang=en)
  * Counties: [Population changes. Counties, latest quarter](https://data.ssb.no/api/v0/dataset/1102?lang=en)
  * Municipalities: [Population changes. Municipalities, latest quarter](https://data.ssb.no/api/v0/dataset/1108?lang=en)

* As Svalbard residents are included in the Norway mainland population numbers, the population of Svalbard will  not be updated by this program. There is a [separate SSB reporting for Svalbard](https://www.ssb.no/en/befolkning/statistikker/befsvalbard/halvaar), which could be updated manually.

* Population data from SSB is [licensed under the NLOD 2.0 license](https://www.ssb.no/en/informasjon/copyright). OpenStreetMap has obtained [permission](https://lists.nuug.no/pipermail/kart/2018-January/006345.html) to use all NLOD data from SSB.


## 2) urban_population2osm

Extracts population numbers for [urban settlements ("tettsteder")](https://www.ssb.no/en/befolkning/statistikker/beftett) from SSB and updates OSM file.

### Usage

<code>python urban_population2osm.py</code> (no parameter)


### Notes

* This program will:
  * Load population numbers for urban settlements from SSB.
  * Load urban settlements (place objects) with the _ref:ssb_tettsted_ tag for Norway from OSM.
  * Update the _population_ and _population:date_ tags of the settlements.
  * Produce a _tettsted.osm_ file ready for further editing and uploading to OSM through JOSM.
  
* The urban settlement population numbers are used for the _place=city/town/village_ etc nodes. This has the implication that the population numbers for place=city/town will be different from the corresponding municipality relations (could be either smaller or bigger). For example the population of the Arendal place=town node will be different from the Arendal municipality relation.

* The SSB input table and source date must be defined in the program. The program accepts the SSB municipality table on [this web page](https://www.ssb.no/en/befolkning/statistikker/beftett) in CSV format (link below table 1 at the time of writing). The table is updated by SSB once a year, usually in October, and gets a new url link each year.

## 3) Reference

* [Statistics Norway (SSB)](https://www.ssb.no/en)
* [SSB API](https://www.ssb.no/en/omssb/tjenester-og-verktoy/api)
* [SSB population topic page](https://www.ssb.no/en/befolkning)
* [SSB urban settlements ("tettsteder") topic page](https://www.ssb.no/en/befolkning/statistikker/beftett)
