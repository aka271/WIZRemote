class LightDevice:
    def __init__(
        self,
        ip,
        mac,
        homeId,
        roomId,
        moduleName,
        fwVersion,
        rssi=None,
        state=None,
        sceneId=None,
        dimming=None,
    ):
        self.ip = ip
        self.mac = mac
        self.homeId = homeId
        self.roomId = roomId
        self.moduleName = moduleName
        self.fwVersion = fwVersion
        self.rssi = rssi
        self.state = state
        self.sceneId = sceneId
        self.dimming = dimming

    def __repr__(self):
        return (f"<LightDevice ip={self.ip} mac={self.mac} "
                f"module={self.moduleName} fw={self.fwVersion} "
                f"state={self.state} dimming={self.dimming} scene={self.sceneId} rssi={self.rssi}>")
