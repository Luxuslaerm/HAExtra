import asyncio
import json
import logging
from functools import partial

from datetime import timedelta
from collections import OrderedDict
import json
from collections import OrderedDict
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.switch import PLATFORM_SCHEMA, SwitchEntity
from homeassistant.const import *
from homeassistant.exceptions import PlatformNotReady
from miio.device import Device
from miio.exceptions import DeviceException
from miio.miot_device import MiotDevice

from . import ToggleableMiotDevice, MiotSubToggleableDevice
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
    SCHEMA,
    MAP
)
import copy

TYPE = 'switch'

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Generic MIoT " + TYPE
DATA_KEY = TYPE + '.' + DOMAIN
SCAN_INTERVAL = timedelta(seconds=10)
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    SCHEMA
)
# pylint: disable=unused-argument
@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the sensor from config."""
    if DATA_KEY not in hass.data:
        hass.data[DATA_KEY] = {}

    host = config.get(CONF_HOST)
    token = config.get(CONF_TOKEN)
    mapping = config.get(CONF_MAPPING)
    params = config.get(CONF_CONTROL_PARAMS)

    mappingnew = {}

    main_mi_type = None
    other_mi_type = []

    for t in MAP[TYPE]:
        if mapping.get(t):
            other_mi_type.append(t)
        if 'main' in (params.get(t) or ""):
            main_mi_type = t

    try:
        other_mi_type.remove(main_mi_type)
    except:
        pass

    if main_mi_type or type(params) == OrderedDict:
        for k,v in mapping.items():
            for kk,vv in v.items():
                mappingnew[f"{k[:10]}_{kk}"] = vv

        _LOGGER.info("Initializing %s with host %s (token %s...)", config.get(CONF_NAME), host, token[:5])

        try:
            if type(params) == OrderedDict:
                miio_device = MiotDevice(ip=host, token=token, mapping=mapping)
            else:
                miio_device = MiotDevice(ip=host, token=token, mapping=mappingnew)
            device_info = miio_device.info()
            model = device_info.model
            _LOGGER.info(
                "%s %s %s detected",
                model,
                device_info.firmware_version,
                device_info.hardware_version,
            )

            device = MiotSwitch(miio_device, config, device_info, hass, main_mi_type)
        except DeviceException as de:
            _LOGGER.warn(de)
            raise PlatformNotReady

        _LOGGER.info(f"{main_mi_type} is the main device of {host}.")
        hass.data[DOMAIN]['miot_main_entity'][host] = device
        hass.data[DOMAIN]['entities'][device.unique_id] = device
        async_add_devices([device], update_before_add=True)
    if other_mi_type:
        parent_device = None
        try:
            parent_device = hass.data[DOMAIN]['miot_main_entity'][host]
        except KeyError:
            _LOGGER.warning(f"{host} 的主设备尚未就绪，子设备 {TYPE} 等待主设备加载完毕后才会加载")
            raise PlatformNotReady

        # _LOGGER.error( parent_device.device_state_attributes)

        for k,v in mapping.items():
            if k in MAP[TYPE]:
                for kk,vv in v.items():
                    mappingnew[f"{k[:10]}_{kk}"] = vv

        devices = []
        for item in other_mi_type:
            devices.append(MiotSubSwitch(parent_device, mapping.get(item), params.get(item), item))
        async_add_devices(devices, update_before_add=True)


async def async_setup_entry(hass, config_entry, async_add_entities):
    config = copy.copy(hass.data[DOMAIN]['configs'].get(config_entry.entry_id, dict(config_entry.data)))
    # config[CONF_MAPPING] = config[CONF_MAPPING][TYPE]
    # config[CONF_CONTROL_PARAMS] = config[CONF_CONTROL_PARAMS][TYPE]
    await async_setup_platform(hass, config, async_add_entities)

class MiotSwitch(ToggleableMiotDevice, SwitchEntity):
    def __init__(self, device, config, device_info, hass, main_mi_type):
        ToggleableMiotDevice.__init__(self, device, config, device_info, hass, main_mi_type)


class MiotSubSwitch(MiotSubToggleableDevice, SwitchEntity):
    pass