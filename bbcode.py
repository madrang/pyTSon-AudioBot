
class _BBCode:
    def __init__(self, **kwargs):
        for key in kwargs:
            setattr(self, key, kwargs[key])
    
    def __getattr__(self, name):
        method = _Virtual(name)
        setattr(self, name, method)
        return method

class _Virtual:

    def __init__(self, name):
        self.__name = name.upper()

    def __call__(self, string, *args):
        return '[{0}{1}]{2}[/{0}]'.format(self.__name, ('=' + ','.join(map(str, args))) if args else '', string)

BBCode = _BBCode()

class _BBListPatch(_BBCode):
    def __init__(self, **kwargs):
        for key in kwargs:
            setattr(self, key, kwargs[key])

    def bulleted(self, *items):
        return '[LIST]' + ''.join(map(lambda item: '[*]' + item, items)) + '[/LIST]'

    def numbered(self, *items):
        return '[LIST=1]' + ''.join(map(lambda item: '[*]' + item, items)) + '[/LIST]'
    
    
#BBCode = _BBListPatch(SELF='[me]', RULE='[hr]')
