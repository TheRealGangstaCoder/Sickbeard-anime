# Author: Nic Wolfe <nic@wolfeden.ca>
# URL: http://code.google.com/p/sickbeard/
#
# This file is part of Sick Beard.
#
# Sick Beard is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Sick Beard is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Sick Beard.  If not, see <http://www.gnu.org/licenses/>.

import urllib
import datetime
import time

from xml.dom.minidom import parseString

import sickbeard
import generic

from sickbeard import classes, show_name_helpers, helpers
from sickbeard import exceptions, logger, db
from sickbeard.common import *
from sickbeard import tvcache
from lib.dateutil.parser import parse as parseDate

class NyaaProvider(generic.TorrentProvider):

    def __init__(self):

        generic.TorrentProvider.__init__(self, "NYAA")
        
        self.supportsBacklog = False
        self.description = u"Only useful for anime.<br>Pseudo backlog support."
        self.supportsAbsoluteNumbering = True

        self.cache = NyaaCache(self)

        self.url = 'http://www.nyaa.eu/'

    def isEnabled(self):
        return sickbeard.NYAA
        
    def imageName(self):
        return 'nyaa.png'
    
    def getQuality(self, item):
        
        quality = Quality.nameQuality(item[0])
        return quality    

    def _reverseQuality(self,quality):

        quality_string = ''

        if quality == Quality.SDTV:
            quality_string = 'HDTV x264'
        if quality == Quality.SDDVD:
            quality_string = 'DVDRIP'    
        elif quality == Quality.HDTV:    
            quality_string = '720p HDTV x264'
        elif quality == Quality.FULLHDTV:
            quality_string = '1080p HDTV x264'        
        elif quality == Quality.RAWHDTV:
            quality_string = '1080i HDTV mpeg2'
        elif quality == Quality.HDWEBDL:
            quality_string = '720p WEB-DL'
        elif quality == Quality.FULLHDWEBDL:
            quality_string = '1080p WEB-DL'            
        elif quality == Quality.HDBLURAY:
            quality_string = '720p Bluray x264'
        elif quality == Quality.FULLHDBLURAY:
            quality_string = '1080p Bluray x264'  
        
        return quality_string
    
    def _get_season_search_strings(self, show, season, scene=False):
        names = []
        if season is -1:
            names = [show.name.encode('utf-8')]
        names.extend(show_name_helpers.makeSceneSeasonSearchString(show, season, scene=scene))
        return names

    def _get_episode_search_strings(self, ep_obj):
        # names = [(ep_obj.show.name + " " + str(ep_obj.absolute_number)).encode('utf-8')]
        names = show_name_helpers.makeSceneSearchString(ep_obj)
        logger.log("_get_episode_search_strings : name : " + str(names))
        return names

    def _doSearch(self, search_params, show=None):
    
        if show and not show.is_anime:
            logger.log(u"" + str(show.name) + " is not an anime skiping " + str(self.name))
            return []

        params = {
            "cats": "1_38",
            "term": search_params.encode('utf-8'),
        }

        searchURL = self.url + "?page=rss&" + urllib.urlencode(params)

        logger.log(u"Search string: " + searchURL, logger.DEBUG)

        searchResult = self.getURL(searchURL)

        # Pause to avoid 503's
        time.sleep(5)

        if searchResult == None:
            return []

        try:
            parsedXML = parseString(searchResult)
            items = parsedXML.getElementsByTagName('item')
        except Exception, e:
            logger.log(u"Error trying to load NYAA RSS feed: " + str(e).decode('utf-8'), logger.ERROR)
            return []

        results = []

        for curItem in items:
            (title, url) = self._get_title_and_url(curItem)

            if not title or not url:
                logger.log(u"The XML returned from the NYAA RSS feed is incomplete, this result is unusable: " + searchResult, logger.ERROR)
                continue

            url = url.replace('&amp;', '&')

            results.append(curItem)
            
        

        return results
    
    def _get_title_and_url(self, item):
        (title, url) = generic.TorrentProvider._get_title_and_url(self, item)
        return (title, url)
    
    def findPropers(self, date=None):

        results = []

        for i in [2, 3, 4]: # we will look for a version 2, 3 and 4
            """
            because of this the proper search failed !!
            well more precisly because _doSearch does not accept a dict rather then a string
            params = {
                "q":"v"+str(i).encode('utf-8')
                  }
            """
            for curResult in self._doSearch("v" + str(i)):

                match = re.search('(\w{3}, \d{1,2} \w{3} \d{4} \d\d:\d\d:\d\d) [\+\-]\d{4}', curResult.findtext('pubDate'))
                if not match:
                    continue

                dateString = match.group(1)
                resultDate = parseDate(dateString).replace(tzinfo=None)

                if date == None or resultDate > date:
                    results.append(classes.Proper(curResult.findtext('title'), curResult.findtext('link'), resultDate))

        return results

class NyaaCache(tvcache.TVCache):

   def __init__(self, provider):

        tvcache.TVCache.__init__(self, provider)

        # only poll Nyaa every 15 minutes max
        self.minTime = 15


   def _getRSSData(self):
    
        url = 'http://www.nyaa.se/?page=rss&cats=1_38'
        logger.log(u"Nyaa cache update URL: "+ url, logger.DEBUG)

        data = self.provider.getURL(url)
        
        parsedXML = parseString(data)
        channel = parsedXML.getElementsByTagName('channel')[0]
        description = channel.getElementsByTagName('description')[0]

        description_text = helpers.get_xml_text(description)

        if "User can't be found" in description_text:
            logger.log(u"Nyaa invalid digest, check your config", logger.ERROR)

        if "Invalid Hash" in description_text:
            logger.log(u"Nyaa invalid hash, check your config", logger.ERROR)

        return data

   def _parseItem(self, item):

        (title, url) = self.provider._get_title_and_url(item)

        if not title or not url:
            logger.log(u"The XML returned from the Nyaa RSS feed is incomplete, this result is unusable", logger.ERROR)
            return

        logger.log(u"Adding item from RSS to cache: "+title, logger.DEBUG)

        self._addCacheEntry(title, url)

provider = NyaaProvider()