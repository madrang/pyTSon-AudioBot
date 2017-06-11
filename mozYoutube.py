from audiobot.botplayer import playerstatus, basePlayer
from audiobot.mozPlayer import mozPlayer
from audiobot.ffMozREPL import Mozrepl
from audiobot.youtubeparser import YouTubeParser

class mozYoutube(mozPlayer):
    def __init__(self, mozFF = None, playerId='movie_player', tabID=-1):
        if not moxFF:
            mozFF = ffMozREPL.Mozrepl()
        self.moz = mozFF
        self.playerId = playerId
        self.tabID = tabID
    
    def available(self):
        """
        Check if the Youtube player is available.
        """
        try:
            with self:
                tmpVarName = "MozReplTempValue"
                self.run("%(var)s = Components.utils.Sandbox(gBrowser.tabContainer.childNodes[%(id)s].linkedBrowser.contentWindow,{sandboxPrototype:gBrowser.tabContainer.childNodes[%(id)s].linkedBrowser.contentWindow, wantXrays:false})" % {'var':tmpVarName, 'id':self.tabID})
                result = self.get_text_result("Components.utils.evalInSandbox(\"document.getElementById('%s') == null ? false : true\", %s)" % (self.playerId, tmpVarName))
                self.run('delete {v}'.format(v=tmpVarName))
            return bool(strtobool(result))
        except Exception as err:
            return False
    
    def getState(self):
        """
        Returns the state of the player.
        
            -1 – unstarted
            0 – ended
            1 – playing
            2 – paused
            3 – buffering
            5 – video cued
        """
        with self:
            tmpVarName = "MozReplTempValue"
            self.run("%(var)s = Components.utils.Sandbox(gBrowser.tabContainer.childNodes[%(id)s].linkedBrowser.contentWindow,{sandboxPrototype:gBrowser.tabContainer.childNodes[%(id)s].linkedBrowser.contentWindow, wantXrays:false})" % {'var':tmpVarName, 'id':self.tabID})
            result = self.get_text_result("Components.utils.evalInSandbox(\"document.getElementById('%s').getPlayerState()\", %s)" % (self.playerId, tmpVarName))
            self.run('delete {v}'.format(v=tmpVarName))
        if result == '"None"':
            return playerstatus.UNSTARTED
        intRes = int(result)
        #Dont use 5 Video Cued, return -1 Unstarted.
        #Same for any other status.
        if intRes == -1:
            return playerstatus.UNSTARTED
        elif intRes == 0:
            return playerstatus.ENDED
        elif intRes == 1:
            return playerstatus.PLAYING
        elif intRes == 2:
            return playerstatus.PAUSED
        elif intRes == 3:
            return playerstatus.BUFFERING
        else:
            return playerstatus.UNSTARTED
    
    def play(self, pause=False):
        """
        HTML source of the current tab.

        If the current page is big, don't use
        this method on it, it'll take much time.
        """
        with self:
            tmpVarName = "MozReplTempValue"
            self.run("%(var)s = Components.utils.Sandbox(gBrowser.tabContainer.childNodes[%(id)s].linkedBrowser.contentWindow,{sandboxPrototype:gBrowser.tabContainer.childNodes[%(id)s].linkedBrowser.contentWindow, wantXrays:false})" % {'var':tmpVarName, 'id':self.tabID})
            if play:
                result = self.get_text_result("Components.utils.evalInSandbox(\"document.getElementById('%s').playVideo()\", %s)" % (self.playerId, tmpVarName))
            else:
                result = self.get_text_result("Components.utils.evalInSandbox(\"document.getElementById('%s').pauseVideo()\", %s)" % (self.playerId, tmpVarName))
            self.run('delete {v}'.format(v=tmpVarName))
        if result == '"None"':
            return None
        return result.strip(string.whitespace+'"')
    
    def getCurrentTime(self):
        """
        Returns the elapsed time in seconds since the video started playing.
        """
        with self:
            tmpVarName = "MozReplTempValue"
            self.run("%(var)s = Components.utils.Sandbox(gBrowser.tabContainer.childNodes[%(id)s].linkedBrowser.contentWindow,{sandboxPrototype:gBrowser.tabContainer.childNodes[%(id)s].linkedBrowser.contentWindow, wantXrays:false})" % {'var':tmpVarName, 'id':self.tabID})
            result = self.get_text_result("Components.utils.evalInSandbox(\"document.getElementById('%s').getCurrentTime()\", %s)" % (self.playerId, tmpVarName))
            self.run('delete {v}'.format(v=tmpVarName))
        if result == '"None"':
            return None
        return float(result)
    
    def getDuration(self):
        """
        Returns the duration in seconds of the currently playing video.
        """
        with self:
            tmpVarName = "MozReplTempValue"
            self.run("%(var)s = Components.utils.Sandbox(gBrowser.tabContainer.childNodes[%(id)s].linkedBrowser.contentWindow,{sandboxPrototype:gBrowser.tabContainer.childNodes[%(id)s].linkedBrowser.contentWindow, wantXrays:false})" % {'var':tmpVarName, 'id':self.tabID})
            result = self.get_text_result("Components.utils.evalInSandbox(\"document.getElementById('%s').getDuration()\", %s)" % (self.playerId, tmpVarName))
            self.run('delete {v}'.format(v=tmpVarName))
        if result == '"None"':
            return None
        return float(result)
    
    def seek(self, time):
        """
        HTML source of the current tab.

        If the current page is big, don't use
        this method on it, it'll take much time.
        """
        with self:
            tmpVarName = "MozReplTempValue"
            self.run("%(var)s = Components.utils.Sandbox(gBrowser.tabContainer.childNodes[%(id)s].linkedBrowser.contentWindow,{sandboxPrototype:gBrowser.tabContainer.childNodes[%(id)s].linkedBrowser.contentWindow, wantXrays:false})" % {'var':tmpVarName, 'id':self.tabID})
            result = self.get_text_result("Components.utils.evalInSandbox(\"document.getElementById('%s').seekTo(%s, true)\", %s)" % (self.playerId, time, tmpVarName))
            self.run('delete {v}'.format(v=tmpVarName))
        if result == '"None"':
            return None
        return result.strip(string.whitespace+'"')
    
    def getVolume(self):
        """
        HTML source of the current tab.

        If the current page is big, don't use
        this method on it, it'll take much time.
        """
        with self:
            tmpVarName = "MozReplTempValue"
            self.run("%(var)s = Components.utils.Sandbox(gBrowser.tabContainer.childNodes[%(id)s].linkedBrowser.contentWindow,{sandboxPrototype:gBrowser.tabContainer.childNodes[%(id)s].linkedBrowser.contentWindow, wantXrays:false})" % {'var':tmpVarName, 'id':self.tabID})
            result = self.get_text_result("Components.utils.evalInSandbox(\"document.getElementById('%s').getVolume()\", %s)" % (self.playerId, tmpVarName))
            self.run('delete {v}'.format(v=tmpVarName))
        return float(result)
    
    def setVolume(self, level):
        """
        HTML source of the current tab.

        If the current page is big, don't use
        this method on it, it'll take much time.
        """
        with self:
            tmpVarName = "MozReplTempValue"
            self.run("%(var)s = Components.utils.Sandbox(gBrowser.tabContainer.childNodes[%(id)s].linkedBrowser.contentWindow,{sandboxPrototype:gBrowser.tabContainer.childNodes[%(id)s].linkedBrowser.contentWindow, wantXrays:false})" % {'var':tmpVarName, 'id':self.tabID})
            result = self.get_text_result("Components.utils.evalInSandbox(\"document.getElementById('%s').setVolume(%s)\", %s)" % (self.playerId, vol, tmpVarName))
            self.run('delete {v}'.format(v=tmpVarName))
        if result == '"None"':
            return None
        return result.strip(string.whitespace+'"')
    
