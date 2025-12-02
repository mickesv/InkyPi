from plugins.base_plugin.base_plugin import BasePlugin
from PIL import Image
from datetime import datetime, timedelta
from functools import reduce
import logging

#from nordpool import elspot
from . import elspot
from . import testdata

logger = logging.getLogger(__name__)

UPDATETIME = '23'

def _stringify_element(elem):
    return {'start': elem['start'].strftime("%Y-%m-%d %H:%M"),
            'end': elem['end'].strftime("%Y-%m-%d %H:%M"),
            'value': elem['value']} 

def _datify_element(elem):
    return {'start': datetime.strptime(elem['start'], "%Y-%m-%d %H:%M"),
            'end': datetime.strptime(elem['end'], "%Y-%m-%d %H:%M"),
            'value': elem['value']} 

def _parse_entry(table, entry):
    start = entry["start"]
    now = datetime.now()
    value = round(entry["value"]/1000, 2)

    if (start.day < now.day):
        # print("ignoring old dates")
        return table
    else:
        table[0][start.hour] = start.strftime("%d/%m")
        table[1][start.hour] = start.hour
        match start.minute:
            case 0:  table[2][start.hour] = value
            case 15: table[3][start.hour] = value
            case 30: table[4][start.hour] = value
            case 45: table[5][start.hour] = value
        return table

class Nordpool(BasePlugin):
    def generate_settings_template(self):
        template_params = super().generate_settings_template()
        template_params['area'] = 'SE4'
        template_params['updatetime'] = UPDATETIME # Hard coded to avoid worrying about keeping yesterday's data along with tomorrow's
        template_params['currency'] = 'SEK'
        template_params['testdata'] = 'True'
        template_params['startdisplay'] = 6
        template_params['enddisplay'] = 23
        return template_params

    def generate_image(self, settings, device_config):
        area =  settings.get('area')
        title = 'Nordpool ' + area
        use_test_data = settings.get('testdata')
        prices = testdata.oneday
        startdisplay = settings.get('startdisplay', 6)
        enddisplay = settings.get('enddisplay', 23)

        if use_test_data:
            logger.info("Using test data...")
        else:
            logger.info("Maybe fetching from Nordpool")
            prices = self._maybe_fetch(settings)

        #print(prices)
        if prices:
            prices = self._make_table(prices["areas"][area]["values"])
        else:
            logger.error("Do not have a proper nordpool data object.")

        dimensions = device_config.get_resolution()
        if device_config.get_config("orientation") == "vertical":
            dimensions = dimensions[::-1]
        
        template_params = {
            "title": title,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "currenthour": datetime.now().hour,
            "area" : area,
            "prices": prices,
            "plugin_settings": settings,
            "startdisplay": startdisplay,
            "enddisplay": enddisplay
        }

        image = self.render_image(dimensions, "nordpool.html", "nordpool.css", template_params)
        return image

    def _maybe_fetch(self, settings):
        currency = settings.get('currency', 'SEK')
        area =  settings.get('area', 'SE4')

        now = datetime.now()
        yesterday = now - timedelta(days=1)

        lastupdate = settings.get('lastupdate', yesterday.timestamp())
        if lastupdate: lastupdate = datetime.fromtimestamp(lastupdate)

        updatetime = int(settings.get('updatetime', UPDATETIME))
        update_at = now.replace(hour=updatetime, minute=0, second=0)

        cached = settings.get('cached_prices')

        if now > update_at and now.day > lastupdate.day or not cached:
            logger.info("Definitely fetching from Nordpool")
            price_fetcher = elspot.Prices(currency)
            prices = price_fetcher.fetch(areas=[area])

            if None==prices:
                logger.info("Did not get any data for tomorrow. Trying to get today's prices instead.")
                prices = price_fetcher.fetch(areas=[area], end_date=datetime.today())                

            settings['lastupdate'] = now.timestamp()
            settings['cached_prices'] = self._stringify(prices["areas"][area]["values"])
            return prices
        else:
            logger.info("Using cached nordpool data...")
            if cached:
                return {"areas": {area: {"values": self._datify(cached)}}}
            else:
                return testdata.oneday
            


    def _create_empty_table(self):
        rows = 6 # date, hour + 00, 15, 30, 45
        cols = 24 # One hour is probably 23:00 yesterday, but keep the column for now
        t = [[0 for x in range(cols)] for y in range(rows)]
        return t

    def _make_table(self, values):
        start_table = self._create_empty_table()
        table_data = reduce( _parse_entry, values, start_table)
        return table_data

    def _stringify(self, prices):
        return list( map(_stringify_element, prices ))

    def _datify(self, prices):
        return list( map(_datify_element, prices ))
