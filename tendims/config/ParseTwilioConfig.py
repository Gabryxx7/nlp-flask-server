import ConfigParser
import io

class Parser:
    _account_sid = ""
    _auth_token = ""
    _configFilePath = ""
    _botURL = ""
    _clientAccesAPIAI = ""
    _devAccessAPIAI = ""
    configParser = ConfigParser.RawConfigParser()

    def __init__(self, filepath):
        self._configFilePath = filepath
        print 'Using File : ', filepath

        try:
            self.configParser.readfp(open(filepath, 'r'))
        except:
            print 'Invalid cofig file path, Cannot open', filepath

    def parseConfig(self):
        try:
            self._auth_token =  self.configParser.get('User_Twilio_Config','AuthToken')
            self._account_sid = self.configParser.get('User_Twilio_Config','AccountSid')
            self._botURL = self.configParser.get('User_Twilio_Config','botURL')
            self._clientAccesAPIAI = self.configParser.get('User_Twilio_Config','ClientAccessTokenAPIAI')
            self._devAccessAPIAI = self.configParser.get('User_Twilio_Config','DevAccessTokenAPIAI')
        except:
            print 'Invalid configuration'


    def getAuthToken(self):
        return self._auth_token

    def getAccountSid(self):
        return self._account_sid

    def getBotURL(self):
        return self._botURL

    def getClientAccessAPIAI(self):
        return self._clientAccesAPIAI

    def getDevAccessAPIAI(self):
        return self._devAccessAPIAI


