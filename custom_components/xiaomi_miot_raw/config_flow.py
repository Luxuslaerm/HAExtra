"""teset."""
from homeassistant import config_entries
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import *
from .deps.const import (
    DOMAIN,
    CONF_UPDATE_INSTANT,
    CONF_MAPPING,
    CONF_CONTROL_PARAMS,
    CONF_CLOUD,
    CONF_MODEL,
    ATTR_STATE_VALUE,
    ATTR_MODEL,
    ATTR_FIRMWARE_VERSION,
    ATTR_HARDWARE_VERSION,
    SUPPORTED_DOMAINS,
)
import json
from homeassistant.helpers.device_registry import format_mac
from miio import (
    Device as MiioDevice,
    DeviceException,
)
from miio.miot_device import MiotDevice
import async_timeout
from aiohttp import ClientSession
from homeassistant.helpers import aiohttp_client, discovery
import requests
from .deps.miot_device_adapter import MiotAdapter
from homeassistant.components import persistent_notification
from .deps.xiaomi_cloud_new import MiCloud
import re
from .deps.special_devices import SPECIAL_DEVICES

VALIDATE = {'fan': [{"switch_status"}, {"switch_status"}],
            'switch': [{"switch_status"}, {"switch_status"}],
            'light': [{"switch_status"}, {"switch_status"}],
            'cover': [{"motor_control"}, {"motor_control"}],
            'humidifier': [{"switch_status","target_humidity"}, {"switch_status","target_humidity"}]
            }

async def validate_devinfo(hass, data):
    """检验配置是否缺项。无问题返回[[],[]]，有缺项返回缺项。"""
    # print(result)
    devtype = data['devtype']
    ret = [[],[]]
    requirements = VALIDATE.get(devtype)
    if not requirements:
        return ret
    else:
        for item in requirements[0]:
            if item not in json.loads(data[CONF_MAPPING]):
                ret[0].append(item)
        for item in requirements[1]:
            if item not in json.loads(data[CONF_CONTROL_PARAMS]):
                ret[1].append(item)
        return ret

async def async_get_mp_from_net(hass, model):
    cs = aiohttp_client.async_get_clientsession(hass)
    url = "https://raw.githubusercontent.com/ha0y/miot-params/master/main.json"
    with async_timeout.timeout(10):
        try:
            a = await cs.get(url)
        except Exception:
            a = None
    if a:
        data = await a.json(content_type=None)
        for item in data:
            if item['device_model'] == model:
                return item
    return None

async def guess_mp_from_model(hass,model):
    if m := SPECIAL_DEVICES.get(model):
        return {
            "device_type": m["device_type"],
            "mapping": json.dumps(m["mapping"],separators=(',', ':')),
            "params": json.dumps(m["params"],separators=(',', ':')),
        }

    cs = aiohttp_client.async_get_clientsession(hass)
    url_all = 'http://miot-spec.org/miot-spec-v2/instances?status=all'
    url_spec = 'http://miot-spec.org/miot-spec-v2/instance'
    with async_timeout.timeout(10):
        try:
            a = await cs.get(url_all)

        except Exception:
            a = None
    if a:
        dev_list = await a.json(content_type=None)
        dev_list = dev_list.get('instances')
    else:
        dev_list = None
    result = None
    if dev_list:
        for item in dev_list:
            if model == item['model']:
                result = item
        urn = result['type']
        params = {'type': urn}
        with async_timeout.timeout(10):
            try:
                s = await cs.get(url_spec, params=params)
            except Exception:
                s = None
        if s:
            spec = await s.json()
            ad = MiotAdapter(spec)
            mt = ad.mitype

            dt = ad.get_all_devtype()
            mp = ad.get_all_mapping()
            prm = ad.get_all_params()
            return {
                'device_type': dt or ['switch'],
                'mapping': json.dumps(mp,separators=(',', ':')),
                'params': json.dumps(prm,separators=(',', ':'))
            }
    else:
        return {
            'device_type': [],
            'mapping': "{}",
            'params': "{}"
        }
    # TODO

def data_masking(s: str, n: int) -> str:
    return re.sub(f"(?<=.{{{n}}}).(?=.{{{n}}})", "*", str(s))

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize flow"""
        self._name = vol.UNDEFINED
        self._host = vol.UNDEFINED
        self._token = vol.UNDEFINED
        self._mapping = vol.UNDEFINED
        self._params = vol.UNDEFINED
        self._devtype = vol.UNDEFINED
        self._info = None
        self._model = None
        self._input2 = {}

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            if user_input['action'] == 'xiaomi_account':
                return await self.async_step_xiaomi_account()
            elif user_input['action'] == 'localinfo':
                return await self.async_step_localinfo()
            else:
                # device = next(d for d in self.hass.data[DOMAIN]['devices']
                            #   if d['did'] == user_input['action'])
                # return self.async_show_form(
                #     step_id='localinfo',
                #     data_schema=vol.Schema({
                #         vol.Required('host', default=device['localip']): str,
                #         vol.Required('token', default=device['token']): str,
                #     }),
                #     description_placeholders={'error_text': ''}
                # )
                pass

        # if DOMAIN in self.hass.data and 'micloud_devices' in self.hass.data[DOMAIN]:
        #     for device in self.hass.data[DOMAIN]['devices']:
        #         if (device['model'] == 'lumi.gateway.mgl03' and
        #                 device['did'] not in ACTIONS):
        #             name = f"Add {device['name']} ({device['localip']})"
        #             ACTIONS[device['did']] = name

        return self.async_show_form(
            step_id='user',
            data_schema=vol.Schema({
                vol.Required('action', default='localinfo'): vol.In({
                    'xiaomi_account': "登录小米账号",
                    'localinfo': "接入设备"
                })
            })
        )

    async def async_step_localinfo(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}

        # Check if already configured
        # await self.async_set_unique_id(DOMAIN)
        # self._abort_if_unique_id_configured()

        if user_input is not None:

            self._name = user_input[CONF_NAME]
            self._host = user_input[CONF_HOST]
            self._token = user_input[CONF_TOKEN]
            self._input2 = {**self._input2, **user_input}
            # self._mapping = user_input[CONF_MAPPING]
            # self._params = user_input[CONF_CONTROL_PARAMS]

            device = MiioDevice(self._host, self._token)
            try:
                self._info = device.info()
            except DeviceException:
                # print("DeviceException!!!!!!")
                errors['base'] = 'cannot_connect'
            # except ValueError:
            #     errors['base'] = 'value_error'


            if self._info is not None:
                unique_id = format_mac(self._info.mac_address)
                # await self.async_set_unique_id(unique_id)
                for entry in self._async_current_entries():
                    if entry.unique_id == unique_id:
                        persistent_notification.async_create(
                            self.hass,
                            f"您新添加的设备: **{self._name}** ，\n"
                            f"其 MAC 地址与现有的某个设备相同。\n"
                            f"只是通知，不会造成任何影响。",
                            "设备可能重复")
                        break

                self._abort_if_unique_id_configured()
                d = self._info.raw
                self._model = d['model']
                device_info = (
                    f"Model: {d['model']}\n"
                    f"Firmware: {d['fw_ver']}\n"
                    f"MAC: {d['mac']}\n"
                )

                # self._info = self.get_devconfg_by_model(self._model)

                # self._info = await async_get_mp_from_net(self.hass, self._model) \
                    # or await guess_mp_from_model(self.hass, self._model)

                self._info = await guess_mp_from_model(self.hass, self._model)

                if self._info and self._info.get('mapping') != "{}":
                    device_info += "\n已经自动发现配置参数。\n如无特殊需要，无需修改下列内容。\n"
                    devtype_default = self._info.get('device_type')

                    # mp = f'''{{"{self._info.get('device_type')}":{self._info.get('mapping')}}}'''
                    # prm = f'''{{"{self._info.get('device_type')}":{self._info.get('params')}}}'''

                    mp = self._info.get('mapping')
                    prm = self._info.get('params')
                    mapping_default = mp
                    params_default = prm
                else:
                    device_info += f"很抱歉，未能自动发现配置参数。但这不代表您的设备不受支持。\n您可以[手工编写配置](https://github.com/ha0y/xiaomi_miot_raw/#文件配置法)，或者将型号 **{self._model}** 报告给作者。"
                    devtype_default = []
                    mapping_default = '{"switch_status":{"siid":2,"piid":1}}'
                    params_default = '{"switch_status":{"power_on":true,"power_off":false}}'

                return self.async_show_form(
                    step_id="devinfo",
                    data_schema=vol.Schema({
                        # vol.Required('devtype', default=devtype_default): vol.In(SUPPORTED_DOMAINS),
                        vol.Required('devtype', default=devtype_default): cv.multi_select(SUPPORTED_DOMAINS),
                        vol.Required(CONF_MAPPING, default=mapping_default): str,
                        vol.Required(CONF_CONTROL_PARAMS, default=params_default): str,
                        vol.Optional('cloud_read'): bool,
                        vol.Optional('cloud_write'): bool,
                        }),
                    description_placeholders={"device_info": device_info},
                    errors=errors,
                )
            else:
                return self.async_show_form(
                    step_id='xiaoai',
                    data_schema=vol.Schema({
                        vol.Required(CONF_MODEL): str,
                    }),
                    errors={'base': 'no_connect_warning'}
                )

        return self.async_show_form(
            step_id="localinfo",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME): str,
                    vol.Required(CONF_HOST, default='192.168.'): str,
                    vol.Required(CONF_TOKEN): str,
                    # vol.Required(CONF_MAPPING, default='{"switch_status":{"siid":2,"piid":1}}'): str,
                    # vol.Required(CONF_CONTROL_PARAMS, default='{"switch_status":{"power_on":true,"power_off":false}}'): str,
                }
            ),
            # description_placeholders={"device_info": "device_info"},
            errors=errors,
        )

    async def async_step_devinfo(self, user_input=None):
        errors = {}
        hint = ""
        if user_input is not None:
            self._devtype = user_input['devtype']
            self._input2['devtype'] = self._devtype
            self._input2[CONF_MAPPING] = user_input[CONF_MAPPING]
            self._input2[CONF_CONTROL_PARAMS] = user_input[CONF_CONTROL_PARAMS]
            # self._input2['cloud_read'] = user_input['cloud_read']
            self._input2['cloud_write'] = user_input.get('cloud_write')

            # v = await validate_devinfo(self.hass, self._input2)
            v= [[],[]]
            if v == [[],[]] :

                try:
                    # print(result)
                    if not user_input.get('cloud_read') and not user_input.get('cloud_write'):
                        device = MiotDevice(ip=self._input2[CONF_HOST], token=self._input2[CONF_TOKEN], mapping=list(json.loads(self._input2[CONF_MAPPING]).values())[0])
                        result = device.get_properties_for_mapping()
                        return self.async_create_entry(
                            title=self._input2[CONF_NAME],
                            data=self._input2,
                        )
                    else:
                        if cloud := self.hass.data[DOMAIN].get('cloud_instance'):
                            did = None
                            for dev in self.hass.data[DOMAIN]['micloud_devices']:
                                if dev.get('localip') == self._input2[CONF_HOST]:
                                    did = dev['did']
                            if did:
                                self._input2['update_from_cloud'] = {
                                    'did': did,
                                    'userId': cloud.auth['user_id'],
                                    'serviceToken': cloud.auth['service_token'],
                                    'ssecurity': cloud.auth['ssecurity'],
                                }
                                return self.async_create_entry(
                                    title=self._input2[CONF_NAME],
                                    data=self._input2,
                                )
                            else:
                                return self.async_show_form(
                                    step_id="cloudinfo",
                                    data_schema=vol.Schema({
                                        vol.Required('did'): str,
                                        vol.Required('userId', default=cloud.auth['user_id']): str,
                                        vol.Required('serviceToken', default=cloud.auth['service_token']): str,
                                        vol.Required('ssecurity', default=cloud.auth['ssecurity']): str,
                                    }),
                                description_placeholders={"device_info": "没找到 did，请手动填一下"},
                                errors=errors,
                            )
                        else:
                            return self.async_show_form(
                                step_id="cloudinfo",
                                data_schema=vol.Schema({
                                    vol.Required('did'): str,
                                    vol.Required('userId'): str,
                                    vol.Required('serviceToken'): str,
                                    vol.Required('ssecurity'): str,
                                    }),
                                # description_placeholders={"device_info": hint},
                                errors=errors,
                            )
                except DeviceException as ex:
                    errors["base"] = "no_local_access"
                    hint = f"错误信息: {ex}"
            else:
                errors["base"] = "bad_params"

                hint = ""
                if v[0]:
                    hint += "\nmapping 缺少必须配置的项目："
                    for item in v[0]:
                        hint += (item + ', ')
                if v[1]:
                    hint += "\nparams 缺少必须配置的项目："
                    for item in v[1]:
                        hint += (item + ', ')

            # if info:
        return self.async_show_form(
            step_id="devinfo",
            data_schema=vol.Schema({
                vol.Required('devtype', default=user_input['devtype']): cv.multi_select(SUPPORTED_DOMAINS),
                vol.Required(CONF_MAPPING, default=user_input[CONF_MAPPING]): str,
                vol.Required(CONF_CONTROL_PARAMS, default=user_input[CONF_CONTROL_PARAMS]): str,
                vol.Optional('cloud_read'): bool,
                vol.Optional('cloud_write'): bool,
                }),
            description_placeholders={"device_info": hint},
            errors=errors,
        )

    async def async_step_cloudinfo(self, user_input=None):
        errors = {}
        if user_input is not None:
            self._input2['update_from_cloud'] = {}
            self._input2['update_from_cloud']['did'] = user_input['did']
            self._input2['update_from_cloud']['userId'] = user_input['userId']
            self._input2['update_from_cloud']['serviceToken'] = user_input['serviceToken']
            self._input2['update_from_cloud']['ssecurity'] = user_input['ssecurity']

            return self.async_create_entry(
                title=self._input2[CONF_NAME],
                data=self._input2,
            )

    async def async_step_import(self, user_input):
        """Import a config flow from configuration."""
        return True

    async def async_step_xiaomi_account(self, user_input=None, error=None):
        if user_input:
            # if not user_input['servers']:
                # return await self.async_step_xiaomi_account(error='no_servers')

            session = aiohttp_client.async_create_clientsession(self.hass)
            cloud = MiCloud(session)
            if await cloud.login(user_input['username'],
                                 user_input['password']):
                user_input.update(cloud.auth)
                return self.async_create_entry(title=data_masking(user_input['username'], 4),
                                               data=user_input)

            else:
                return await self.async_step_xiaomi_account(error='cant_login')

        return self.async_show_form(
            step_id='xiaomi_account',
            data_schema=vol.Schema({
                vol.Required('username'): str,
                vol.Required('password'): str,
                # vol.Required('servers', default=['cn']):
                    # cv.multi_select(SERVERS)
            }),
            errors={'base': error} if error else None
        )

    async def async_step_xiaoai(self, user_input=None, error=None):
        errors = {}
        if user_input is not None:
            self._input2 = {**self._input2, **user_input}
            self._model = user_input[CONF_MODEL]
            # Line 240-270
            self._info = await guess_mp_from_model(self.hass, self._model)
            hint = ""
            if self._info and self._info.get('mapping') != "{}":
                hint += "\n根据您手动输入的 model，已经自动发现配置参数。\n如无特殊需要，无需修改下列内容。\n"
                devtype_default = self._info.get('device_type')

                # mp = f'''{{"{self._info.get('device_type')}":{self._info.get('mapping')}}}'''
                # prm = f'''{{"{self._info.get('device_type')}":{self._info.get('params')}}}'''

                mp = self._info.get('mapping')
                prm = self._info.get('params')
                mapping_default = mp
                params_default = prm
            else:
                hint += f"很抱歉，未能自动发现配置参数。但这不代表您的设备不受支持。\n您可以[手工编写配置](https://github.com/ha0y/xiaomi_miot_raw/#文件配置法)，或者将型号 **{self._model}** 报告给作者。"
                devtype_default = []
                mapping_default = '{"switch_status":{"siid":2,"piid":1}}'
                params_default = '{"switch_status":{"power_on":true,"power_off":false}}'


            return self.async_show_form(
                step_id="devinfo",
                data_schema=vol.Schema({
                    # vol.Required('devtype', default=devtype_default): vol.In(SUPPORTED_DOMAINS),
                    vol.Required('devtype', default=devtype_default): cv.multi_select(SUPPORTED_DOMAINS),
                    vol.Required(CONF_MAPPING, default=mapping_default): str,
                    vol.Required(CONF_CONTROL_PARAMS, default=params_default): str,
                    vol.Optional('cloud_read'): bool,
                    vol.Optional('cloud_write'): bool,
                }),
                description_placeholders={"device_info": hint},
                errors=errors,
            )

        return self.async_show_form(
            step_id='xiaoai',
            data_schema=vol.Schema({
                vol.Required(CONF_MODEL): str,
            }),
            errors={'base': 'no_connect_warning'}
        )
