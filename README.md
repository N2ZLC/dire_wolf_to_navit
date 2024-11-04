![Screenshot](/docs/images/navit.png)

# What is this?

**dire_wolf_to_navit.py** is a simple Python application that takes decoded APRS transmissions from **Dire Wolf** and passes them to **Navit** for rendering on a map.

# Why?

**dire_wolf_to_navit.py** is intended as a proof of concept for those who would rather use a map-centric application like **Navit** over alternative APRS applications like **YAAC** and **Xastir**.

# Yes but why not just use aprs.fi—which is so much better.

**dire_wolf_to_navit.py** is intended for offline or emergency communication. No Internet is needed.

# What can it do?

Show APRS contacts on a map! All contacts are represented by a single icon&nbsp;…

![GPRS Active Icon](/icons/gprs_active.png)

Contacts that have not been heard for a while are ghosted&nbsp;…

![GPRS Inactive Icon](/icons/gprs_inactive.png)

…&nbsp;and eventually disappear altogether. The only APRS data that's displayed is the station ID and comment.

# How does it work?

![How does it work?](/docs/images/how_does_it_work.png)

1. **Dire Wolf** logs APRS events to **aprs.log**.
2. **dire_wolf_to_navit.py** parses and filters **aprs.log** to generate **aprs_poi.txt**.
3. **dire_wolf_to_navit.py** also instructs **Navit** where and when to center and refresh the screen, so that the APRS events from **aprs_poi.txt** are rendered on the map as Points of Interest (POI).

# Installation and configuration

After cloning this project&nbsp;…

```
git clone https://github.com/N2ZLC/dire_wolf_to_navit.git
```

\
…&nbsp;the most important configuration is where you want **Navit's** map centered. Once **dire_wolf_to_navit.py** takes over, it will control this according to its configuration. It is currently set to the center of Phoenix&nbsp;…

```python
# Map center in decimal degree format (sign is cardinality).
# This default is more or less the center of Phoenix (at Sky Harbor/PHX airport).
LATITUDE = 33.435
LONGITUDE = -112.00833334
```

\
Is that what you want? No? Then you must change it! Whatever you enter must correspond to the map you've configured **Navit** to use. Make sense? The coordinate must be within the map's range, or you'll be looking at *terra incognita*.

The other minimal configuration requirements involve **Navit**.

Those coordinates you entered in Python? Enter them in **navit.xml** as well. The ```radius="0"``` attribute is also crucial to avoid an offset&nbsp;…

```xml
<navit center="-112.00833334 33.435" zoom="1024" tracking="0" orientation="0" recent_dest="0" drag_bitmap="0" radius="0">
```

\
Note it's longitude followed by latitude. Don't mix that up! Note you need to delete the **center.txt** file to get Navit to reuse your `center` attribute, as it's only used once.

\
**Navit** must be configured to execute **dire_wolf_to_navit.py** with&nbsp;…

```xml
<vehicle name="Local GPS" profilename="car" enabled="yes" active="1" source="pipe:/home/pi/dire_wolf_to_navit/src/dire_wolf_to_navit.py" follow="1">
```

\
The relevant parts here are the `source` and `follow` attributes.

\
**Navit** needs to have a map, and it needs a Points of Interest (POI) overlay. So you need a configuration like this&nbsp;…

```xml
<!-- Mapset template for openstreetmaps -->
<mapset enabled="yes">
    <map type="textfile" enabled="yes" charset="utf8" data="/home/pi/.navit/aprs_poi.txt"/>
    <map type="binfile" enabled="yes" data="/home/pi/Maps/OSM/<YOUR_MAP>.bin"/>
</mapset>
```

\
Don't have a map? My favorite place to get maps is here: http://maps9.navit-project.org

\
Last but not least, we want our APRS icons to always show regardless of map zoom level. To do that, we need to set `order="1-"` for all `poi_custom0` entries&nbsp;…

```xml
<itemgra item_types="poi_custom0,poi_custom1,poi_custom2,poi_custom3,poi_custom4,poi_custom5,poi_custom6,poi_custom7,poi_custom8,poi_custom9,poi_customa,poi_customb,poi_customc,poi_customd,poi_custome,poi_customf" order="1-">
```

\
You'll need to do this in at least two places in **navit.xml**, as the icons have one entry, and their text labels have another.

\
To assist in configuration, this project contains [example Dire Wolf and Navit configuration files](examples/) that may be useful.

\
A standard **Dire Wolf** installation can be made to utilize the example configuration directly by referencing it when **Dire Wolf** itself is executed&nbsp;…

```
rtl_fm -f 144.39M - | direwolf -c '/home/pi/dire_wolf_to_navit/examples/Dire Wolf configuration/sdr.conf'
```

\
A standard **Navit** installation can be made to utilize the example configuration directly by creating a symbolic link to it&nbsp;…

```
ln -s '/home/pi/dire_wolf_to_navit/examples/Navit configuration/navit.xml' /home/pi/.navit/navit.xml
```

# Execution

| Application           | What?                                                                                                    | Who executes it? |
|:----------------------|:---------------------------------------------------------------------------------------------------------|:-----------------|
| rtl-fm                | Software for controlling RTL2832U-based <br>SDR radio receivers.                                         | You.             |
| Dire Wolf             | Decodes APRS data from audio streams <br>piped to it.                                                    | You.             |
| Navit                 | Vehicle navigation software that <br>renders maps.                                                       | You.             |
| dire_wolf_to_navit.py | Takes decoded APRS transmissions from <br>Dire Wolf and passes them to Navit for <br>rendering on a map. | Navit.           |

\
In order for **Navit** to execute **dire_wolf_to_navit.py**, it must be made executable&nbsp;…

```
sudo chmod +x dire_wolf_to_navit.py
```
