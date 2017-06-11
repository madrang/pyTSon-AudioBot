#!/usr/bin/env python2

"""
Automate your browser via telnet.
Requirements:
* Firefox
* MozRepl add-on (https://addons.mozilla.org/en-US/firefox/addon/mozrepl/)
  - activate the add-on (under Tools -> MozRepl, "Start" and "Activate on startup")

Documentation of gBrowser:
* https://developer.mozilla.org/en-US/docs/XUL/tabbrowser (reference)
* https://developer.mozilla.org/en-US/docs/Code_snippets/Tabbed_browser (code snippets)

# from jpl2 import firefox as ff

written by Jabba Laci
https://github.com/jabbalaci
"""

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

import json
import re
import socket
import sys
import telnetlib
import time
import string
from threading import RLock
from distutils.util import strtobool

class Mozrepl(object):
    """
    based on https://github.com/bard/mozrepl/wiki/Pyrepl
    """
    
    HOST = 'localhost'
    PORT = 4242
    
    # list of regular expressions
    bprompt = [br'repl\d*> ']
    sprompt = [r'repl\d*> ']
    
    
    def __init__(self, ip=HOST, port=PORT, autoConnect=True):
        self._autoConnected = False
        self._isConnected = False
        self._mutex = RLock()
        self._instanceCount = 0
        
        self.ip = ip
        self.port = port
        self.timeout = 9
        self._autoConnected = autoConnect
        
    
    def __enter__(self):
        if self._autoConnected:
            self._connect()
        if not self._isConnected:
            raise Exception ("Telnet is not connected and auto connect is set to false.")
        self._mutex.acquire()
        self._instanceCount += 1
        return self
    
    def __exit__(self, type, value, traceback):
        self._mutex.release()
        self._instanceCount -= 1
        if self._autoConnected and self._isConnected and self._instanceCount == 0:
            self._disconnect()
    
    def autoConnected(self):
        return self._autoConnected
    
    def isConnected(self):
        return self._isConnected
    
    def _connect(self):
        try:
            self.tn = telnetlib.Telnet(self.ip, self.port)
        except ConnectionRefusedError:
            return
        self.tn.expect(Mozrepl.bprompt)
        self._isConnected = True
    
    def _disconnect(self):
        self._isConnected = False
        try:
            self.tn.close()
        finally:
            del self.tn
    
    def connect(self):
        if self._autoConnected:
            raise Exception ("connect should not be called when autoConnected if set.")
        self._connect()
    
    def disconnect(self):
        if self._autoConnected:
            raise Exception ("connect should not be called when autoConnected if set.")
        self._disconnect()
    
    @staticmethod
    def is_installed():
        """
        Test if MozRepl is installed.

        We simply try to connect to localhost:4242 where
        MozRepl should be listening.
        """
        try:
            with Mozrepl() as mr:
                pass
            return True
        except socket.error:
            return False
    
    def run(self, command):
        """
        Execute the command and fetch its result.
        """
        self.tn.write(command.encode() + b"\n")
        (index, match, data) = self.tn.expect(Mozrepl.bprompt, timeout=self.timeout)
        return data.decode("utf8")
    
    def get_text_result(self, command, sep=''):
        """
        Execute the command and fetch its result as text.
        """
        lines = self.run(command).split("\n")
        if re.search(Mozrepl.sprompt[0].strip(), lines[-1]):
            lines = lines[:-1]
        return sep.join(lines)
    
    def set_tab_url(self, url, tabID=-1):
        """
        Open a URL in any tab, use -1 for the *current* tab.
        """
        with self:
            if not (tabID == 0 or tabID == -1):
                #There should always be a tab zero, same for a current tab.
                #Skip check.
                if not (-1 <= tabID < self.get_number_of_tabs()):
                    raise ValueError("TabID should be -1 for current tab or the tab ID.")
            if tabID == -1:
                self.run("content.location.href = '{u}'".format(u=url))
            else:
                self.run("gBrowser.tabContainer.childNodes[{i}].linkedBrowser.contentDocument.location.href = '{u}'".format(i=tabID, u=url))
    
    def get_tab_url(self, tabID=-1):
        """
        URL of the tab, use -1 for the *current* tab.
        """
        #Access Window Element.
        #gBrowser.tabContainer.childNodes[{i}].linkedBrowser.contentDocument.defaultView
        #gBrowser.tabContainer.childNodes[{i}].linkedBrowser.contentWindow
        with self:
            if not (tabID == 0 or tabID == -1):
                #There should always be a tab zero, same for a current tab.
                #Skip check.
                if not (-1 <= tabID < self.get_number_of_tabs()):
                    raise ValueError("TabID should be -1 for current tab or the tab ID.")
            #Ignore first and last char to remove quotes around the Url.
            if tabID == -1:
                return self.get_text_result("content.location.href")[1:-1]
            #linkedBrowser == browser, contentDocument == content
            return self.get_text_result('gBrowser.tabContainer.childNodes[{i}].linkedBrowser.contentDocument.location.href'.format(i=tabID))[1:-1]

    def open_new_tab(self, url=None):
        """
        Open a new empty tab and put the focus on it.
        """
        if url is None:
            url = "about:blank"
        with self:
            self.run('gBrowser.selectedTab = gBrowser.addTab("{}");'.format(url))
    
    def get_number_of_tabs(self):
        """
        Number of tabs in the browser.
        """
        with self:
            result = self.get_text_result('gBrowser.tabContainer.childNodes.length')
            return int(result)
    
    def set_selected_tab(self, n):
        """
        Put the focus on the selected tab.
        """
        with self:
            if n != 0:
                #There should always be a tab zero
                #Skip check.
                if not (0 <= n < self.get_number_of_tabs()):
                    raise ValueError("Incorrect tab number!")
            self.run('gBrowser.selectedTab = gBrowser.tabContainer.childNodes[{n}]'.format(n=n))
    
    def get_selected_tab_index(self):
        """
        Return the currently selected tab id.
        """
        with self:
            result = self.get_text_result('gBrowser.tabContainer.selectedIndex')
            return int(result)
    
    def is_tab_selected(self, n):
        """
        Put the focus on the selected tab.
        """
        with self:
            if n != 0:
                #There should always be a tab zero.
                #Skip check.
                if not (0 <= n < self.get_number_of_tabs()):
                    raise ValueError("Incorrect tab number!")
            result = self.get_text_result('gBrowser.tabContainer.childNodes[{n}].selected'.format(n=n))
            return bool(strtobool(result))
    
    def get_tab_elementByClassName_html(self, classNames, index=0, tabID=-1):
        """
        Return the HTML source of an element.
        """
        with self:
            tmpVarName = "MozReplTempValue"
            self.run('{v} = gBrowser.tabContainer.childNodes[{i}].linkedBrowser.contentDocument.getElementsByClassName("{n}")'.format(v=tmpVarName, i=tabID, n=classNames))
            result = self.get_text_result('{v}.length <= {c} ? "None" : {v}[{c}].innerHTML'.format(v=tmpVarName, c=index))
            self.run('delete {v}'.format(v=tmpVarName))
        if result == '"None"':
            return None
        return result.strip(string.whitespace+'"')
        
    def get_tab_elementByClassName_href(self, classNames, index=0, tabID=-1):
        """
        Get the url an element points to.
        """
        with self:
            tmpVarName = "MozReplTempValue"
            self.run('{v} = gBrowser.tabContainer.childNodes[{i}].linkedBrowser.contentDocument.getElementsByClassName("{n}")'.format(v=tmpVarName, i=tabID, n=classNames))
            result = self.get_text_result('{v}.length <= {c} ? "None" : {v}[{c}].href'.format(v=tmpVarName, c=index))
            self.run('delete {v}'.format(v=tmpVarName))
        if result == '"None"':
            return None
        return result.strip(string.whitespace+'"')
    
    def get_tab_elementById_html(self, elementId, tabID=-1):
        """
        HTML source of the current tab.

        If the current page is big, don't use
        this method on it, it'll take much time.
        """
        with self:
            tmpVarName = "MozReplTempValue"
            self.run('{v} = gBrowser.tabContainer.childNodes[{i}].linkedBrowser.contentDocument.getElementById("{e}")'.format(v=tmpVarName, i=tabID, e=elementId))
            result = self.get_text_result('{v} == null ? "None" : {v}.innerHTML'.format(v=tmpVarName))
            self.run('delete {v}'.format(v=tmpVarName))
        if result == '"None"':
            return None
        return result.strip(string.whitespace+'"')
        
    def tab_movie_player_available(self, playerId='movie_player', tabID=-1):
        """
        """
        with self:
            tmpVarName = "MozReplTempValue"
            self.run("%(var)s = Components.utils.Sandbox(gBrowser.tabContainer.childNodes[%(id)s].linkedBrowser.contentWindow,{sandboxPrototype:gBrowser.tabContainer.childNodes[%(id)s].linkedBrowser.contentWindow, wantXrays:false})" % {'var':tmpVarName, 'id':tabID})
            result = self.get_text_result("Components.utils.evalInSandbox(\"document.getElementById('%s') == null ? false : true\", %s)" % (playerId, tmpVarName))
            self.run('delete {v}'.format(v=tmpVarName))
        return bool(strtobool(result))
    
    def get_tab_movie_player_state(self, playerId='movie_player', tabID=-1):
        """
        Returns the state of the player.
        
           -1 -- unstarted
            0 -- ended
            1 -- playing
            2 -- paused
            3 -- buffering
            5 -- video cued
        """
        with self:
            tmpVarName = "MozReplTempValue"
            self.run("%(var)s = Components.utils.Sandbox(gBrowser.tabContainer.childNodes[%(id)s].linkedBrowser.contentWindow,{sandboxPrototype:gBrowser.tabContainer.childNodes[%(id)s].linkedBrowser.contentWindow, wantXrays:false})" % {'var':tmpVarName, 'id':tabID})
            result = self.get_text_result("Components.utils.evalInSandbox(\"document.getElementById('%s').getPlayerState()\", %s)" % (playerId, tmpVarName))
            self.run('delete {v}'.format(v=tmpVarName))
        if result == '"None"':
            return -1
        intRes = int(result)
        if -1 > intRes or intRes > 3:
            #Dont use 5 Video Cued, return -1 Unstarted.
            #Same for any other status.
            return -1
        return intRes
    
    def get_tab_movie_player_current_time(self, playerId='movie_player', tabID=-1):
        """
        Returns the elapsed time in seconds since the video started playing.
        """
        with self:
            tmpVarName = "MozReplTempValue"
            self.run("%(var)s = Components.utils.Sandbox(gBrowser.tabContainer.childNodes[%(id)s].linkedBrowser.contentWindow,{sandboxPrototype:gBrowser.tabContainer.childNodes[%(id)s].linkedBrowser.contentWindow, wantXrays:false})" % {'var':tmpVarName, 'id':tabID})
            result = self.get_text_result("Components.utils.evalInSandbox(\"document.getElementById('%s').getCurrentTime()\", %s)" % (playerId, tmpVarName))
            self.run('delete {v}'.format(v=tmpVarName))
        if result == '"None"':
            return None
        return float(result)
        
    def get_tab_movie_player_duration(self, playerId='movie_player', tabID=-1):
        """
        Returns the duration in seconds of the currently playing video.
        """
        with self:
            tmpVarName = "MozReplTempValue"
            self.run("%(var)s = Components.utils.Sandbox(gBrowser.tabContainer.childNodes[%(id)s].linkedBrowser.contentWindow,{sandboxPrototype:gBrowser.tabContainer.childNodes[%(id)s].linkedBrowser.contentWindow, wantXrays:false})" % {'var':tmpVarName, 'id':tabID})
            result = self.get_text_result("Components.utils.evalInSandbox(\"document.getElementById('%s').getDuration()\", %s)" % (playerId, tmpVarName))
            self.run('delete {v}'.format(v=tmpVarName))
        if result == '"None"':
            return None
        return float(result)
    
    def tab_movie_player_seek(self, time, playerId='movie_player', tabID=-1):
        """
        HTML source of the current tab.

        If the current page is big, don't use
        this method on it, it'll take much time.
        """
        with self:
            tmpVarName = "MozReplTempValue"
            self.run("%(var)s = Components.utils.Sandbox(gBrowser.tabContainer.childNodes[%(id)s].linkedBrowser.contentWindow,{sandboxPrototype:gBrowser.tabContainer.childNodes[%(id)s].linkedBrowser.contentWindow, wantXrays:false})" % {'var':tmpVarName, 'id':tabID})
            result = self.get_text_result("Components.utils.evalInSandbox(\"document.getElementById('%s').seekTo(%s, true)\", %s)" % (playerId, time, tmpVarName))
            self.run('delete {v}'.format(v=tmpVarName))
        if result == '"None"':
            return None
        return result.strip(string.whitespace+'"')

    def tab_movie_player_getVolume(self, playerId='movie_player', tabID=-1):
        """
        HTML source of the current tab.

        If the current page is big, don't use
        this method on it, it'll take much time.
        """
        with self:
            tmpVarName = "MozReplTempValue"
            self.run("%(var)s = Components.utils.Sandbox(gBrowser.tabContainer.childNodes[%(id)s].linkedBrowser.contentWindow,{sandboxPrototype:gBrowser.tabContainer.childNodes[%(id)s].linkedBrowser.contentWindow, wantXrays:false})" % {'var':tmpVarName, 'id':tabID})
            result = self.get_text_result("Components.utils.evalInSandbox(\"document.getElementById('%s').getVolume()\", %s)" % (playerId, tmpVarName))
            self.run('delete {v}'.format(v=tmpVarName))
        return float(result)
    
    def tab_movie_player_setVolume(self, vol, playerId='movie_player', tabID=-1):
        """
        HTML source of the current tab.

        If the current page is big, don't use
        this method on it, it'll take much time.
        """
        with self:
            tmpVarName = "MozReplTempValue"
            self.run("%(var)s = Components.utils.Sandbox(gBrowser.tabContainer.childNodes[%(id)s].linkedBrowser.contentWindow,{sandboxPrototype:gBrowser.tabContainer.childNodes[%(id)s].linkedBrowser.contentWindow, wantXrays:false})" % {'var':tmpVarName, 'id':tabID})
            result = self.get_text_result("Components.utils.evalInSandbox(\"document.getElementById('%s').setVolume(%s)\", %s)" % (playerId, vol, tmpVarName))
            self.run('delete {v}'.format(v=tmpVarName))
        if result == '"None"':
            return None
        return result.strip(string.whitespace+'"')

    def tab_movie_player_play(self, play=True, playerId='movie_player', tabID=-1):
        """
        HTML source of the current tab.

        If the current page is big, don't use
        this method on it, it'll take much time.
        """
        with self:
            tmpVarName = "MozReplTempValue"
            self.run("%(var)s = Components.utils.Sandbox(gBrowser.tabContainer.childNodes[%(id)s].linkedBrowser.contentWindow,{sandboxPrototype:gBrowser.tabContainer.childNodes[%(id)s].linkedBrowser.contentWindow, wantXrays:false})" % {'var':tmpVarName, 'id':tabID})
            if play:
                result = self.get_text_result("Components.utils.evalInSandbox(\"document.getElementById('%s').playVideo()\", %s)" % (playerId, tmpVarName))
            else:
                result = self.get_text_result("Components.utils.evalInSandbox(\"document.getElementById('%s').pauseVideo()\", %s)" % (playerId, tmpVarName))
            self.run('delete {v}'.format(v=tmpVarName))
        if result == '"None"':
            return None
        return result.strip(string.whitespace+'"')
    
    def close_tab(self, tabID=-1):
        """
        Close the current tab.
        """
        with self:
            if not (-1 <= tabID < self.get_number_of_tabs()):
                raise ValueError("TabID should be -1 for current tab or the tab ID.")
            if tabID == -1:
                self.run('gBrowser.removeCurrentTab()')
            else:
                self.run('gBrowser.removeTab(gBrowser.tabContainer.childNodes[{}])'.format(tabID))
    
    def get_curr_tab_title(self):
        """
        Title of the page in the current tab.
        """
        with self:
            result = self.get_text_result('document.title')
            return result
    
    def get_tab_list(self):
        cmd = \
"""
String.prototype.format = function() {
    var formatted = this;
    for(arg in arguments) {
        formatted = formatted.replace("{" + arg + "}", arguments[arg]);
    }
    return formatted;
};

var all_tabs = gBrowser.mTabContainer.childNodes;
var tab_list = [];
for (var i = 0; i < all_tabs.length; ++i ) {
    var tab = gBrowser.getBrowserForTab(all_tabs[i]).contentDocument;
    if(tab.location != "about:blank")
        tab_list.push({"url":tab.location, "title":tab.title});
}

for (var i=0; i<tab_list.length; ++i) {
    var title = tab_list[i].title;
    title = title.replace(/"/g, "'");
    var item = '{"index": {0}, "title": "{1}", "url": "{2}"}'.format(i, title, tab_list[i].url);
    repl.print(item);
}
"""
        with self:
            result = self.get_text_result(cmd, sep='\n')
            li = []
            for e in result.split('\n'):
                li.append(json.loads(e))
            return li

    def restoreRepl(self):
        with self:
            self.run('repl.home()')
        
    def isLoadingDocument(self):
        with self:
            result = self.get_text_result("window.getBrowser().webProgress.isLoadingDocument")
            return bool(strtobool(result))
            
    def back(self):
        with self:
            return self.run("gBrowser.goBack()")
        
    @staticmethod
    def sanitizeText(txt):
        txt = txt.strip(string.whitespace + '"')
        if txt.startswith("[URL]") == True:
            txt = txt[len("[URL]"):0-(len("[/URL]"))]
        #<span>The Young Turks LIVE! 6.01.17</span>
        
    
    
#############################################################################
"""
Inject on load

var newTabBrowser = gBrowser.getBrowserForTab(gBrowser.addTab("http://www.google.com/"));
newTabBrowser.addEventListener("load", function () {
  newTabBrowser.contentDocument.body.innerHTML = "<div>hello world</div>";
}, true);
"""

if __name__ == "__main__":
    if not Mozrepl.is_installed():
        print('Cannot connect to {host}:{port}'.format(host=Mozrepl.HOST, port=Mozrepl.PORT))
        print('Make sure that the MozRepl Firefox add-on is installed and activated.')
        sys.exit(1)
    else:
        li = ["Music", "listentothis", "crappymusic"]
        with Mozrepl() as mr:
            for e in li:
                mr.open_new_tab("http://www.reddit.com/r/{}".format(e))
        
