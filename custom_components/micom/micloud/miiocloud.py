import json
import logging

_LOGGER = logging.getLogger(__name__)

#REGIONS = ['cn', 'de', 'i2', 'ru', 'sg', 'us']


class MiIOCloud:

    def __init__(self, auth, region=None):
        self.auth = auth
        self.server = 'https://' + ('' if region is None or region == 'cn' else region + '.') + 'api.io.mi.com/app'

    async def request(self, uri, data='', relogin=True):
        if self.auth.token is not None or await self.auth.login():  # Ensure login
            _LOGGER.debug(f"{uri} {data}")
            try:
                r = await self.auth.session.post(self.server + uri, cookies={
                    'userId': self.auth.token['userId'],
                    'serviceToken': self.auth.token['serviceToken'],
                    # 'locale': 'en_US'
                }, headers={
                    'User-Agent': self.auth.user_agent,
                    'x-xiaomi-protocal-flag-cli': 'PROTOCAL-HTTP2'
                }, data=self.auth.sign(uri, data), timeout=10)
                resp = await r.json(content_type=None)
                code = resp['code']
                if code == 0:
                    result = resp['result']
                    if result is not None:
                        return result
                elif code == 2 and relogin:
                    _LOGGER.debug(f"Auth error on request {uri}, relogin...")
                    self.token = None  # Auth error, reset login
                    return self.request(uri, data, False)
            except Exception as e:
                resp = e
        else:
            resp = "Login failed"
        error = f"Request {uri} error: {resp}"
        _LOGGER.error(error)
        return Exception(error)

    async def miotspec(self, api, data='{}'):
        return await self.request('/miotspec/' + api, data)

    async def miot_prop(self, did, props=[]):
        prop_set = False
        params = ''
        for prop in props:
            if params:
                params += ', '
            params += '{"did":"%s", "siid":%s, "piid":%s' % (did, prop[0], prop[1])
            if (len(prop) > 2):
                prop_set = True
                value = prop[2]
                if isinstance(value, bool) or value is None:
                    value = str(value).lower()
                elif isinstance(value, str) and (len(prop) == 3 or prop[3]):
                    value = ('"' + value + '"')
                params += ', "value":%s' % value
            params += '}'
        result = await self.miotspec('prop/' + 'set' if prop_set else 'get', '{"params": [' + params + ']}')
        if isinstance(result, list):
            if prop_set:
                return [it.get('code') == 0 for it in result]
            return [it.get('value') if it.get('code') == 0 else None for it in result]
        return result

    async def miot_prop_get(self, did, siid, piid=1):
        result = await self.miot_prop(did, {(siid, piid)})
        return result[0] if isinstance(result, list) else None

    async def miot_prop_set(self, did, siid, piid, value, quote=True):
        result = await self.miot_prop(did, {(siid, piid, value, quote)})
        return result[0] if isinstance(result, list) else False

    async def miot_action(self, did, siid, aiid, _in='[]'):
        if not isinstance(_in, str):
            _in = json.dumps(_in)
        elif _in[0] != '[':
            _in = f'["{_in}"]'
        return await self.miotspec('action', '{"params": {"did":"%s", "siid":%s, "aiid":%s, "in":%s}}' % (
            did or f'action-{siid}-{aiid}', siid, aiid, _in))

    async def device_list(self):
        result = await self.request('/home/device_list', '{"getVirtualModel": false, "getHuamiDevices": 0}')
        return None if isinstance(result, Exception) else result.get('list') 
