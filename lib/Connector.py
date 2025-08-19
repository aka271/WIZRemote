import os
import json
import socket
import time

from lib.LightDevice import LightDevice
from lib.scene_dict import SCENES

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
MSG_DIR = BASE_DIR / "../" / "msg_files"

BROADCAST_IP = "255.255.255.255"
UDP_PORT = 38899



SCENE_DICT = {name: number for number, name in SCENES.items()}


class Connector:
    def __init__(self, bc_timeout=4):
        self.msg = {}
        self.sock = None
        self.sock_bc = None
        self.devices = []  # list to store LightDevice objects
        self._cache_msg()
        self._load_sock()
        self._load_bc_sock(bc_timeout)
        
        

                
    def _cache_msg(self):
        for filename in os.listdir(MSG_DIR):
            if filename.endswith('.json'):
                filepath = os.path.join(MSG_DIR, filename)
                with open(filepath, 'r') as f:
                    try:
                        key = filename[:-5]  # removes ".json"
                        self.msg[key] = json.load(f)
                    except json.JSONDecodeError as e:
                        print(f"Failed to load {filename}: {e}")

    def scan_for_devices(self):
        print("Scanning for wiz-light Devices")
        msg = json.dumps(self.msg["get_config"]).encode("utf-8")
        self.devices.clear()  # Clear old device list
        self.sock_bc.sendto(msg, (BROADCAST_IP, UDP_PORT))
        
        try:
            while True:
                data, addr = self.sock_bc.recvfrom(4096)
                ip = addr[0]
                try:
                    response = json.loads(data.decode('utf-8'))
                    pretty_response = json.dumps(response, indent=4)
                    print(f"Received from {addr}:\n{pretty_response}")

                    if "result" in response:
                        res = response["result"]
                        device = LightDevice(
                            ip=ip,
                            mac=res.get("mac", ""),
                            homeId=res.get("homeId", None),
                            roomId=res.get("roomId", None),
                            moduleName=res.get("moduleName", ""),
                            fwVersion=res.get("fwVersion", ""),
                        )
                        self.devices.append(device)
                except json.JSONDecodeError:
                    print(f"Received from {addr} (non-JSON):\n{data.decode('utf-8', errors='ignore')}")

        except socket.timeout:
            print("No more responses (timed out).")

            # Sort devices by IP
            self.devices.sort(key=lambda d: tuple(int(part) for part in d.ip.split(".")))

            # Automatically fetch pilot info for each discovered device
        for device in self.devices:
            self.get_pilot(device)

    
    def _load_bc_sock(self, timeout):
        self.sock_bc = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock_bc.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.sock_bc.settimeout(timeout)
        
    def _load_sock(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Instantiate Connector to scan and save devices
    def dimm_light(self, device, amount):
        print(f"Dimming light {device} to amount {amount}")
        msg = self.msg["dimming"]
        msg["params"]["dimming"] = amount
        msg = json.dumps(msg).encode("utf-8")
        self.sock.sendto(msg, (device, UDP_PORT))
        
        
    def turn_off_light(self, device):
        print(f"Turning light off {device}")
        msg = self.msg["turn_off"]
        msg = json.dumps(msg).encode("utf-8")
        self.sock.sendto(msg, (device, UDP_PORT))
        
    def turn_on_light(self, device):
        print(f"Turning light on {device}")
        msg = self.msg["turn_on"]
        msg = json.dumps(msg).encode("utf-8")
        self.sock.sendto(msg, (device, UDP_PORT))
        
        
    def rgb_color_light(self, device, r, g, b):
        print(f"Turning color of {device} to hex({r}, {g}, {b})")
        msg = self.msg["rgb_color"]
        msg["params"]["r"] = r
        msg["params"]["g"] = g
        msg["params"]["b"] = b
        msg = json.dumps(msg).encode("utf-8")
        self.sock.sendto(msg, (device, UDP_PORT))
        
        
    def change_scene(self, device, scene):
        print(f"Changing Scene of {device} to {scene}")
        msg = self.msg["scene"]
        sceneId = SCENE_DICT.get(scene)
        msg["params"]["sceneId"] = sceneId
        msg = json.dumps(msg).encode("utf-8")
        self.sock.sendto(msg, (device, UDP_PORT))
        
    def get_config(self, device):
        print(f"Getting config from {device}")
        
        # Send get_config request
        msg = json.dumps(self.msg["get_config"]).encode("utf-8")
        self.sock.sendto(msg, (device, UDP_PORT))

        # Set a timeout to avoid infinite blocking
        self.sock.settimeout(2)

        try:
            while True:
                data, addr = self.sock.recvfrom(4096)
                if addr[0] == device:
                    try:
                        response = json.loads(data.decode("utf-8"))
                        print(f"Response from {addr}:\n{json.dumps(response, indent=4)}")
                        return response  # You can return this or parse specific fields
                    except json.JSONDecodeError:
                        print(f"Received invalid JSON from {addr}")
                        return None
        except socket.timeout:
            print(f"No response from {device} (timeout)")
            return None
        
        
    def get_pilot(self, device_obj):
        device_ip = device_obj.ip
        print(f"Getting config from {device_ip}")

        # Send get_pilot request
        msg = json.dumps(self.msg["get_pilot"]).encode("utf-8")
        self.sock.sendto(msg, (device_ip, UDP_PORT))

        # Set a timeout to avoid infinite blocking
        self.sock.settimeout(2)

        try:
            while True:
                data, addr = self.sock.recvfrom(4096)
                if addr[0] == device_ip:
                    try:
                        response = json.loads(data.decode("utf-8"))
                        print(f"Response from {addr}:\n{json.dumps(response, indent=4)}")

                        result = response.get("result", {})

                        # Update LightDevice attributes
                        device_obj.rssi = result.get("rssi")
                        device_obj.state = result.get("state")
                        device_obj.sceneId = result.get("sceneId")
                        device_obj.dimming = result.get("dimming")

                        return response
                    except json.JSONDecodeError:
                        print(f"Received invalid JSON from {addr}")
                        return None
        except socket.timeout:
            print(f"No response from {device_ip} (timeout)")
            return None


""" x = Connector()


#test class
x.dimm_light("192.168.2.22", 20)
        
x.turn_on_light("192.168.2.22")
time.sleep(2)
x.turn_off_light("192.168.2.22")
time.sleep(2)
x.turn_on_light("192.168.2.22")

x.rgb_color_light("192.168.2.22", 255, 0, 0)
time.sleep(2)
x.rgb_color_light("192.168.2.22", 0, 255, 0)
time.sleep(2)
x.rgb_color_light("192.168.2.22", 0, 0, 255)

time.sleep(3)
x.change_scene("192.168.2.22", "Cozy")


x.turn_off_light("192.168.2.23") 
x.turn_off_light("192.168.2.24") """