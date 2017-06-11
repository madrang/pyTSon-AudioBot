#!/usr/bin/env python3
"""%(prog)s - Get Youtube playlist Url

Usage: %(prog)s [-vf] URL...
       %(prog)s [-vf] URL [URL ...]

URL should be a Youtube Video or the Video ID.
"""
try:
    import requests
except ImportError:
    #Fix for TS3 not including requests by default.
    #If not found, use the one included in the audiobot folder.
    import audiobot.requests
import sys, os
from urllib.parse import urlparse, parse_qs, urlencode
import re

#from urlparse import urlparse, parse_qs


bs4Imported=False
try:
    import bs4
    bs4Imported=True
except ImportError:
    from html.parser import HTMLParser
    from html.entities import name2codepoint
    class MixParser(HTMLParser):
        final_link = None
        def handle_starttag(self, tag, attrs):
            if tag == "a" and self.final_link is None:
                dkeys = dict((x, y) for x, y in attrs)
                if "class" in dkeys and "mix-playlist" in dkeys['class'] and "href" in dkeys:
                    self.final_link = dkeys['href']
                    
    class TitleParser(HTMLParser):
        final_title = None
        def handle_starttag(self, tag, attrs):
            if tag == "span" and self.final_title is None:
                dkeys = dict((x, y) for x, y in attrs)
                if "id" in dkeys and dkeys['id'] == "eow-title" and "title" in dkeys:
                    self.final_title = dkeys['title']
                    
    class HTMLTextExtractor(HTMLParser):
        def __init__(self):
            HTMLParser.__init__(self)
            self.result = [ ]
        
        def handle_data(self, d):
            self.result.append(d)
        
        def handle_charref(self, number):
            codepoint = int(number[1:], 16) if number[0] in (u'x', u'X') else int(number)
            self.result.append(unichr(codepoint))
        
        def handle_entityref(self, name):
            codepoint = htmlentitydefs.name2codepoint[name]
            self.result.append(unichr(codepoint))
        
        def get_text(self):
            return u''.join(self.result)
    
    
class YouTubeParser():
    
    @staticmethod
    def grab_mix_playlist_id(video_id, fullUrl=False):
        if video_id.startswith("https://"):
            video_id = YouTubeParser.sanitizeUrl(video_id)
        
        response = requests.get("https://www.youtube.com/watch", params={"v": video_id})
        return YouTubeParser.grab_mix_playlist_id_from_content(response.content, fullUrl=fullUrl)
        
    @staticmethod
    def grab_mix_playlist_id_from_content(content, fullUrl=False):
        if bs4Imported:
            selec = "a.mix-playlist"
            bs = bs4.BeautifulSoup(content, "lxml")
            items = bs.select(selec)
            if len(items) != 1:
                return None
            else:
                if fullUrl:
                    return "https://www.youtube.com%s" % items[0]['href']
                else:
                    url = parse_qs(urlparse(items[0]['href']).query)
                    return url['list'][0]
        else:
            parser = MixParser()
            parser.feed(content.decode('utf-8'))
            if parser.final_link is None:
                return None
            else:
                if fullUrl:
                    return "https://www.youtube.com%s" % parser.final_link
                else:
                    url = parse_qs(urlparse(parser.final_link).query)
                    return url['list'][0]
                    
    
    @staticmethod
    def grab_title(video_id):
        if video_id.startswith("https://"):
            video_id = YouTubeParser.sanitizeUrl(video_id)
        
        response = requests.get("https://www.youtube.com/watch", params={"v": video_id})
        return YouTubeParser.grab_title_from_content(response.content)
        
    @staticmethod
    def grab_title_from_content(content):
        if bs4Imported:
            selec = "span#eow-title"
            bs = bs4.BeautifulSoup(content, "lxml")
            items = bs.select(selec)
            if len(items) != 1:
                return None
            else:
                return items[0]['title']
        else:
            parser = TitleParser()
            parser.feed(content.decode('utf-8'))
            return parser.final_title
    
    @staticmethod
    def textFromHTML(html):
        if not html:
            return None
        if bs4Imported:
            bs = bs4.BeautifulSoup(html)
            return bs.get_text()
        else:
            parser = HTMLTextExtractor()
            parser.feed(html)
            return parser.get_text()
    
    @staticmethod
    def sanitizeUrl(url, fullUrl=False, allowPlaylist=False, allowTime=False):
        """Returns Video_ID extracting from the given url of Youtube
        
        Examples of URLs:
          Valid:
            'http://youtu.be/_lOT2p_FCvA',
            'www.youtube.com/watch?v=_lOT2p_FCvA&feature=feedu',
            'http://www.youtube.com/embed/_lOT2p_FCvA',
            'http://www.youtube.com/v/_lOT2p_FCvA?version=3&amp;hl=en_US',
            'https://www.youtube.com/watch?v=rTHlyTphWP0&index=6&list=PLjeDyYvG6-40qawYNR4juzvSOg-ezZ2a6',
            'youtube.com/watch?v=_lOT2p_FCvA',
            'https://m.youtube.com/watch?v=683hzaj3oc8'
          Invalid:
            'youtu.be/watch?v=_lOT2p_FCvA',
        """
        
        if url.startswith(('youtu', 'www')):
            url = 'http://' + url
            
        pUrl = urlparse(url)
        videoID = None
        queryArgs = None
        
        if pUrl.query:
            queryArgs = parse_qs(pUrl.query)
        
        if 'youtube' in pUrl.hostname:
            if pUrl.path == '/watch' and 'v' in queryArgs:
                videoID = queryArgs['v'][0]
            elif pUrl.path.startswith(('/embed/', '/v/')):
                videoID = pUrl.path.split('/')[2]
            else:
                raise ValueError("Youtube url has no video id.")
        elif 'youtu.be' in pUrl.hostname:
            videoID = pUrl.path[1:]
        else:
            raise ValueError("Not a youtube url.")
        
        if not videoID or not re.match(r"^[-\w]{11}$", videoID):
            raise ValueError("Invalid video Id")
            
        #Id is valid, if there are args, validate those.
        if queryArgs:
            if allowPlaylist and 'list' in queryArgs:
                #TODO Validate playlist id.
                pass
                if 'index' in queryArgs:
                    #TODO Validate index.
                    pass
            if allowTime and 't' in queryArgs:
                #TODO Validate Time arg
                pass
        
        #Return results.
        if not fullUrl:
            if not allowPlaylist and not allowTime:
                return videoID
            else:
                res = { 'id': videoID }
                if 'list' in queryArgs:
                    res['list'] = queryArgs['list'][0]
                if 't' in queryArgs:
                    res['t'] = queryArgs['t'][0]
                return res
        #Build the url query.
        newQuery = [ ('v', videoID) ]
        if queryArgs:
            if allowPlaylist and 'list' in queryArgs:
                newQuery.append(('list', queryArgs['list'][0]))
                if 'index' in queryArgs:
                    newQuery.append(('index', queryArgs['index'][0]))
            if allowTime and 't' in queryArgs:
                newQuery.append(('t', queryArgs['t'][0]))
        
        return "https://www.youtube.com/watch?{}".format(urlencode(newQuery))

#Title <span id="eow-title" class="watch-title" dir="ltr" title="Murder By Death - Comin Home">Murder By Death - Comin Home</span>
#Next <a class="ytp-next-button ytp-button" data-preview="https://i1.ytimg.com/vi/9b7iOZiRdOE/mqdefault.jpg" data-tooltip-text="Awolnation - Burn it Down (Sons of Anarchy) HD" href="https://www.youtube.com/watch?list=RDU6_IOwu-H8A&amp;v=9b7iOZiRdOE" aria-disabled="false" title="Next"><svg height="100%" version="1.1" viewBox="0 0 36 36" width="100%"><use class="ytp-svg-shadow" xlink:href="#ytp-svg-10"></use><path class="ytp-svg-fill" d="M 12,24 20.5,18 12,12 V 24 z M 22,12 v 12 h 2 V 12 h -2 z" id="ytp-svg-10"></path></svg></a>
#Previous <a class="ytp-prev-button ytp-button" aria-disabled="false" title="Replay"><svg height="100%" version="1.1" viewBox="0 0 36 36" width="100%"><use class="ytp-svg-shadow" xlink:href="#ytp-svg-8"></use><path class="ytp-svg-fill" d="m 12,12 h 2 v 12 h -2 z m 3.5,6 8.5,6 V 12 z" id="ytp-svg-8"></path></svg></a>

#PlaylistTitle <h3 class="playlist-title"> Mix - Jamey Johnson - You are my sunshine (Sons of Anarchy Soundtrack) </h3>

#<a href="/playlist?list=PL7FEE4DBE28ADEB51" class=" yt-uix-sessionlink      spf-link " data-sessionlink="ei=4FY6WaTkOcGPDanpp4gN">2017 Current Playlist</a>

if __name__ == "__main__":
    args = sys.argv
    prog = os.path.basename(args.pop(0))
    
    if '-h' in args or '--help' in args:
        print(__doc__ % {'prog': prog}, end='')
        exit(0)
    
    verbose = False
    fullUrlFlag = False
    
    while args and args[0][0] == '-':
        flag = args.pop(0)
        if flag == '-v':
            verbose = True
        elif flag == '-f':
            fullUrlFlag = True
        else:
            break
    
    if len(args) <= 0:
        print(__doc__ % {'prog': prog}, end='')
        exit(1)
    
    if len(args) > 1:
        print ("Resolving more than one video mix is not implemented.")
        exit(1)
    
    try:
        video_id = args[0]
        if video_id.startswith("https://"):
            video_id = YouTubeParser.sanitizeUrl(video_id)
        
        response = requests.get("https://www.youtube.com/watch", params={"v": video_id})
        
        print("Title: %s" % YouTubeParser.grab_title_from_content(response.content))
        print("Mix: %s" % YouTubeParser.grab_mix_playlist_id_from_content(response.content, fullUrl=fullUrlFlag))
    except ValueError as error:
        print(repr(error))
    
