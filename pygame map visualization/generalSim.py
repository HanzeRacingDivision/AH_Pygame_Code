from Map import Map
import coneConnecting as CC
import pathFinding    as PF
import pathPlanningTemp as PP
import simulatedCar   as SC
import carMCUclass    as RC
import drawDriverless as DD
import mapTransSock   as MS

import time
#import numpy as np

import threading as thr

## copyExtractMap() is moved to mapTransSock, you can still call it with MS.copyExtractMap()

class pygamesimLocal(CC.coneConnecter, PF.pathFinder, PP.pathPlanner, DD.pygameDrawer):
    def __init__(self, window, drawSize=(700,350), drawOffset=(0,0), carCamOrient=0, sizeScale=120, startWithCarCam=False, invertYaxis=True):
        Map.__init__(self) #init map class
        
        #self.clockSet(SC.simClockExample) #an altered clock, only for simulations where the speed is faster/slower than normal
        self.car = SC.simCar(self) #simCar has Map.Car as a parent class, so all regular Car stuff will still work
        
        #self.car = RC.realCar(comPort='COM8')
        
        CC.coneConnecter.__init__(self)
        PF.pathFinder.__init__(self)
        PP.pathPlanner.__init__(self)
        DD.pygameDrawer.__init__(self, self, window, drawSize, drawOffset, carCamOrient, sizeScale, startWithCarCam, invertYaxis)
        #tell the drawing class which parts are present
        self.coneConnecterPresent = True
        self.pathFinderPresent = True
        self.pathPlanningPresent = True
        self.SLAMPresent = False
        
        self.isRemote = False #tell the drawing class to apply UI elements locally
        
        #self.carPolygonMode = True #if you dont want to use the car sprite, set this to true (but if the sprite wasnt loaded this will be used automatically)
        
        if(self.pathPlanningPresent):
            self.car.pathFolData = PP.pathPlannerData()
        
        #self.mapList = [copyExtractMap(self)]


resolution = [1200, 600]

DD.pygameInit(resolution)
sim1 = pygamesimLocal(DD.window, resolution)

timeSinceLastUpdate = sim1.clock()
FPSlimitTimer = sim1.clock()
#mapSaveTimer = sim1.clock()
print("printing serial ports:")
[print(entry.name) for entry in RC.serial.tools.list_ports.comports()]
print("done printing ports.")
print()

try:
    mapSender = MS.mapTransmitterSocket(host='', port=65432, objectWithMap=sim1)
    mapSender.mapSendInterval = 0.2 #start safe, you can bring this number down if the connection is good (FPS = 1/this)
    threadKeepRunning = [True] #an argument (functional pointer) shared between the main and mapSockThread and main thread
    autoMapSend = [True] #an argument (functional pointer) shared between the main and mapSockThread and main thread
    UIreceive = [True] #an argument (functional pointer) shared between the main and mapSockThread and main thread
    mapSockThread = thr.Thread(target=mapSender.runOnThread, name="mapSockThread", args=(threadKeepRunning, autoMapSend, UIreceive), daemon=True)
    mapSockThread.start()
    ##note: mapSender.manualSendBuffer is a list to which you can append things (any object) to be sent to the connected client (if any)
    
    while DD.windowKeepRunning:
        FPSrightNow = sim1.clock() #this is only for the framerate limiter (time.sleep() doesn't accept negative numbers, this solves that)
        rightNow = sim1.clock()
        dt = rightNow - timeSinceLastUpdate
        DD.handleAllWindowEvents(sim1) #handle all window events like key/mouse presses, quitting and most other things
        
        if((sim1.car.pathFolData.auto) if (sim1.pathPlanningPresent and (sim1.car.pathFolData is not None)) else False):
            sim1.calcAutoDriving()
            sim1.car.sendSpeedAngle(sim1.car.desired_velocity, sim1.car.desired_steering) #(spam) send instruction (or simulate doing so)
        sim1.car.getFeedback() #run this to parse serial data (or simulate doing so)
        sim1.car.update(dt)
        
        sim1.redraw()
        DD.frameRefresh() #not done in redraw() to accomodate multi-sim options
        
        ## you can 
        # if((rightNow-mapSaveTimer)>0.25):
        #     sim1.mapList.append(MS.deepCopyExtractMap(sim1))
        #     if(len(sim1.mapList) > 40):
        #         sim1.mapList.pop(0)
        #     #print((sim1.clock()-mapSaveTimer)*1000)
        #     mapSaveTimer = rightNow
        
        timeSinceLastUpdate = rightNow #save time (from start of loop) to be used next time
        
        ## after all the important stuff:
        if((FPSrightNow-FPSlimitTimer) < 0.015): #60FPS limiter (optional)
            time.sleep(0.0155-(FPSrightNow-FPSlimitTimer))
        FPSlimitTimer = FPSrightNow

except KeyboardInterrupt:
    print("main thread keyboard interrupt")
except Exception as excep:
    print("main thread exception:", excep)
finally:
    try:
        mapSender.manualClose()
    except:
        print("manualClose() failed")
    try:
        threadKeepRunning[0] = False #signal the Thread function to stop its while() loop(s) (the list is just a manual boolean pointer (hack))
        mapSockThread.join(2)
        print("mapSockThread still alive?:", mapSockThread.is_alive())
    except Exception as excep:
        print("couldn't stop thread?:", excep)
    DD.pygameEnd() #correctly shut down pygame window
    try:  #alternatively:  if(type(sim1.car) is RC.realCar):
        sim1.car.disconnect()
    except Exception as excep:
        print("failed to run car.disconnect():", excep)