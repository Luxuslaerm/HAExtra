
import json


def twins_split(twins, sep, default=None):
    pos = twins.find(sep)
    return (twins, default) if pos == -1 else (twins[0:pos], twins[pos + 1:])


def string_value(value):
    if value == 'none':
        return None
    elif value == 'false':
        return False
    elif value == 'true':
        return True
    else:
        return int(value)


def miio_cmd_help(arg0='?', did=None):
    if did:
        did_sufix = ''
    else:
        did = '267090026'
        did_sufix = '@' + did
    quote = '' if arg0 == '?' else "'"
    return f'\
Help Info: {arg0}help\n\
Devs List: {arg0}list\n\
Get Props: {arg0}1,1-2,1-3,1-4,2,3{did_sufix}\n\
Set Props: {arg0}2==60,2-2==false,3=test{did_sufix}\n\
Do Action: {arg0}{quote}["您好"]5{did_sufix}{quote}\n\
Do Action: {arg0}{quote}["天气",1]5-4{did_sufix}{quote}\n\
Call MIoT: {arg0}{quote}{{"did":"{did}","siid":5,"aiid":1,"in":["您好"]}}action{quote}\n\
Call MiIO: {arg0}{quote}{{"getVirtualModel":false,"getHuamiDevices":1}}/home/device_list{quote}'


async def miio_cmd(cloud, cmd, did=None):
    if cmd.startswith('{'):
        pos = cmd.rfind('}')
        if pos != -1:
            data = cmd[0:pos+1]
            uri = cmd[pos+1:]
            if uri.startswith('/'):
                return await cloud.miio(uri, data)
            return await cloud.miot_spec(uri, json.loads(data))

    elif cmd.startswith('['):
        pos = cmd.rfind(']')
        if pos != -1:
            iid, did = twins_split(cmd[pos+1:], '@', did)
            if did:
                siid, aiid = twins_split(iid, '-', 1)
                return await cloud.miot_action(did, int(siid), int(aiid), json.loads(cmd[0:pos+1]))

    elif cmd.startswith('list'):
        return await cloud.device_list()

    elif cmd == 'help' or cmd == '-h' or cmd == '--help':
        return miio_cmd_help()

    else:
        items, did = twins_split(cmd, '@', did)
        if did and items:
            props = []
            isget = False
            for item in items.split(','):
                iid, value = twins_split(item, '=')
                siid, piid = twins_split(iid, '-', 1)
                prop = [int(siid), int(piid)]
                if not isget:
                    if value is None:
                        isget = True
                    else:
                        prop.append(string_value(value[1:]) if value[0] == '=' else value)
                props.append(prop)
            result = await (cloud.miot_get_props if isget else cloud.miot_set_props)(did, props)
            return result

    return 'Corrupt parameter'
