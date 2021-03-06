from .genie import handleRequest, makeResponse, errorResult
from .basebot import basebot

import logging
_LOGGER = logging.getLogger(__name__)


class geniebot(basebot):

    def access_token(self, data):
        return data['payload']['accessToken']

    async def async_handle(self, data):
        self.data = data
        return await handleRequest(data)

    def error(self, err):
        return errorResult('ACCESS_TOKEN_INVALIDATE' if type(err) == PermissionError else 'SERVICE_ERROR')

    def response(self, answer):
        return self.json(makeResponse(self.data, answer))
