from . import get_examples
from ..micom import miio_cloud
from ..micom.micloud.miiocmd import miio_cmd

import logging
_LOGGER = logging.getLogger(__name__)


MODEL_SPECS = {
    # 'default': {'siid': 5, 'aiid': 1, 'execute_siid': 5, 'execute_aiid': 5, 'volume_siid': 2, 'volume_piid': 1},
    'lx01': {},
    'lx04': {'execute_aiid': 4},
    'lx08c': {'siid': 3, 'volume_siid': 4},
}


class miaimsg:

    def __init__(self, hass, conf):
        self.hass = hass
        self.did = str(conf['did'])
        self.spec = MODEL_SPECS[conf.get('model', 'lx01')]

    async def async_send(self, message, data):

        result = await miio_cmd(miio_cloud(), message, self.did, '#')
        if result != 'Invalid command':
            return result

        if message == '?':
            return get_examples(self.hass, 'miai')

        if message.startswith('音量'):
            pos = message.find('%')
            if pos == -1:
                volume = message[2:]
                message = None
            else:
                volume = message[2:pos]
                message = message[pos+1:].strip()
            siid = self.spec.get('volume_siid', 2)
            piid = self.spec.get('volume_piid', 1)
            try:
                volume = int(volume)
                code = await miio_cloud().miot_set_prop(self.did, siid, piid, volume)
                if not message:
                    if code != 0:
                        return f"设置音量出错：{code}"
                    else:
                        raise Exception
            except:
                return f"当前音量：{await miio_cloud().miot_get_prop(self.did, siid, piid)}"

        if message.startswith('查询') or message.startswith('执行') or message.startswith('静默'):
            siid = self.spec.get('execute_siid', 5)
            aiid = self.spec.get('execute_aiid', 5)
            echo = 0 if message.startswith('静默') else 1
            message = message[2:].strip()
            args = [message, echo]
        else:
            siid = self.spec.get('siid', 5)
            aiid = self.spec.get('aiid', 1)
            args = [message]

        if not message:
            return "空谈误国，实干兴邦！"

        result = await miio_cloud().miot_action(self.did, siid, aiid, args)
        return None if result.get('code') == 0 else result
