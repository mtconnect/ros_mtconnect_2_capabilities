import os,sys

path = os.path.join(os.getenv('HOME'), 'capabilities/ros_mtconnect_2/simulator/src')

import xml.etree.ElementTree as ET
import uuid, re
import datetime, copy

class PPA:

    def __init__(self, part_archetype_uuid = None, process_archetype_uuid = None, initiate = True):

        self.uuid = part_archetype_uuid
        self.process_uuid = process_archetype_uuid
        self.part_instance_uuid = None

        self.part_archetype_root = str()
        self.part_instance_root = str()

        self.process_archetype_root = str()
        self.process_instance_root = str()

        self.archetype_json = str()

        self.instance_root = str()
        self.instance_json = dict()

        self.capabilities = dict()
        self.capabilities['REQUESTED'] = dict()
        self.capabilities['PROVIDED'] = dict()

        self.process_plan = dict()
        self.process_plan_instance = dict()
        self.updated_process_plan = dict()

        self.device_process = list()

        self.initialize(initiate)


    def initialize(self, initiate = True):
        if self.uuid and initiate:
            self.define_archetype()
            self.define_instance()
            self.required_capabilities()


    def read_asset(self, assetType = None, id = str()):
        if assetType:
            assets = assetType.split('_')
            assetType = str()
            for Type in assets:
                assetType = assetType + Type.title()

        try:
            file_open = open(os.path.join(path, 'partsProcessArchetype', assetType + id + '.xml'))
            file_read = file_open.read()
            root = ET.fromstring(file_read)

            return root.findall('.//'+root.tag.split('}')[0]+'}'+'Assets')[0][0]

        except Exception as e:
            print ("No archetypes found with uuid:",self.uuid,assetType,id)
            print ("Error:",e)

    def define_archetype(self):
        self.part_archetype_root = self.read_asset('PART_ARCHETYPE', '_' + str(self.uuid))

        if len(self.part_archetype_root.tag.split('}'))>1:
            self.xmlns = self.part_archetype_root.tag.split('}')[0]+'}'
        else:
            self.xmlns = str()

        self.process_archetype_root = self.read_asset('PROCESS_ARCHETYPE', '_' + str(self.uuid))


    def define_instance(self, assetType = None, asset = None):

        if assetType and asset:
            if assetType == "PartInstance":
                self.part_instance_root = ET.fromstring(asset)
                self.xmlns = self.part_instance_root.tag.split('}')[0]+'}'

                for ref in self.part_instance_root.find('AssetRefs'):
                    if ref.attrib['assetType'] == 'PartArchetype':
                        self.uuid = copy.deepcopy(ref.text)

                    elif ref.attrib['assetType'] == 'ProcessInstance':
                        self.process_uuid = copy.deepcopy(ref.text)

            return

        self.part_instance_root = self.read_asset('PART_INSTANCE')

        self.process_instance_root = self.read_asset('PROCESS_INSTANCE')

        self.instantiate_instances()


    def instantiate_instances(self):
        #Part Instance
        self.part_instance_root.attrib['assetId'] = str(uuid.uuid4())
        self.part_instance_root.attrib['timestamp'] = str(datetime.datetime.now().isoformat()+'Z')

        for ref in self.part_instance_root.find(self.xmlns+'AssetRefs'):

            if ref.attrib['assetType'] == 'PartArchetype':
                ref.text = self.part_archetype_root.find(self.xmlns+'Uuid').text

        #Process Instance
        self.process_instance_root.attrib['assetId'] = str(uuid.uuid4())
        self.process_instance_root.attrib['timestamp'] = str(datetime.datetime.now().isoformat()+'Z')

        for ref2 in self.process_instance_root.find(self.xmlns+'AssetRefs'):

            if ref2.attrib['assetType'] == 'ProcessArchetype':
                ref2.text = self.process_archetype_root.find(self.xmlns+'Uuid').text
                self.process_uuid = ref2.text


    def update_instance(self, type = 'PartInstance', assetId = None, element = None, text = None):
        if type == 'PartInstance':
            self.part_instance_root.find(self.xmlns+str(element)).text = text

        elif type == 'ProcessInstance':
            self.process_instance_root.find(self.xmlns+str(element)).text = text


    def required_capabilities(self):
        if self.process_archetype_root is str() and self.part_archetype_root is str(): return

        process_caps = self.process_archetype_root.find('.//'+self.xmlns+'Capabilities')
        if process_caps is not None:
            if self.process_uuid not in self.capabilities['REQUESTED']:
                self.capabilities['REQUESTED'][self.process_uuid] = {}
            self.traverse(self.capabilities['REQUESTED'][self.process_uuid],process_caps)

            self.first_process_cap_request()

        part_caps = self.part_archetype_root.find('.//'+self.xmlns+'Capabilities')
        if part_caps is not None:
            if self.uuid not in self.capabilities['REQUESTED']:
                self.capabilities['REQUESTED'][self.uuid] = {}
            self.traverse(self.capabilities['REQUESTED'][self.uuid],part_caps)


    def first_process_cap_request(self):
        cap = {}
        cap['DEVICE'] = {'TYPE':{}}
        cap['DEVICE']['TYPE']['subType'] = 'REQUESTED'
        cap['DEVICE']['TYPE']['type'] = 'TYPE'
        cap['DEVICE']['TYPE']['Value'] = ['CONVEYOR']
        self.capabilities['REQUESTED'][self.process_uuid]['PROCESS']['TYPE']['Value'].append('PROCESS_ARCHETYPE')
        self.capabilities['REQUESTED'][self.process_uuid]['PROCESS']['TYPE']['PROCESS_ARCHETYPE'] = cap


    def provided_capabilities(self, capabilities_root = None, device_uuid = None):
        if capabilities_root is None or device_uuid is None:
            return

        device_caps = capabilities_root
        if len(device_caps.tag.split('}'))>1:
            xmlns = device_caps.tag.split('}')[0]+'}'
        else:
            xmlns = str()

        if device_uuid not in self.capabilities['PROVIDED']:
            self.capabilities['PROVIDED'][device_uuid] = {}

        self.traverse(self.capabilities['PROVIDED'][device_uuid],device_caps, xmlns)


    def traverse(self, caps, asset_caps, xmlns = None):
        if xmlns is None:
            xmlns = self.xmlns

        key =  asset_caps.attrib['type']
        if key not in caps:
            caps[key] = {}

        for cap in asset_caps:
            if cap.attrib['type'] not in caps[key]:
                caps[key][cap.attrib['type']] = {}    

            for values in cap.getchildren():
                tag = values.tag.split('}')[-1]
                if tag == 'Capabilities': continue

                if tag not in caps[key][cap.attrib['type']]:
                    caps[key][cap.attrib['type']][tag] = [values.text]
                else:
                    caps[key][cap.attrib['type']][tag].append(values.text)

            for attrib in cap.attrib:

                caps[key][cap.attrib['type']][attrib] = cap.attrib[attrib]


            if cap.find('.//'+xmlns+'Capabilities') is not None:

                caps[key][cap.attrib['type']][cap.find('.//'+xmlns+'Value').text] = {}

                self.traverse(
                    caps[key][cap.attrib['type']][cap.find('.//'+xmlns+'Value').text],
                    cap.find('.//'+xmlns+'Capabilities'),
                    xmlns
                    )

    def process_plan_archetype(self):
        process_plan_root = self.process_archetype_root.findall('.//'+self.xmlns+'ProcessPlan')[0]

        for process_step in process_plan_root:

            process_archetype = process_step.find('.//'+self.xmlns+'ProcessArchetype').text

            process_archetype_root = self.read_asset(process_archetype)

            self.process_plan[process_archetype] = {}

            self.process_plan[process_archetype]['TargetMachine'] = process_archetype_root.findall('.//'+self.xmlns+'TargetMachine')[0].text


            self.process_plan[process_archetype]['ActualDevice'] = list()


            for elem in process_step.getchildren():
                self.process_plan[process_archetype][elem.tag.split('}')[-1]] = elem.text


    def update_process_plan(self, process_archetype = None, key = None, val = None):
        if self.process_plan.has_key(process_archetype) and key and val:
            self.process_plan[process_archetype][key] = val

        elif not self.process_plan.has_key(process_archetype):
            self.process_plan[process_archetype] = {}
            self.process_plan[process_archetype]['TargetMachine'] = list()
            self.process_plan[process_archetype]['ActualDevice'] = list()
            self.process_plan[process_archetype]['OperationNumber'] = 'OPTIONAL'
            self.process_plan[process_archetype]['ProcessArchetype'] = process_archetype


    def gen_dict_extract(self, key, var):
        if hasattr(var,'iteritems'):
            for k, v in var.iteritems():
                if k == key:
                    yield v
                if isinstance(v, dict):
                    for result in self.gen_dict_extract(key, v):
                        yield result
                elif isinstance(v, list):
                    for d in v:
                        for result in self.gen_dict_extract(key, d):
                            yield result


    def part_capability_assessment(self):
        # part assessment
        part_cap = self.capabilities['REQUESTED'][self.uuid]['PART']
        devices = self.capabilities['PROVIDED'].keys()

        device_cap = self.capabilities['PROVIDED']

        device_capable = True
        devices_capable = []
        for device in devices:

            for cap in part_cap:

                try:
                    provided_cap = self.gen_dict_extract(cap,device_cap[device]).next()

                except Exception as e:
                    if type(e) == StopIteration:
                        device_capable = False
                        break

                if part_cap[cap]['type'] == 'TYPE':
                    if part_cap[cap]['Value'][0] not in provided_cap['Value']:
                        device_capable = False
                        break

                elif 'units' in part_cap[cap]:
                    if 'Value' in provided_cap and float(part_cap[cap]['Value'][0]) >= float(provided_cap['Value'][0]):
                        if ('Maximum' or 'Minimum') not in provided_cap:
                            device_capable = False
                            break

                    if ('Maximum' or 'Minimum') in provided_cap:
                        if 'Maximum' in provided_cap:
                            if float(part_cap[cap]['Value'][0]) > float(provided_cap['Maximum'][0]):
                                device_capable = False
                                break
                        if 'Minimum' in provided_cap:
                            if float(part_cap[cap]['Value'][0]) < float(provided_cap['Minimum'][0]):
                                device_capable = False
                                break

                else:
                    if part_cap[cap]['Value'][0] not in provided_cap['Value'] and provided_cap['Value'][0]!='ALL':
                        device_capable = False
                        break


            if device_capable:
                devices_capable.append(device)
            else:
                device_capable = True

        return devices_capable


    def process_capability_assessment(self, proc_cap_list = list(), device_uuid = None):

        devices = self.part_capability_assessment()
        devices_out = copy.deepcopy(devices)

        device_cap = self.capabilities['PROVIDED']

        process_cap = self.capabilities['REQUESTED'][self.process_uuid]

        device_capable = True

        proc_cap_list = list()
        cap_list = list()

        for k,v in process_cap.iteritems():

            for val in v.values()[0]['Value']:
                cap_list.append([k,v.keys()[0],[val]])

                self.cap_traverse(v.values()[0][val],cap_list)

                proc_cap_list.append(cap_list)
                cap_list = list()

        for steps in proc_cap_list:

            for device in devices:

                for cap in steps:

                    try:
                        provided_cap = self.gen_dict_extract(cap[0],device_cap[device]).next()

                    except Exception as e:
                        if type(e) == StopIteration:
                            device_capable = False
                            break

                    if cap[2]:
                        flag = False
                        for dev in cap[2]:
                            if dev in provided_cap[cap[1]]['Value']:
                                flag = True
                        if not flag:
                            device_capable = False
                            break

                if not device_capable:
                    devices_out.remove(device)
                    device_capable = True


            if not self.process_plan.has_key(steps[0][2][0]):
                self.update_process_plan(steps[0][2][0])


            process_archetype_root = self.read_asset(steps[0][2][0])

            self.update_process_plan(
                steps[0][2][0],
                'TargetMachine',
                process_archetype_root.findall('.//'+self.xmlns+'TargetMachine')[0].text
                )

            if devices_out:
                if self.device_uuid in devices_out:
                    self.device_process.append(steps[0][2][0])
                self.update_process_plan(steps[0][2][0], 'ActualDevice', devices_out)
                        

            devices_out = copy.deepcopy(devices)


    def cap_traverse(self, caps_req = dict(), cap = list()):
        for k,v in caps_req.iteritems():
            if isinstance(v,dict) and v.values()[0].has_key('Value') and not v.values()[0].has_key('units'):
                cap.append([k,v.keys()[0],v.values()[0]['Value']])

                for x in v.values()[0].keys():
                    if x in v.values()[0]['Value']:
                        self.cap_traverse(v.values()[0][x], cap)
        return cap


    def complete_process_plan(self):
        self.process_plan = dict()
        self.device_process = list()
        self.process_plan_archetype()
        self.process_capability_assessment()

        self.update_process_plan('PROCESS_ARCHETYPE','TargetMachine', 'CONVEYOR')
        self.update_process_plan('PROCESS_ARCHETYPE','OperationNumber', '00')

        complete_process_plan = []
        for key, val in self.process_plan.iteritems():
            if val['OperationNumber'].isdigit():
                complete_process_plan.append([int(val['OperationNumber']), key, val])

        complete_process_plan.sort()

        last_operation_number = None
        for steps in reversed(complete_process_plan):
            if steps[0]:
                last_operation_number = steps[0]
                break

        updates_to_process_plan = []

        for i,x in enumerate(complete_process_plan):

            if i<(len(complete_process_plan)-1):

                if len(x[2]['ActualDevice']) > 0:

                    if x[2]['ActualDevice'][0] not in complete_process_plan[i+1][2]:
                        operation_number = int((float(x[0])+float(complete_process_plan[i+1][0]))/2)
                        process_archetype = copy.deepcopy(self.process_plan['MOVE'])
                        process_archetype['OperationNumber'] = str(operation_number)

                        updates_to_process_plan.append([operation_number,'MOVE',process_archetype])

            elif x[0] == last_operation_number:

                if x[1] != 'PROCESS_ARCHETYPE':
                    operation_number = int(float(x[0])+5)
                    process_archetype = copy.deepcopy(self.process_plan['MOVE'])
                    process_archetype['OperationNumber'] = str(operation_number)

                    updates_to_process_plan.append([operation_number,'MOVE',process_archetype])

                    operation_number = int()
                    operation_number = int(float(x[0])+10)
                    process_archetype = copy.deepcopy(self.process_plan['PROCESS_ARCHETYPE'])
                    process_archetype['OperationNumber'] = str(operation_number)

                    updates_to_process_plan.append([operation_number,'PROCESS_ARCHETYPE',process_archetype])

        if updates_to_process_plan:
            complete_process_plan = complete_process_plan + updates_to_process_plan

        complete_process_plan.sort()

        if last_operation_number:
            self.process_plan_instance = complete_process_plan


    def update_asset_instance(self, assetIns = None, dataitem = None, value = None):
        if type(assetIns) == ET.Element:
            xmlns = assetIns.tag.split('}')
            if len(xmlns)>1:
                xmlns = assetIns.tag.split('}')[0]+'}'
            else:
                xmlns = str()
            if assetIns.findall('.//'+xmlns+dataitem)[0].text != value:
                assetIns.attrib['timestamp'] = datetime.datetime.now().isoformat() + 'Z'
                assetIns.findall('.//'+xmlns+dataitem)[0].text = value
            return assetIns
        else:
            assetIns = ET.fromstring(assetIns)
            xmlns = assetIns.tag.split('}')
            if len(xmlns)>1:
                xmlns = assetIns.tag.split('}')[0]+'}'
            else:
                xmlns = str()
            if assetIns.findall('.//'+xmlns+dataitem)[0].text != value:
                assetIns.attrib['timestamp'] = datetime.datetime.now().isoformat() + 'Z'
                assetIns.findall('.//'+xmlns+dataitem)[0].text = value
            return ET.tostring(assetIns)


    def create_asset_instance(self, device_cap = None, device_uuid = None):
        self.device_process = list()
        self.device_uuid = device_uuid

        self.provided_capabilities(device_cap,device_uuid)

        if device_uuid:
            self.process_capability_assessment(device_uuid = device_uuid)

        self.complete_process_plan()

        for i,process in enumerate(self.process_plan_instance):
            if process[1] in self.device_process:
                break

        self.current_process = process

        process_archetype = self.read_asset(process[1])

        process_instance = self.read_asset('PROCESS_INSTANCE')
        asset_refs = process_instance.findall('.//'+self.xmlns+'AssetRef')

        for asset in asset_refs:
            if asset.attrib['assetType'] == 'ProcessArchetype' and self.process_uuid:
                asset.text = process_archetype.findall('.//'+self.xmlns+'Uuid')[0].text

            elif asset.attrib['assetType'] == 'PartInstance' and self.part_instance_uuid:
                asset.text = self.part_instance_uuid
        
        process_instance = self.update_asset_instance(process_instance, 'ActualDevice', process[2]['ActualDevice'][0])        
        process_instance = self.update_asset_instance(process_instance, 'Uuid', str(uuid.uuid4()))

        return process_instance


    def next_process(self, current_process = None):
        for i,process in enumerate(self.process_plan_instance):

            if current_process and process[1] == current_process and i<(len(self.process_plan_instance)-1):
                return self.process_plan_instance[i+1]

            elif not current_process and process[1] in self.device_process and i<(len(self.process_plan_instance)-1):
                return self.process_plan_instance[i+1]

        return


if __name__ == '__main__':
    a = PPA(str(123))
    b=ET.fromstring(open('/home/ssingh/capabilities/ros_mtconnect_2/simulator/src/deviceFiles/combined.xml').read())

    b_xmlns = b.tag.split('}')[0]+'}'

    c = b.findall('.//'+b_xmlns+'Device')

    #for x in c:
    #    a.provided_capabilities(x.findall('.//'+b_xmlns+'Capabilities')[0], x.attrib['uuid'])

    #a.provided_capabilities(c[0].findall('.//'+b_xmlns+'Capabilities')[0], c[0].attrib['uuid'])

