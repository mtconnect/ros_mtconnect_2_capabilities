"""
Sample module for implementing a robot that coordinates with a CNC and conveyors.
"""

from material import *
from door import *
from chuck import *
from coordinator import *
from collaborator import *
from mtconnect_adapter import Adapter
from long_pull import LongPull
from data_item import Event, SimpleCondition, Sample, ThreeDSample
from archetypeToInstance import archetypeToInstance
from from_long_pull import from_long_pull, from_long_pull_asset

from transitions.extensions import HierarchicalMachine as Machine
from transitions.extensions.nesting import NestedState
from threading import Timer, Thread
import functools, time, re, datetime
import requests, urllib2, collections
import xml.etree.ElementTree as ET


RobotEvent = collections.namedtuple('RobotEvent', ['source', 'component', 'name', 'value', 'code', 'text'])

class Robot:
    class StateModel:
        """The model for MTConnect behavior in the robot."""
        def __init__(self):

            self.initiate_adapter('localhost',7961)
            self.adapter.start()
            self.initiate_dataitems()

            self.initiate_interfaces()

            self.events = []

            self.master_tasks ={}

            self.deviceUuid = "r1"

            self.material_load_interface.superstate.simulated_duration = 20
            self.material_unload_interface.superstate.simulated_duration = 20

            self.master_uuid = str()

            self.iscoordinator = False
            
            self.iscollaborator = True

            self.fail_next = False

            self.initiate_pull_thread()

        def initiate_interfaces(self):
            self.material_load_interface = MaterialLoadResponse(self)
            self.material_unload_interface = MaterialUnloadResponse(self)
            self.open_chuck_interface = OpenChuckRequest(self)
            self.close_chuck_interface = CloseChuckRequest(self)
            self.open_door_interface = OpenDoorRequest(self)
            self.close_door_interface = CloseDoorRequest(self)
            
        def initiate_adapter(self, host, port):
            self.adapter = Adapter((host,port))

            self.mode1 = Event('mode')
            self.adapter.add_data_item(self.mode1)

            self.e1 = Event('exec')
            self.adapter.add_data_item(self.e1)

            self.avail1 = Event('avail')
            self.adapter.add_data_item(self.avail1)

            self.binding_state_material = Event('binding_state_material')
            self.adapter.add_data_item(self.binding_state_material)

            self.open_chuck = Event('open_chuck')
            self.adapter.add_data_item(self.open_chuck)

            self.close_chuck = Event('close_chuck')
            self.adapter.add_data_item(self.close_chuck)

            self.open_door = Event('open_door')
            self.adapter.add_data_item(self.open_door)

            self.close_door = Event('close_door')
            self.adapter.add_data_item(self.close_door)

            self.material_load = Event('material_load')
            self.adapter.add_data_item(self.material_load)

            self.material_unload = Event('material_unload')
            self.adapter.add_data_item(self.material_unload)

            self.material_state = Event('material_state')
            self.adapter.add_data_item(self.material_state)

        def initiate_dataitems(self):
            self.adapter.begin_gather()

            self.avail1.set_value("AVAILABLE")
            self.e1.set_value("READY")
            self.mode1.set_value("AUTOMATIC")
            self.binding_state_material.set_value("INACTIVE")
            self.open_chuck.set_value("NOT_READY")
            self.close_chuck.set_value("NOT_READY")
            self.open_door.set_value("NOT_READY")
            self.close_door.set_value("NOT_READY")
            self.material_load.set_value("NOT_READY")
            self.material_unload.set_value("NOT_READY")
            self.material_state.set_value("UNLOADED")

            self.adapter.complete_gather()

        def initiate_pull_thread(self):

            thread= Thread(target = self.start_pull,args=("http://localhost:5000","/cnc/sample?interval=100&count=1000",from_long_pull))
            thread.start()

            thread2= Thread(target = self.start_pull,args=("http://localhost:5000","/conv/sample?interval=100&count=1000",from_long_pull))
            thread2.start()
            
        def interface_type(self, value = None, subtype = None):
            self.interfaceType = value

        def start_pull(self,addr,request, func, stream = True):

            response = requests.get(addr+request, stream=stream)
            lp = LongPull(response, addr, self)
            lp.long_pull(func)

        def start_pull_asset(self, addr, request, assetId, stream_root):
            response = urllib2.urlopen(addr+request).read()
            from_long_pull_asset(self, response, stream_root)


        def ACTIVATE(self):
            self.make_operational()
            self.open_chuck_interface.superstate.start()
            self.close_chuck_interface.superstate.start()
            self.open_door_interface.superstate.start()
            self.close_door_interface.superstate.start()

        def OPERATIONAL(self):
            self.make_idle()

        def IDLE(self):
            self.material_unload_interface.superstate.not_ready()
            self.material_load_interface.superstate.not_ready()
            self.master_tasks = {}
            self.collaborator = collaborator(parent = self, interface = self.binding_state_material, collaborator_name = 'r1')
            self.collaborator.create_statemachine()
            self.collaborator.superstate.unavailable()

        def LOADING(self):
            self.material_unload_interface.superstate.not_ready()
            self.material_load_interface.superstate.ready()

        def UNLOADING(self):
            self.material_load_interface.superstate.not_ready()
            self.material_unload_interface.superstate.ready()

        def LOADING_COMPLETE(self):
            self.CHECK_COMPLETION()

        def CHECK_COMPLETION(self):
            #temporary fix till task/subtask sequencing is determined
            while self.master_tasks[self.master_uuid]['collaborators'][self.deviceUuid]['state'][2] != 'COMPLETE':
                pass
                

        def UNLOADING_COMPLETE(self):
            """self.material_unload_interface.superstate.not_ready()"""

        def LOAD_READY(self):
            """Function triggered when the CNC is ready to be loaded"""
            #TODO: verify that it's ok to start loading
            "self.loading()"

        def UNLOAD_READY(self):
            """Function triggered when the CNC is ready to be unloaded"""
            #TODO: verify that it's ok to start unloading
            "self.unloading()"

        def COMPLETED(self):
            if "request" in self.interfaceType.lower():
                "self.complete()" #What to do with the requests!?
            elif "response" in self.interfaceType.lower() and "material" in self.interfaceType.lower():
                if "unloaded" not in self.interfaceType.lower():
                    self.material_state.set_value("LOADED")
                    self.event(self.deviceUuid, 'material_interface', 'SubTask_'+'MaterialUnload','COMPLETE')
                elif "unloaded" in self.interfaceType.lower():
                    self.material_state.set_value("UNLOADED")
                    self.event(self.deviceUuid, 'material_interface', 'SubTask_'+'MaterialLoad','COMPLETE')

        def event(self, source, comp, name, value, code = None, text = None):
            """Process events.

            :type ev: .event.Event
            """
            #print "\nROBOT Event Enter",source,comp,name,value,datetime.datetime.now().isoformat()
            ev = RobotEvent(source, comp, name, value, code, text)

            #print('Robot received: ', source, comp, name, value)
            self.events.append(ev)

            action = value.lower()

            if "Collaborator" in comp and action!='unavailable':
                self.coordinator.superstate.event(source, comp, name, value, code, text)

            elif "Coordinator" in comp and action!='unavailable':
                self.collaborator.superstate.event(source, comp, name, value, code, text)

            elif 'SubTask' in name and action!='unavailable':
                
                if self.iscoordinator == True:
                    self.coordinator.superstate.event(source, comp, name, value, code, text)

                elif self.iscollaborator == True:
                    if 'BindingState' in comp and value.lower() == 'committed' and text == self.master_tasks[self.master_uuid]['coordinator'].keys()[0]:
                        #self.collaborator.superstate.event(source, 'MaterialHandlerInterface', 'SubTask_MaterialUnload', 'ACTIVE', code, text)
                        if self.material_state.value() == "LOADED":
                            #print "material state is ",self.material_state.value()
                            self.material_load_ready()
                        else:
                            #print "material state IS ",self.material_state.value()
                            self.material_unload_ready()
                    elif text == self.deviceUuid:
                        check = False
                        for x in self.master_tasks[self.master_uuid]['collaborators'][self.deviceUuid]['SubTask'][name.split('_')[-1]]:
                            if x[2] != None:
                                check = True
                            else:
                                break
                        if check:
                            for k,v in self.master_tasks[self.master_uuid]['coordinator'][self.master_tasks[self.master_uuid]['coordinator'].keys()[0]]['SubTask'].iteritems():
                                if v and v[0] == name.split('_')[-1]:
                                    self.master_tasks[self.master_uuid]['coordinator'][self.master_tasks[self.master_uuid]['coordinator'].keys()[0]]['SubTask'][k][1] = 'COMPLETE'

                    elif 'Door' in name or 'Chuck' in name:
                        #to be done in the lowlevel robot operation.
                        if self.collaborator.superstate.currentSubTask and action!='idle':# and name.split('_')[-1] in self.collaborator.superstate.currentSubTask: check it later
                            if 'Chuck' in name:
                                if 'Open' in name:
                                    if 'not_ready' in self.open_chuck_interface.superstate.state:
                                        self.open_chuck_interface.superstate.idle()
                                elif 'Close' in name:
                                    if 'not_ready' in self.close_chuck_interface.superstate.state:
                                        self.close_chuck_interface.superstate.idle()
                            elif 'Door' in name:
                                if 'Open' in name:
                                    if 'not_ready' in self.open_door_interface.superstate.state:
                                        self.open_door_interface.superstate.idle()
                                elif 'Close' in name:
                                    if 'not_ready' in self.close_door_interface.superstate.state:
                                        self.close_door_interface.superstate.idle()
                        check = False
                        for k,v in self.master_tasks[self.master_uuid]['coordinator'][self.master_tasks[self.master_uuid]['coordinator'].keys()[0]]['SubTask'].iteritems():
                            if v:
                                if v[0] == name.split('_')[-1] and v[1] != None:
                                    check == True
                                else:
                                    break
                        if check:
                            self.collaborator.superstate.event(source, comp, name, value, code, text)
                            time.sleep(0.1)
                            self.collaborator.superstate.event('robot', comp, name, value, self.master_uuid, self.deviceUuid) #(robot, some_interface, SubTask_MaterialLoad/Unload, 'COMPLETE', self.master_uuid, self.deviceUuid)
                        else:
                            self.collaborator.superstate.event(source, comp, name, value, code, text)

                    else:
                        self.collaborator.superstate.event(source, comp, name, value, code, text)


            elif ev.name.startswith('Material') and action!='unavailable':
                #print "in material method"
                self.material_event(ev)

            elif ('Chuck' in name or 'Door' in name) and action!='unavailable':
                                                                             
                if 'Chuck' in name:
                    if 'Open' in name:
                        eval('self.open_chuck_interface.superstate.'+action+'()')
                    elif 'Close' in name:
                        eval('self.close_chuck_interface.superstate.'+action+'()')
                elif 'Door' in name:
                    if 'Open' in name:
                        eval('self.open_door_interface.superstate.'+action+'()')
                    elif 'Close' in name:
                        eval('self.close_door_interface.superstate.'+action+'()')
                    

            #elif ev.component.startswith('Controller'):
                #self.controller_event(ev)

            #elif ev.component.startswith('Device'):
                #self.device_event(ev)

            else:
                """#print('Unknown event: ' + str(ev))"""

            #print "\nRobotEvent Exit",source,comp,name,value,datetime.datetime.now().isoformat()
        def material_event(self, ev):
            if ev.name == "MaterialLoad":
                if self.state == 'base:operational:idle':
                    self.material_load_ready()
                #print ev.value.lower()
                if ev.value.lower() == 'complete':
                    self.complete()
                else:
                    eval('self.material_load_interface.superstate.'+ev.value.lower()+'()')

            elif ev.name == "MaterialUnload":
                if self.state == 'base:operational:idle':
                    self.material_unload_ready()
                #print ev.value.lower()
                if ev.value.lower() == 'complete':
                    self.complete()
                else:
                    eval('self.material_unload_interface.superstate.'+ev.value.lower()+'()')

            else:
                """#print "raise(Exception('Unknown Material event: ' + str(ev)))'"""

        def controller_event(self, ev):
            if ev.name == "ControllerMode":
                if ev.source.lower() == 'robot':
                    
                    self.adapter.begin_gather()
                    self.mode1.set_value(ev.value.upper())
                    self.adapter.complete_gather()
                    
            elif ev.name == "Execution":
                if ev.source.lower() == 'robot':
                    
                    self.adapter.begin_gather()
                    self.e1.set_value(ev.value.upper())
                    self.adapter.complete_gather()
                    
            else:
                """raise(Exception('Unknown Controller event: ' + str(ev)))"""


        def device_event(self, ev):
            if ev.name == 'Availability':
                if ev.source.lower() == 'robot':
                    
                    self.adapter.begin_gather()
                    self.avail1.set_value(ev.value.upper())
                    self.adapter.complete_gather()
                #exec('self.'+ev.source.lower()+'_availability_'+value.lower()+'()')

            else:
                raise(Exception('Unknown Device event: ' + str(ev)))


        #end StateModel class definition

    def __init__(self):
        self.superstate = Robot.StateModel()
        self.statemachine = self.create_state_machine(self.superstate)

    def draw(self):
        print("Creating robot.png diagram")
        self.statemachine.get_graph().draw('robot.png', prog='dot')

    @staticmethod
    def create_state_machine(state_machine_model):
        """Create and initialize the robot state machine"""

        NestedState.separator = ':'
        states = [
            {
                'name': 'base',
                'children': [
                    'activated',
                    {
                        'name': 'operational',
                        'children': ['idle', 'loading', 'unloading']
                    },
                    {
                        'name': 'disabled',
                        'children': [
                            'not_ready',
                            {
                                'name': 'fault',
                                'children': ['software', 'hardware', 'e_stop']
                            },
                        ]
                    },
                ]
            }
        ]

        transitions = [
            ['start', 'base', 'base:disabled:not_ready'],
            ['activate', 'base:disabled:not_ready', 'base:activated'],
            ['make_operational', 'base:activated', 'base:operational'],
            ['make_idle', 'base:operational', 'base:operational:idle'],
            
            ['enable', 'base', 'base:activated'],

            ['safety_violation', 'base', 'base:disabled:soft'],
            ['collision', 'base', 'base:disabled:fault:soft'],
            ['hard_fault', 'base', 'base:disable:fault:hard'],
            ['e_stop', 'base', 'base:disabled:fault:e_stop'],
            ['clear_fault', 'base:disabled:fault', 'base:disabled:not_ready'],

            {
                'trigger': 'material_unload_ready',
                'source': 'base:operational:idle',
                'dest': 'base:operational:unloading',
                'after': 'UNLOAD_READY'
            },
            {
                'trigger': 'material_load_ready',
                'source': 'base:operational:idle',
                'dest': 'base:operational:loading',
                'after': 'LOAD_READY'
            },
            {
                'trigger': 'complete',
                'source': 'base:operational:loading',
                'dest': 'base:operational:idle',
                'before': 'LOADING_COMPLETE'
            },
            {
                'trigger': 'complete',
                'source': 'base:operational:unloading',
                'dest': 'base:operational:loading',
                'after': 'UNLOADING_COMPLETE'
            },

        ]

        statemachine = Machine(
            model = state_machine_model,
            states = states,
            transitions = transitions,
            initial = 'base',
            ignore_invalid_triggers=True
        )

        statemachine.on_enter('base:activated', 'ACTIVATE')
        statemachine.on_enter('base:operational', 'OPERATIONAL')
        statemachine.on_enter('base:operational:idle','IDLE')
        #statemachine.on_enter('base:operational:cycle_start', 'CYCLING')
        statemachine.on_enter('base:operational:loading', 'LOADING')
        statemachine.on_enter('base:operational:unloading', 'UNLOADING')

        return statemachine

if __name__ == '__main__':
    robot1 = Robot()
    time.sleep(1)
    robot1.superstate.enable()
