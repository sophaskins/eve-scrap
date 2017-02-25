import sqlite3
import operator
import requests
import cachetools
from xml.etree import ElementTree
from functools import reduce


price_cache = cachetools.TTLCache(10000, 86400)


def typename_to_typeid(typename):
    eve_sde = sqlite3.connect('sqlite-latest.sqlite')
    cursor = eve_sde.cursor()
    cursor.execute("SELECT typeID from invTypes where typeName = ?", (typename,))
    result = cursor.fetchone()

    if result:
        typeid = result[0]
    else:
        typeid = 0

    return typeid


def typeid_to_minerals(type_id):
    """Returns the "perfect refine" component materials of
    a given typeid. At the moment, only supports minerals - the return
    format is an 8-tuple of number of minerals"""

    # The SDE (https://developers.eveonline.com/resource/static-data-export)
    # as converted by Fuzzworks (https://www.fuzzwork.co.uk/dump/)
    eve_sde = sqlite3.connect('sqlite-latest.sqlite')

    cursor = eve_sde.cursor()
    cursor.execute("""SELECT
        SUM(CASE WHEN m1.materialTypeID = 34 THEN m1.quantity ELSE 0 END) AS Tritanium,
        SUM(CASE WHEN m1.materialTypeID = 35 THEN m1.quantity ELSE 0 END) AS Pyerite,
        SUM(CASE WHEN m1.materialTypeID = 36 THEN m1.quantity ELSE 0 END) AS Mexallon,
        SUM(CASE WHEN m1.materialTypeID = 37 THEN m1.quantity ELSE 0 END) AS Isogen,
        SUM(CASE WHEN m1.materialTypeID = 38 THEN m1.quantity ELSE 0 END) AS Nocxium,
        SUM(CASE WHEN m1.materialTypeID = 39 THEN m1.quantity ELSE 0 END) AS Zydrine,
        SUM(CASE WHEN m1.materialTypeID = 40 THEN m1.quantity ELSE 0 END) AS Megacyte,
        SUM(CASE WHEN m1.materialTypeID = 11399 THEN m1.quantity ELSE 0 END) AS Morphite
    FROM invTypes t1
    INNER JOIN invTypeMaterials m1 ON t1.typeID = m1.typeID
    WHERE m1.typeID = ?""", (type_id,))

    result = cursor.fetchone()
    # items that do not refine in to minerals don't get a result row :(
    if result[0] is None:
        result = (0, 0, 0, 0, 0, 0, 0, 0)
    return result


def calculate_refined_value(type_id, refining_multiplier):
    materials = typeid_to_minerals(type_id)
    refined_materials_with_loss = [material * refining_multiplier for material in materials]

    mineral_prices = lookup_mineral_prices()
    refined_value_by_material = map(operator.mul, refined_materials_with_loss, mineral_prices)

    total_value = reduce(operator.add, refined_value_by_material)
    return total_value


def calculate_reprocessing_rate(station_base_rate, tax_rate, scrapmetal_skill_level):
    return 8 * [station_base_rate * (1 - tax_rate) * (1 + 0.02 * scrapmetal_skill_level)]


def lookup_mineral_prices():
    return (
        lookup_market_price(34),  # Tritanium
        lookup_market_price(35),  # Pyerite
        lookup_market_price(36),  # Mexallon
        lookup_market_price(37),  # Isogen
        lookup_market_price(38),  # Nocxium
        lookup_market_price(39),  # Zydrine
        lookup_market_price(40),  # Megacyte
        lookup_market_price(11399),  # Morphite
    )


@cachetools.cached(price_cache)
def lookup_market_price(type_id):
    """Grabs the price of an item from eve-central. For now, we
    *always* grab the Jita 95% Buy Price"""
    params = {"typeid": type_id, "usesystem": 30000142}  # Jita
    response = requests.get("http://api.eve-central.com/api/marketstat", params=params)
    xml_tree = ElementTree.fromstring(response.content)
    price = xml_tree.find('.//buy/percentile').text
    return float(price)


def appraise(items):
    refining_multiplier = 1
    parsed_out = []
    for item in items:
        try:
            appraisal = appraise_item(item)
            if appraisal:
                parsed_out.append(appraisal)
        except e:
            pass
    return parsed_out


def appraise_item(item):
    refining_multiplier = 1
    appraisal = None
    typeID = typename_to_typeid(item['name'])
    if typeID:
        market_price = lookup_market_price(typeID)
        refined_value = calculate_refined_value(typeID, refining_multiplier)

        if market_price > 0 and refined_value > 0:
            refining_loss = (market_price - refined_value) / market_price
            should_refine = refining_loss < 0.2

            appraisal = {
                'type': 'successful',
                'name': item['name'],
                'quantity': item['quantity'],
                'market_price': market_price,
                'refined_value': refined_value,
                'refining_loss': refining_loss * 100.0,
                'refine': should_refine,
            }
        else:
            appraisal = {
                'type': 'norefine',
                'name': item['name'],
                'quantity': item['quantity'],
                'refine': False,
            }

    if appraisal is None:
        appraisal = {
            'type': 'unparseable',
            'raw_item': item,
        }

    return appraisal
