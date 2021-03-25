#TBD: add spoof coneConnecter class that gets data from network, to run visualization for non-local coneConnecter
#adopt mapClassTemp.py
#seperate pathfinding and coneconnecting classes

#note: for numpy sin/cos/tan angles, 0 is at 3 o'clock, positive values are CCW and the range returned by arctan2 is (-180,180) or (-pi, pi)


import pygame       #python game library, used for the visualization
import numpy as np  #general math library
import datetime     #used for naming log files
import time         #used for (temporary) driving math in raceCar() class

from mapClassTemp import Map
import generalFunctions as GF #(homemade) some useful functions for everyday ease of use


global DONT_SORT, SORTBY_DIST, SORTBY_ANGL, SORTBY_ANGL_DELT, SORTBY_ANGL_DELT_ABS
DONT_SORT = 0
SORTBY_DIST = 1
SORTBY_ANGL = 2
SORTBY_ANGL_DELT = 3
SORTBY_ANGL_DELT_ABS = 4
global NO_CONN_EXCL, EXCL_UNCONN, EXCL_SING_CONN, EXCL_DUBL_CONN
NO_CONN_EXCL = 0
EXCL_UNCONN = 1
EXCL_SING_CONN = 2
EXCL_DUBL_CONN = 3
EXCL_ANY_CONN = 4

#to be removed once csv f
global CD_FINISH, coneLogTableColumnDef
CD_FINISH = 'finish'
coneLogTableColumnDef = "cone ID,leftOrRight,Xpos,Ypos,prev ID,next ID,coneData\n"


class coneConnection: #a class to go in Map.Cone.coneConData
    def __init__(self, angle=0, dist=0, strength=0):
        #self.cone = conePointer #(pointer to) connected cone (ALREADY IN Cone CLASS UNDER Cone.connections)
        self.angle = angle #angle between cones
        self.dist = dist #distance between cones
        self.strength = strength #connection strength (highest strength option was used)




class coneConnecter(Map):
    def __init__(self, importConeLogFilename='', logging=True, logname="coneLog"):
        Map.__init__(self) #init map class
        self.coneConnectionThreshold = 5  #in meters (or at least not pixels)  note: hard threshold beyond which cones will NOT come into contention for connection
        self.coneConnectionThresholdSquared = self.coneConnectionThreshold**2
        self.coneConnectionHighAngleDelta = np.deg2rad(60) #IMPORTANT: not actual hard threshold, just distance at which lowest strength-score is given
        self.coneConnectionMaxAngleDelta = np.deg2rad(120) #if the angle difference is larger than this, it just doesnt make sense to connect them. (this IS a hard threshold)
        self.coneConnectionRestrictiveAngleChangeThreshold = np.deg2rad(20) # the most-restrictive-angle code only switches if angle is this much more restrictive
        self.coneConnectionRestrictiveAngleStrengthThreshold = 0.5 # the strength of the more restrictive cone needs to be at least this proportion of the old (less restrictive angle) strength
        
        self.pathConnectionThreshold = 10 #in meters (or at least not pixels)  IMPORTANT: not actual hard threshold, just distance at which lowest strength-score is given
        self.pathConnectionMaxAngleDelta = np.deg2rad(60) #IMPORTANT: not actual hard threshold, just distance at which lowest strength-score is given
        
        self.pathFirstLineCarAngleDeltaMax = np.deg2rad(45) #if the radDiff() between car (.orient) and the first line's connections is bigger than this, switch conneections or stop
        self.pathFirstLineCarSideAngleDelta = np.deg2rad(80) #left cones should be within +- pathFirstLineCarSideAngleDelta radians of the side of the car (asin, car.orient + or - pi/2, depending on left/right side)
        self.pathFirstLinePosDist = 4 # simple center to center distance, hard threshold, used to filter out very far cones
        self.pathFirstLineCarDist = 3 # real distance, not hard threshold, just distance at which lowest strength-score is given
        
        #self.leftConesFullCircle = False  #TBD: no checking function yet, and because connectCone() can connect a cone to the 0th cone at any time without completing the circle, a special function this is required
        #self.rightConesFullCircle = False
        self.pathFullCircle = False
    
    
    
    def connectCone(self, coneToConnect, applyResult=True): #
        #the correct cone should be selected based on a number of parameters:
        #distance to last cone, angle difference from last and second-to-last cones's, angle that 'track' is (presumably) going based on cones on other side (left/right) (if right cones make corner, left cones must also), etc
        # ideas: distance between last (existing) cone connection may be similar to current cone distance (human may place cones in inner corners close together and outer corners far apart, but at least consistent)
        # ideas: vincent's "most restrictive" angle could be done by realizing the a right corner (CW) is restrictive for left-cones, and a left corner (CCW) is restrictive for right-cones, so whether the angle delta is positive or negative (and leftOrRight boolean) could determine strength
        #more parameters to be added later, in non-simulation code
        currentConnectionCount = len(coneToConnect.connections)
        if(currentConnectionCount >= 2):#if cone is already doubly connected
            print("input cone already doubly connected?!:", coneToConnect.coneConData)
            return(False, None)
        else:
            currentExistingAngle = 0.0
            if((currentConnectionCount>0) and (coneToConnect.coneConData is not None)): #only 1 of the 2 checks should be needed, but just to be safe
                currentExistingAngle = GF.radRoll(GF.radInv(coneToConnect.coneConData[0].angle))
            
            nearbyConeList = self.distanceToCone(coneToConnect.position, self.right_cone_list if coneToConnect.LorR else self.left_cone_list, SORTBY_DIST, [coneToConnect.ID], self.coneConnectionThreshold, EXCL_DUBL_CONN, [coneToConnect.ID])  #note: list is sorted by distance, but that's not really needed given the (CURRENT) math
            # nearbyConeList structure: [[cone, [dist, angle]], ]
            if(len(nearbyConeList) < 1):
                print("nearbyConeList empty")
                return(False, None)
            bestCandidateIndex = -1;   highestStrength = 0;   candidatesDiscarded = 0
            candidateList = []
            for i in range(len(nearbyConeList)):
                cone = nearbyConeList[i][0] #not strictly needed, just for legibility
                connectionCount = len(cone.connections)
                coneCandidateStrength = 1 #init var
                coneCandidateStrength *= 1.5-(nearbyConeList[i][1][0]/self.coneConnectionThreshold)  #high distance, low strength. Linear. worst>0.5 best<1.5  (note, no need to limit, because the min score is at the hard threshold)
                angleToCone = nearbyConeList[i][1][1]
                #hard no's: if the angle difference is above the max (like 135 degrees), the prospect cone is just too damn weird, just dont connect to this one
                #note: this can be partially achieved by using angleThreshRange in distanceToCone() to preventatively discard cones like  angleThreshRange=([currentExistingAngle - self.coneConnectionMaxAngleDelta, currentExistingAngle + self.coneConnectionMaxAngleDelta] if (currentConnectionsFilled[0] or currentConnectionsFilled[1]) else [])
                if(((abs(GF.radDiff(angleToCone, cone.coneConData[0].angle)) > self.coneConnectionMaxAngleDelta) if (connectionCount > 0) else False) or ((abs(GF.radDiff(angleToCone, currentExistingAngle)) > self.coneConnectionMaxAngleDelta) if (currentConnectionCount > 0) else False)):
                    #print("very large angle delta")
                    candidatesDiscarded += 1
                else:
                    if(connectionCount > 0): #if cone already has a connection, check the angle delta
                        coneExistingAngle = cone.coneConData[0].angle
                        coneCandidateStrength *= 1.5- min(abs(GF.radDiff(coneExistingAngle, angleToCone))/self.coneConnectionHighAngleDelta, 1)  #high angle delta, low strength. Linear. worst>0.5 best<1.5
                    if(currentConnectionCount > 0):
                        angleDif = GF.radDiff(currentExistingAngle, angleToCone) #radians to add to currentExistingAngle to get to angleToCone (abs value is most interesting)
                        coneCandidateStrength *= 1.5- min(abs(angleDif)/self.coneConnectionHighAngleDelta, 1)  #high angle delta, low strength. Linear. worst>0.5 best<1.5
                        ## (Vincent's) most-restrictive angle could be implemented here, or at the end, by using SORTBY_ANGL_DELT and scrolling through the list from bestCandidateIndex to one of the ends of the list (based on left/right-edness), however, this does require a previous connection (preferably a connection that is in, or leads to, the pathList) to get angleDeltaTarget
                        coneCandidateStrength *= 1 + (0.5 if coneToConnect.LorR else -0.5)*max(min(angleDif/self.coneConnectionHighAngleDelta, 1), -1)  #high angle delta, low strength. Linear. worst>0.5 best<1.5
                        ## if most-restrictive angle is applied at the end, when all candidates have been reviewed
                        candidateList.append([i, angleDif, coneCandidateStrength])
                    #if(idk yet
                    if(coneCandidateStrength > highestStrength):
                        highestStrength = coneCandidateStrength
                        bestCandidateIndex = i
            if((bestCandidateIndex < 0) or (highestStrength <= 0) or (len(nearbyConeList) == candidatesDiscarded)):
                print("it seems no suitible candidates for cone connection were found at all... bummer.", len(nearbyConeList), candidatesDiscarded, bestCandidateIndex, highestStrength)
                return(False, None)
            ## success!
            ## most restrictive angle check
            if(currentConnectionCount > 0): #most restrictive angle can only be applied if there is a reference angle (you could also check len(candidateList)
                bestCandidateListIndex = GF.findIndexBy2DEntry(candidateList, 0, bestCandidateIndex) #this index is of candidateList, not of nearbyConeList
                for i in range(len(candidateList)):
                    if((candidateList[i][1] > candidateList[bestCandidateListIndex][1]) if coneToConnect.LorR else (candidateList[i][1] < candidateList[bestCandidateListIndex][1])): #most restrictive angle is lowest angle
                        print("more restrictive angle found:", candidateList[i][1], "is better than", candidateList[bestCandidateListIndex][1])
                        #if((abs(radDiff(candidateList[i][1], candidateList[bestCandidateListIndex][1])) > self.coneConnectionRestrictiveAngleChangeThreshold) and ((candidateList[i][2]/highestStrength) > self.coneConnectionRestrictiveAngleStrengthThreshold)):
                        if(abs(GF.radDiff(candidateList[i][1], candidateList[bestCandidateListIndex][1])) > self.coneConnectionRestrictiveAngleChangeThreshold):
                            print("old highestStrength:", round(highestStrength, 2), " new highestStrength:", round(candidateList[i][2], 2), " ratio:", round(candidateList[i][2]/highestStrength, 2))
                            bestCandidateListIndex = i
                            bestCandidateIndex = candidateList[i][0]
                            highestStrength = candidateList[i][2]
            #print("cone connection made between (ID):", coneToConnectID, "and (ID):", nearbyConeList[bestCandidateIndex][0])
            ## make the connection:
            winningCone = nearbyConeList[bestCandidateIndex][0] #pointer to a Cone class object
            if(applyResult): #True in 99% of situations, but if you want to CHECK a connection without committing to it, then this should be False
                ## input cone
                coneToConnect.connections.append(winningCone) #save cone pointer in the .connections list
                coneToConnect.coneConData.append(coneConnection(nearbyConeList[bestCandidateIndex][1][1], nearbyConeList[bestCandidateIndex][1][0], highestStrength))
                ## and the other cone
                winningCone.connections.append(coneToConnect)
                winningCone.coneConData.append(coneConnection(GF.radInv(nearbyConeList[bestCandidateIndex][1][1]), nearbyConeList[bestCandidateIndex][1][0], highestStrength))
            return(True, winningCone) #return the cone you connected with (or are capable of connecting with, if applyResult=False)
    
    def connectConeSuperSimple(self, coneToConnect, applyResult=True):
        currentConnectionCount = len(coneToConnect.connections)
        if(currentConnectionCount >= 2):#if cone is already doubly connected
            print("input cone already doubly connected?!:", coneToConnect.coneConData)
            return(False, None)
        else:
            nearbyConeList = self.distanceToConeSquared(coneToConnect.position, self.right_cone_list if coneToConnect.LorR else self.left_cone_list, True, [coneToConnect.ID], self.coneConnectionThresholdSquared, EXCL_DUBL_CONN, [coneToConnect.ID])  #note: list is sorted by (squared) distance, but that's not really needed given the (CURRENT) math
            if(len(nearbyConeList) < 1):
                print("nearbyConeList empty")
                return(False, None)
            bestCandidateIndex = -1;   highestStrength = 0;   candidatesDiscarded = 0
            for i in range(len(nearbyConeList)):
                coneCandidateStrength = 1 #init var
                coneCandidateStrength *= 1.5-(nearbyConeList[i][1]/self.coneConnectionThresholdSquared)  #high distance, low strength. non-Linear (quadratic?). worst>0.5 best<1.5  (note, no need to limit, because the min score is at the hard threshold)
                ## no angle math can be done, as Pythagoras's ABC is used, not sohcahtoa :)
                if(coneCandidateStrength > highestStrength):
                    highestStrength = coneCandidateStrength
                    bestCandidateIndex = i
            if((bestCandidateIndex < 0) or (highestStrength <= 0) or (len(nearbyConeList) == candidatesDiscarded)):
                print("it seems no suitible candidates for cone connection were found at all... bummer.", len(nearbyConeList), candidatesDiscarded, bestCandidateIndex, highestStrength)
                return(False, None)
            ## success!
            #print("simple cone connection made between (ID):", coneToConnectID, "and (ID):", nearbyConeList[bestCandidateIndex][0])
            ## make the connection:
            winningCone = nearbyConeList[bestCandidateIndex][0] #pointer to a Cone class object
            if(applyResult): #True in 99% of situations, but if you want to CHECK a connection without committing to it, then this should be False
                ## input cone
                coneToConnect.connections.append(winningCone) #save cone pointer in the .connections list
                coneToConnect.coneConData.append(coneConnection(0.0, nearbyConeList[bestCandidateIndex][1], highestStrength))
                ## and the other cone
                winningCone.connections.append(coneToConnect)
                winningCone.coneConData.append(coneConnection(0.0, nearbyConeList[bestCandidateIndex][1], highestStrength))
            return(True, winningCone) #return the cone you connected with (or are capable of connecting with, if applyResult=False)
    
    
    
    # def makePath(self):
    #     # pathList content:  [center point ([x,y]), [line angle, path (car) angle], track width, [ID, cone pos ([x,y]), index (left)], [(same as last entry but for right-side cone)], path-connection-strength]
    #     # left/right-ConeList content: [cone ID, [x,y], [[cone ID, index, angle, distance, cone-connection-strength], [(same as last entry)]], cone data]
    #     if(self.pathFullCircle):
    #         print("not gonna make path, already full circle")
    #         return(False)
    #     if(self.car is None):
    #         print("cant make path, there is no car")
    #         return(False)
    #     if(len(self.pathList) == 0):
    #         if((len(self.rightConeList) < 2) or (len(self.leftConeList) < 2)): #first pathLine can only be made between 2 connected cones
    #             print("not enough cones in one or more coneLists, cant place first pathLine")
    #             return(False)
            
    #         #search cones here
    #         firstCone = [None, None]
    #         firstConeIndexInArray = [-1,-1]
    #         if((self.finishLinePos[0] is not None) or (self.finishLinePos[1] is not None)):
    #             print("using finish cones to make first pathLine")
    #             if((self.finishLinePos[0] is not None) and (self.finishLinePos[1] is not None)):
    #                 firstCone = self.finishLinePos #finishLinePos is already a list of 2 pointers, so it should be fine to go without copying them(, right?)
    #                 firstConeIndexInArray = [findIndexBy2DEntry(self.leftConeList, 0, firstCone[0][0]), findIndexBy2DEntry(self.rightConeList, 0, firstCone[1][0])]
    #             else:
    #                 print("only 1 finish cone set, makePath can just wait untill the second is found, right?")
    #                 return(False)
    #         else: #if there aren't already finish cones, then find it the old-fashioned way, by looking for cones near the car
    #             sideAngleRanges = [[self.car.orient+(np.pi/2)-self.pathFirstLineCarSideAngleDelta, self.car.orient+(np.pi/2)+self.pathFirstLineCarSideAngleDelta], [self.car.orient-(np.pi/2)-self.pathFirstLineCarSideAngleDelta, self.car.orient-(np.pi/2)+self.pathFirstLineCarSideAngleDelta]] #left side is car.orient +pi/2, right side is car.orient -pi/2
    #             firstConeCandidates = self.distanceToCone(self.car.pos, [self.leftConeList, self.rightConeList], SORTBY_DIST, False, [], self.pathFirstLinePosDist, EXCL_UNCONN, [], self.car.orient, sideAngleRanges)
    #             for LorR in range(2):
    #                 bestCandidateIndex = -1;   highestStrength = 0;   candidatesDiscarded = 0
    #                 #carPerpAngle = self.car.orient + (np.pi*(0.5 if (LorR == 1) else -0.5))
    #                 carPerpAngle = self.car.orient - (np.pi/2) #always get CW perpendicular
    #                 for i in range(len(firstConeCandidates[LorR])):
    #                     cone = firstConeCandidates[LorR][i][2]
    #                     connectionsFilled = [(cone[2][0][1] >= 0), (cone[2][1][1] >= 0)] #2-size list of booleans
    #                     connectionAnglesAllowed = [((abs(radDiff(cone[2][0][2], self.car.orient)) < self.pathFirstLineCarAngleDeltaMax) if connectionsFilled[0] else False), ((abs(radDiff(cone[2][1][2], self.car.orient)) < self.pathFirstLineCarAngleDeltaMax) if connectionsFilled[1] else False)]
    #                     ## it's important to note that the distance calculated by distanceToCone() is between the center of the car and the cone, and therefore not the shortest path, or real distance to the car (a cone next to a wheel will have a higher distance than a cone next to the middle of the car, which is illogical)
    #                     ## this illogical distance can still be used to help filter out candidates, but for an accurate strength-rating, distanceToCar() (a function of the raceCar class) should be used
    #                     coneOverlapsCar, distToCar = self.car.distanceToCar(cone[1])
    #                     #print("evaluating "+("right" if (LorR==1) else "left")+" cone:", cone[0], connectionsFilled, connectionAnglesAllowed, coneOverlapsCar, distToCar)
    #                     if(not (connectionsFilled[0] or connectionsFilled[1])):
    #                         ## somehow, an unconnected cone slipped past the filer in distanceToCone(). this should be impossible, but i wrote the filter code in a hurry, so little debugging cant hurt
    #                         print("impossible filter slip 1")
    #                         candidatesDiscarded += 1
    #                     elif(not (connectionAnglesAllowed[0] or connectionAnglesAllowed[1])):
    #                         ## neither of the connections on this candidate 
    #                         print("neither connections have acceptable angles")
    #                         candidatesDiscarded += 1
    #                     elif(connectionAnglesAllowed[0] and connectionAnglesAllowed[1]):
    #                         ## somehow, both connections are alligned with the car, and since coneConnectionMaxAngleDelta exists, that should be impossible
    #                         print("impossible angle sitch 1")
    #                         candidatesDiscarded += 1
    #                     elif(coneOverlapsCar):
    #                         print("cone overlaps car")
    #                         candidatesDiscarded += 1
    #                     else:
    #                         coneCandidateStrength = 1 #init var
    #                         coneCandidateStrength *= 1.5-min(distToCar/self.pathFirstLineCarDist, 1)  #high distance, low strength. non-Linear (quadratic?). worst>0.5 best<1.5
    #                         coneCandidateStrength *= 1.5-abs(radDiff(cone[2][(0 if connectionAnglesAllowed[0] else 1)][2], self.car.orient))/self.pathFirstLineCarAngleDeltaMax  #high angle delta, low strength. Linear. worst>0.5 best<1.5
    #                         ## this following check makes sure the pathline is perpendicular to the car
    #                         conePerpAngle = 0 #init var
    #                         if(connectionsFilled[0] and connectionsFilled[1]):
    #                             conePerpAngle = radMidd(cone[2][0][2], cone[2][1][2]) #note: radMidd() has inputs (lowBound, upBound), so for right cones this will give an angle that points AWAY from the car, and for left cones it points towards the car (both in the same direction if they're paralel)
    #                         else:
    #                             connectionToUse = (1 if connectionsFilled[1] else 0)
    #                             conePerpAngle = radRoll(cone[2][connectionToUse][2] + (np.pi*(0.5 if (connectionToUse == 0) else -0.5))) #see note on claculation with double connection
    #                         coneCandidateStrength *= 1.5-min(abs(radDiff(conePerpAngle, carPerpAngle))/self.pathConnectionMaxAngleDelta, 1)
    #                         ## using existing chosen firstCone, only works for the right cone (this is an unequal check, so i hate it, but it does work to make sure the first line is straight (not diagonal))
    #                         if(LorR == 1): #TO BE IMPROVED, but i dont know quite how yet
    #                             leftFirstConeConnectionsFilled = [(firstCone[0][2][0][1] >= 0), (firstCone[0][2][1][1] >= 0)]
    #                             leftPerpAngle = 0 #init var
    #                             if(leftFirstConeConnectionsFilled[0] and leftFirstConeConnectionsFilled[1]):
    #                                 leftPerpAngle = radMidd(firstCone[0][2][0][2], firstCone[0][2][1][2])
    #                             else:
    #                                 connectionToUse = (1 if leftFirstConeConnectionsFilled[1] else 0)
    #                                 leftPerpAngle = radRoll(firstCone[0][2][connectionToUse][2] + (np.pi*(0.5 if (connectionToUse == 0) else -0.5)))
    #                             tempPathWidth, tempPathAngle = distAngleBetwPos(firstCone[0][1], cone[1])
    #                             coneCandidateStrength *= 1.5-min(abs(radDiff(tempPathAngle, leftPerpAngle))/self.pathConnectionMaxAngleDelta, 1)
    #                             #you could also even do distance, but whatever
    #                         if(coneCandidateStrength > highestStrength):
    #                             highestStrength = coneCandidateStrength
    #                             bestCandidateIndex = i
    #                 if((bestCandidateIndex < 0) or (highestStrength <= 0) or (len(firstConeCandidates[LorR]) == candidatesDiscarded)):
    #                     print("it seems no suitible candidates for first "+("right" if (LorR==1) else "left")+" cone were found at all... bummer.", len(firstConeCandidates[LorR]), candidatesDiscarded, bestCandidateIndex, highestStrength)
    #                     return(False, [])
    #                 ## if the code makes it here, a suitable first cone has been selected.
    #                 #print("first "+("right" if (LorR==1) else "left")+" cone found!", highestStrength, bestCandidateIndex, len(firstConeCandidates[LorR]), candidatesDiscarded)
    #                 firstCone[LorR] = firstConeCandidates[LorR][bestCandidateIndex][2]
    #                 firstConeIndexInArray[LorR] = firstConeCandidates[LorR][bestCandidateIndex][1] #could be eliminated in favor of pointers?
            
    #         ## angle checks and swithing connections if possible
    #         for LorR in range(2):
    #             firstConeConnectionIndex = 1 #try to use the 'front' connection by default
    #             firstConnectionsFilled = [firstCone[LorR][2][0][1] >= 0, firstCone[LorR][2][1][1] >= 0]
    #             if(not (firstConnectionsFilled[0] or firstConnectionsFilled[1])): #if it has no conenctions at all (this SHOULD NEVER HAPPEN, because distanceToCone() filters out unconnected cones, but might as well check
    #                 #first cone is unconnected
    #                 print("no connections on "+("right" if (LorR==1) else "left")+" firstCone:", firstCone[LorR])
    #                 return(False)
    #             elif(not firstConnectionsFilled[firstConeConnectionIndex]): #if it only has a 'back' connection, just move the back one to the front
    #                 #first, switch connection data to make preferable (front) the only valid one
    #                 #print("whipping lastLeft (1):", lastLeftCone[2])
    #                 tempConVal = firstCone[LorR][2][0] #one of these is an empty connection
    #                 firstCone[LorR][2][0] = firstCone[LorR][2][1]
    #                 firstCone[LorR][2][1] = tempConVal
    #                 self.logFileChanged = True #set flag
    #                 #then check the angle of that connection. If it is too far off from the car angle then something is terribly wrong (or 
    #                 if(abs(radDiff(firstCone[LorR][2][firstConeConnectionIndex][2], self.car.orient)) > self.pathFirstLineCarAngleDeltaMax):
    #                     print("only first "+("right" if (LorR==1) else "left")+" connection angle larger than allowed:", firstConeConnectionIndex, round(np.rad2deg(firstCone[LorR][2][firstConeConnectionIndex][2]), 2), round(np.rad2deg(self.car.orient), 2), round(np.rad2deg(abs(radDiff(firstCone[LorR][2][firstConeConnectionIndex][2], self.car.orient))),2))
    #                     return(False)
    #             elif(firstConnectionsFilled[intBoolInv(firstConeConnectionIndex)]): #if it has both connections:
    #                 if(abs(radDiff(firstCone[LorR][2][firstConeConnectionIndex][2], self.car.orient)) > self.pathFirstLineCarAngleDeltaMax):
    #                     if(abs(radDiff(firstCone[LorR][2][intBoolInv(firstConeConnectionIndex)][2], self.car.orient)) > self.pathFirstLineCarAngleDeltaMax):
    #                         print("second left angle also larger than allowed", round(np.rad2deg(firstCone[LorR][2][intBoolInv(firstConeConnectionIndex)][2]), 2), round(np.rad2deg(self.car.orient), 2), round(np.rad2deg(abs(radDiff(firstCone[LorR][2][intBoolInv(firstConeConnectionIndex)][2], self.car.orient))),2))
    #                         return(False)
    #                     else: #first angle was large, but second angle wasnt, just switch the connections around and we're good to go
    #                         #print("whipping lastLeft (2):", lastLeftCone[2])
    #                         tempConVal = firstCone[LorR][2][0] #one of these is an empty connection
    #                         firstCone[LorR][2][0] = firstCone[LorR][2][1]
    #                         firstCone[LorR][2][1] = tempConVal
    #                         self.logFileChanged = True #set flag
    #             ## else do nothing, everything is allready good and there's no need to worry
    #         ## and now just put the first cones into the pathlist
    #         pathWidth, lineAngle = distAngleBetwPos(firstCone[0][1], firstCone[1][1])
    #         carAngle = radRoll(lineAngle + (np.pi/2)) # angle is from left cone to right, so 90deg (pi/2 rad) CCW rotation is where the car should go
    #         centerPoint = [firstCone[1][1][0] + (firstCone[0][1][0]-firstCone[1][1][0])/2, firstCone[1][1][1] + (firstCone[0][1][1]-firstCone[1][1][1])/2]  # [xpos + half Xdelta, yPos + half Ydelta]
    #         self.pathList.append([centerPoint, [lineAngle, carAngle], pathWidth, [firstCone[0][0], firstCone[0][1], firstConeIndexInArray[0]], [firstCone[1][0], firstCone[1][1], firstConeIndexInArray[1]], 69.420])
        
    #     else: #if len(pathList) > 0
    #         lastPathLine = self.pathList[-1] # -1 gets the last item in list, you could also use (len(pathList)-1)
    #         coneLists = [self.leftConeList, self.rightConeList];  lastCone = [];  lastConeConnectionIndex = [];  lastConePerpAngle = [];  prospectCone = [];  prospectConeConnectionIndex = [];  
    #         for LorR in range(2):
    #             lastCone.append(coneLists[LorR][lastPathLine[3+LorR][2]])
    #             lastConeConnectionIndex.append(1) #try to use the 'front' connection by default
    #             lastConnectionsFilled = [lastCone[LorR][2][0][1] >= 0, lastCone[LorR][2][1][1] >= 0]
    #             #most of the code below is sanity checks, but some of it is for the purpouses of flipping connections to fit the 'back','front' model. This can be done differently, by putting it in the connectCone() function, for example. Threre might be some useless redundancy in the code below, but fuck it, it works (for now)
    #             if(not lastConnectionsFilled[lastConeConnectionIndex[LorR]]): #if it doesnt have a connected cone on the 
    #                 #print("no preferable (front) connection on lastLeftCone")
    #                 if(not lastConnectionsFilled[intBoolInv(lastConeConnectionIndex[LorR])]):
    #                     print("no connections on lastCone["+("right" if (LorR==1) else "left")+"] (impossible):", lastCone[LorR])
    #                     return(False)
    #                 else:
    #                     if(findIndexBy3DEntry(self.pathList, 3+LorR, 0, lastCone[LorR][2][intBoolInv(lastConeConnectionIndex[LorR])][0]) >= 0): #check if that isnt already in pathlist
    #                         ## if it is, then we just stop here. no more path generation can be done for now
    #                         print("single lastCone["+("right" if (LorR==1) else "left")+"] connection already in pathList (path at end of cone line, make more connections)")
    #                         return(False)
    #                     else: #if not, then the 'back' connection is the next (prospect) one, and this (last) cone has it all backwards. Switch the connection data for this cone around
    #                         #print("whipping lastCone["+("right" if (LorR==1) else "left")+"] (3):", lastLeftCone[2])
    #                         tempConVal = lastCone[LorR][2][0]
    #                         lastCone[LorR][2][0] = lastCone[LorR][2][1]
    #                         lastCone[LorR][2][1] = tempConVal
    #                         self.logFileChanged = True #set flag
    #             #super safety check for first-pathLine code
    #             if(len(self.pathList) == 1): #now check both angles again, just to be sure:
    #                 if(abs(radDiff(lastCone[LorR][2][lastConeConnectionIndex[LorR]][2], self.car.orient) > self.pathFirstLineCarAngleDeltaMax)):
    #                     print("post correction first "+("right" if (LorR==1) else "left")+" angle large:", lastConeConnectionIndex[LorR], round(np.rad2deg(lastCone[LorR][2][lastConeConnectionIndex[LorR]][2]), 2), round(np.rad2deg(self.car.orient), 2), round(np.rad2deg(abs(radDiff(lastCone[LorR][2][lastConeConnectionIndex[LorR]][2], self.car.orient))),2))
    #                     if(((lastConnectionsFilled[intBoolInv(lastConeConnectionIndex[LorR])])) and (abs(radDiff(lastCone[LorR][2][intBoolInv(lastConeConnectionIndex[LorR])][2], self.car.orient) > self.pathFirstLineCarAngleDeltaMax))):
    #                         print("post correction second angle also large", round(np.rad2deg(lastCone[LorR][2][intBoolInv(lastConeConnectionIndex[LorR])][2]), 2), round(np.rad2deg(self.car.orient), 2), round(np.rad2deg(abs(radDiff(lastCone[LorR][2][intBoolInv(lastConeConnectionIndex[LorR])][2], self.car.orient))),2))
    #                     return(False)
    #             lastConePerpAngle.append(radMidd(lastCone[LorR][2][LorR][2], lastCone[LorR][2][intBoolInv(LorR)][2]) if (lastCone[LorR][2][intBoolInv(lastConeConnectionIndex[LorR])][1] >= 0) else radRoll(lastCone[LorR][2][lastConeConnectionIndex[LorR]][2] + (np.pi*(0.5 if (lastConeConnectionIndex[LorR]==LorR) else -0.5)))) #note: addition or subtraction of half pi is a bit strange, dont worry about it :)
    #             #note: currently i am using radInv() when calculating angle delta, because angles are from left cone to right cone, but if you reverse radMidd(lastRightCone[2][1][2], lastRightCone[2][0][2]) to be radMidd(lastRightCone[2][0][2], lastRightCone[2][1][2]) it will give an inverted angle already. less human, more efficient
    #             #and now the prospect cones
    #             prospectCone.append(coneLists[LorR][lastCone[LorR][2][lastConeConnectionIndex[LorR]][1]])
            
    #         #check if you've gone full circle
    #         if(((prospectCone[0][0] == self.pathList[0][3][0]) and (prospectCone[1][0] == self.pathList[0][4][0])) \
    #            or ((lastCone[0][0] == self.pathList[0][3][0]) and (prospectCone[1][0] == self.pathList[0][4][0])) \
    #            or ((prospectCone[0][0] == self.pathList[0][3][0]) and (lastCone[1][0] == self.pathList[0][4][0]))):
    #             print("path full circle (by default)")
    #             self.pathFullCircle = True
    #             return(False) #technically, no new pathLine was added, but it does feel a little wrong to output the same value as errors at such a triumphant moment in the loop. 
            
    #         prospectConeConnectionIndex = [];  prospectConePerpAngle = []
    #         for LorR in range(2):
    #             prospectConeConnectionIndex.append(0 if (prospectCone[LorR][2][0][0] == lastCone[LorR][0]) else (1 if (prospectCone[LorR][2][1][0] == lastCone[LorR][0]) else -1)) #match connection. In simple, regular situations you could assume that the 'front' connection of the lastCone is the 'back' connection of prospectCone, but this is not a simple system, now is it :)
    #             if(prospectConeConnectionIndex[LorR] == -1):
    #                 print("BIG issue: lastCone["+("right" if (LorR==1) else "left")+"] pointed to this prospect cone, but this prospect cone does not point back", lastCone[LorR][2], prospectCone[LorR][2])
    #             elif(prospectConeConnectionIndex[LorR] == 1): #prospect cone has its connections switched around (lastLeftCone's 'front' should connect to prospectLeftCone's 'back')
    #                 #print("whipping prospect left:", prospectLeftCone[2])
    #                 tempConVal = prospectCone[LorR][2][0]
    #                 prospectCone[LorR][2][0] = prospectCone[LorR][2][1]
    #                 prospectCone[LorR][2][1] = tempConVal
    #                 prospectConeConnectionIndex[LorR] = 0
    #                 self.logFileChanged = True #set flag
                
    #             prospectConePerpAngle.append(radMidd(prospectCone[LorR][2][LorR][2], prospectCone[LorR][2][intBoolInv(LorR)][2]) if (prospectCone[LorR][2][intBoolInv(prospectConeConnectionIndex[LorR])][1] >= 0) else radRoll(prospectCone[LorR][2][prospectConeConnectionIndex[LorR]][2] + (np.pi*(0.5 if (prospectConeConnectionIndex[LorR] == LorR) else -0.5))))
    #             #note: currently i am using radInv() when calculating angle delta, because angles are from left cone to right cone, but if you reverse radMidd(lastRightCone[2][1][2], lastRightCone[2][0][2]) to be radMidd(lastRightCone[2][0][2], lastRightCone[2][1][2]) it will give an inverted angle already. less human, more efficient
            
    #         # self.debugLines = [] #clear debugLines
    #         # for LorR in range(2):
    #         #     self.debugLines.append([1, self.realToPixelPos(lastCone[LorR][1]), [4, lastConePerpAngle[LorR]], 1+LorR])
    #         #     self.debugLines.append([1, self.realToPixelPos(prospectCone[LorR][1]), [4, prospectConePerpAngle[LorR]], 1+LorR])
            
    #         ## all of could really be in a forloop of some kind, but fuck it; manual it is
    #         strengths = [1,1,1] #4 possible path lines, one of which already exists (between lastLeftCone and lastRightCone), so calculate the strengths for the remaining three possible pathlines
    #         pathWidths = [0,0,0];   pathAngles = [0,0,0]
    #         allCones = lastCone + prospectCone  #combine lists
    #         allPerpAngles = lastConePerpAngle + prospectConePerpAngle #combine lists
    #         maxStrengthIndex = -1; maxStrengthVal = -1;  winningCone = [None, None]
    #         for i in range(3):
    #             pathWidths[i], pathAngles[i] = distAngleBetwPos(allCones[(0 if (i==0) else 2)][1], allCones[(1 if (i==1) else 3)][1]) #last left to next right (for left (CCW) corners, where one left cone (lastLeftCone) connects to several right cones  (lastRightCone AND prospectRightCone))
    #             strengths[i] *= 1.5-min(pathWidths[i]/self.pathConnectionThreshold, 1) #strength based on distance, the threshold just determines minimum score, distance can be larger than threshold without math errors
    #             strengths[i] *= 1.5-min(abs(radDiff(pathAngles[i], allPerpAngles[(0 if (i==0) else 2)]))/self.pathConnectionMaxAngleDelta, 1) #strength based on angle delta from lastLeftConePerpAngle, the maxAngleDelta just determines minimum score, angle can be larger than threshold without math errors
    #             strengths[i] *= 1.5-min(abs(radDiff(radInv(pathAngles[i]), allPerpAngles[(1 if (i==1) else 3)]))/self.pathConnectionMaxAngleDelta, 1) #strength based on angle delta from prospectRightConePerpAngle, the maxAngleDelta just determines minimum score, angle can be larger than threshold without math errors
    #             if(strengths[i] >= maxStrengthVal):
    #                 maxStrengthVal = strengths[i]
    #                 maxStrengthIndex = i
    #                 winningCone[0] = allCones[(0 if (i==0) else 2)];  winningCone[1] = allCones[(1 if (i==1) else 3)]
            
    #         print("path found:", maxStrengthIndex, "at strength:", round(maxStrengthVal, 2))
    #         carAngle = radRoll(pathAngles[maxStrengthIndex] + (np.pi/2)) # angle is from left cone to right, so 90deg (pi/2 rad) CCW rotation is where the car should go
    #         ## the next section could especially benefit from a forloop, as none of these values are in lists/arrays and they absolutely could be. At least it is slightly legible, i guess
    #         winningConeIndex = []
    #         if(maxStrengthIndex == 0):
    #             winningConeIndex.append(lastPathLine[3][2]);  winningConeIndex.append(lastCone[1][2][lastConeConnectionIndex[1]][1])
    #         elif(maxStrengthIndex == 1):
    #             winningConeIndex.append(lastCone[0][2][lastConeConnectionIndex[0]][1]);  winningConeIndex.append(lastPathLine[4][2])
    #         else: #(maxStrengthIndex == 2)
    #             winningConeIndex.append(lastCone[0][2][lastConeConnectionIndex[0]][1]);  winningConeIndex.append(lastCone[1][2][lastConeConnectionIndex[1]][1])
    #         #check if you've gone full circle
    #         if((winningCone[0][0] == self.pathList[0][3][0]) and (winningCone[1][0] == self.pathList[0][4][0])):
    #             print("path full circle (from winning cones)")
    #             self.pathFullCircle = True
    #             return(False) #technically, no new pathLine was added, but it does feel a little wrong to output the same value as errors at such a triumphant moment in the loop. 
    #         else:
    #             centerPoint = [winningCone[1][1][0] + (winningCone[0][1][0]-winningCone[1][1][0])/2, winningCone[1][1][1] + (winningCone[0][1][1]-winningCone[1][1][1])/2]  # [xpos + half Xdelta, yPos + half Ydelta]
    #             self.pathList.append([centerPoint, [pathAngles[maxStrengthIndex], carAngle], pathWidths[maxStrengthIndex], [winningCone[0][0], winningCone[0][1], winningConeIndex[0]], [winningCone[1][0], winningCone[1][1], winningConeIndex[1]], maxStrengthVal])
    #     return(True)
    


#------------------------------------------------------------------------------------------------------------------------- everything from this point is for visualization ---------------------------------------------

#drawing funtions
class pygameDrawer:
    def __init__(self, window, drawSize=(1200,600), drawOffset=(0,0), viewOffset=(0,0), carCamOrient=0, sizeScale=30, startWithCarCam=False, invertYaxis=True):
        self.window = window #pass on the window object (pygame)
        self.drawSize = (int(drawSize[0]),int(drawSize[1])) #width and height of the display area (does not have to be 100% of the window)
        self.drawOffset = (int(drawOffset[0]), int(drawOffset[1])) #draw position offset, (0,0) is topleft
        self.viewOffset = [float(viewOffset[0]), float(viewOffset[1])] #'camera' view offsets, changing this affects the real part of realToPixelPos()
        self.carCamOrient = carCamOrient #orientation of the car (and therefore everything) on the screen. 0 is towards the right
        self.sizeScale = sizeScale #pixels per meter
        self.carCam = startWithCarCam #it's either carCam (car-centered cam, with rotating but no viewOffset), or regular cam (with viewOffset, but no rotating)
        self.invertYaxis = invertYaxis #pygame has pixel(0,0) in the topleft, so this just flips the y-axis when drawing things
        
        self.mapToDraw = self #TBD
        
        self.bgColor = [50,50,50] #grey
        
        self.finishLineColor = [255,40,0]
        self.finishLineWidth = 2 #pixels wide
        
        self.leftConeColor = [255,255,0] #yellow
        self.rightConeColor = [0,50,255] #dark blue
        self.coneLineWidth = 2 #pixels wide
        
        self.pathColor = [0,220,255] #light blue
        self.pathLineWidth = 2 #pixels wide
        #self.pathCenterPixelDiam = 
        
        self.mouseCone = None #either None, True or False, to indicate the color of the (mouse) cone that is about to be placed (replaces floatingCone)
        
        #the drawing stuff:
        self.carColor = [50,200,50]
        #polygon stuff (to be replaced by sprite?)
        self.carPointRadius = None #will be calculated once the car is drawn for the first time
        self.carPointAngle = None #will be calculated once the car is drawn for the first time
        
        self.movingViewOffset = False
        self.prevViewOffset = self.viewOffset
        self.movingViewOffsetMouseStart = [0,0]
        
        self.debugLines = [] #[[lineType, pos, pos/angles, color_index (0-2)], ] #third entry is: (lineType==0: straight line from two positions), (lineType==1: straight line from pos and [radius, angle]), (lineType==2: arc from pos and [radius, startAngle, endAngle])
        self.debugLineColors = [[255,0,255],[255,255,255],[0,255,0], [255,160,255]] #purple, white, green, pink
        self.debugLineWidth = 3
        
        #DELETE ME
        self.timeSinceLastUpdate = time.time()
        
        # try: #if there's no car object, this will not crash the entire program
        #     self.viewOffset = [(-self.car.pos[0]) + ((self.drawSize[0]/self.sizeScale)/2), (-self.car.pos[1]) + ((self.drawSize[1]/self.sizeScale)/2)]
        # except Exception as theExcept:
        #     print("couldn't set viewOffset to car pos:", theExcept)
    
    #pixel conversion functions (the most important functions in here)
    def pixelsToRealPos(self, pixelPos):
        if(self.carCam):
            dist = 0; angle = 0; #init var
            if(self.invertYaxis):
                dist, angle = GF.distAngleBetwPos([self.drawOffset[0]+self.drawSize[0]/2, self.drawOffset[1]+self.drawSize[1]/2], [pixelPos[0], self.drawOffset[1]+(self.drawOffset[1]+self.drawSize[1])-pixelPos[1]]) #get distance to, and angle with respect to, center of the screen (car)
            else:
                dist, angle = GF.distAngleBetwPos([self.drawOffset[0]+self.drawSize[0]/2, self.drawOffset[1]+self.drawSize[1]/2], pixelPos) #get distance to, and angle with respect to, center of the screen (car)
            return(GF.distAnglePosToPos(dist/self.sizeScale, angle+self.car.angle-self.carCamOrient, self.car.position)) #use converted dist, correctly offset angle & the real car pos to get a new real point
        else:
            if(self.invertYaxis):
                return([((pixelPos[0]-self.drawOffset[0])/self.sizeScale)-self.viewOffset[0], ((self.drawSize[1]-pixelPos[1]+self.drawOffset[1])/self.sizeScale)-self.viewOffset[1]])
            else:
                return([((pixelPos[0]-self.drawOffset[0])/self.sizeScale)-self.viewOffset[0], ((pixelPos[1]-self.drawOffset[1])/self.sizeScale)-self.viewOffset[1]])
    
    def realToPixelPos(self, realPos):
        if(self.carCam):
            dist, angle = GF.distAngleBetwPos(self.car.position, realPos) #get distance to, and angle with respect to, car
            shiftedPixelPos = GF.distAnglePosToPos(dist*self.sizeScale, angle-self.car.angle+self.carCamOrient, (self.drawOffset[0]+self.drawSize[0]/2, self.drawOffset[1]+self.drawSize[1]/2)) #calculate new (pixel) pos from the car pos, at the same distance, and the angle, plus the angle that the entire scene is shifted
            if(self.invertYaxis):
                return([shiftedPixelPos[0], self.drawOffset[1]+((self.drawOffset[1]+self.drawSize[1])-shiftedPixelPos[1])]) #invert Y-axis for normal (0,0) at bottomleft display
            else:
                return(shiftedPixelPos)
        else:
            if(self.invertYaxis):
                return([((realPos[0]+self.viewOffset[0])*self.sizeScale)+self.drawOffset[0], self.drawSize[1]-((realPos[1]+self.viewOffset[1])*self.sizeScale)+self.drawOffset[1]]) #invert Y-axis for normal (0,0) at bottomleft display
            else:
                return([((realPos[0]+self.viewOffset[0])*self.sizeScale)+self.drawOffset[0], ((realPos[1]+self.viewOffset[1])*self.sizeScale)+self.drawOffset[1]])
    
    #check if things need to be drawn at all
    def isInsideWindowPixels(self, pixelPos):
        return((pixelPos[0] < (self.drawSize[0] + self.drawOffset[0])) and (pixelPos[0] > self.drawOffset[0]) and (pixelPos[1] < (self.drawSize[1] + self.drawOffset[1])) and (pixelPos[1] > self.drawOffset[1]))
    
    def isInsideWindowReal(self, realPos):
        return(self.isInsideWindowPixels(self.realToPixelPos(realPos))) #not very efficient, but simple
    
    #drawing functions
    def background(self):
        self.window.fill(self.bgColor, (self.drawOffset[0], self.drawOffset[1], self.drawSize[0], self.drawSize[1])) #dont fill entire screen, just this pygamesim's area (allowing for multiple sims in one window)
    
    def drawCones(self, drawLines=True):
        conePixelDiam = Map.Cone.coneDiam * self.sizeScale
        drawnLineList = [] #[ [ID, ID], ] just a list of drawn lines by ID
        combinedConeList = (self.right_cone_list + self.left_cone_list)
        for cone in combinedConeList:
            #if(self.isInsideWindowReal(cone.position)): #if it is within bounds, draw it
            conePos = self.realToPixelPos(cone.position) #convert to pixel positions
            coneColor = self.rightConeColor if cone.LorR else self.leftConeColor
            if(drawLines):
                alreadyDrawn = [False, False]
                for drawnLine in drawnLineList:
                    for i in range(len(cone.connections)):
                        if((cone.ID in drawnLine) and (cone.connections[i].ID in drawnLine)):
                            alreadyDrawn[i] = True
                for i in range(len(cone.connections)):
                    if(not alreadyDrawn[i]):
                        pygame.draw.line(self.window, coneColor, conePos, self.realToPixelPos(cone.connections[i].position), self.coneLineWidth)
                        drawnLineList.append([cone.ID, cone.connections[i].ID]) #put established 'back' connection in list of drawn 
            #pygame.draw.circle(self.window, coneColor, [int(conePos[0]), int(conePos[1])], int(conePixelDiam/2)) #draw cone (as filled circle, not ellipse)
            conePos = GF.ASA(-(conePixelDiam/2), conePos) #bounding box of ellipse is positioned in topleft corner, so shift cone half a conesize to the topleft.
            pygame.draw.ellipse(self.window, coneColor, [conePos, [conePixelDiam, conePixelDiam]]) #draw cone
    
    # def drawPathLines(self, drawConeLines=True, drawCenterPoints=False):
    #     # pathList content:  [center point ([x,y]), [line angle, path (car) angle], track width, [ID, cone pos ([x,y]), index (left)], [(same as last entry but for right-side cone)], path-connection-strength]
    #     pathCenterPixelDiam = self.coneDiam * self.sizeScale
    #     for i in range(len(self.pathList)):
    #         if(self.isInsideWindowReal(self.pathList[i][0])):
    #             if(drawCenterPoints):
    #                 #centerPixelPos = self.realToPixelPos(self.pathList[i][0])
    #                 #pygame.draw.circle(self.window, self.pathColor, [int(centerPixelPos[0]), int(centerPixelPos[1])], int(pathCenterPixelDiam/2)) #draw center point (as filled circle, not ellipse)
    #                 pygame.draw.ellipse(self.window, self.pathColor, [ASA(-(pathCenterPixelDiam/2), self.realToPixelPos(self.pathList[i][0])), [pathCenterPixelDiam, pathCenterPixelDiam]]) #draw center point
    #             if(drawConeLines):
    #                 pygame.draw.line(self.window, self.pathColor, self.realToPixelPos(self.pathList[i][3][1]), self.realToPixelPos(self.pathList[i][4][1]), self.pathLineWidth) #line from left cone to right cone
    #             if(i > 0):#if more than one path point exists (and the forloop is past the first one)
    #                 #draw line between center points of current pathline and previous pathline (to make a line that the car should (sort of) follow)
    #                 pygame.draw.line(self.window, self.pathColor, self.realToPixelPos(self.pathList[i-1][0]), self.realToPixelPos(self.pathList[i][0]), self.pathLineWidth) #line from center pos to center pos
    #     if(self.pathFullCircle):
    #         pygame.draw.line(self.window, self.pathColor, self.realToPixelPos(self.pathList[-1][0]), self.realToPixelPos(self.pathList[0][0]), self.pathLineWidth) #line that loops around to start
    
    def drawFinishLine(self):
        if(len(self.finish_line_cones) >= 2):
            pygame.draw.line(self.window, self.finishLineColor, self.realToPixelPos(self.finish_line_cones[0].position), self.realToPixelPos(self.finish_line_cones[1].position), self.finishLineWidth)
    
    def drawCar(self):
        ## drawing is currently done by calculating the position of the corners and drawing a polygon with those points. Not efficient, not pretty, but fun
        #if(self.isInsideWindowReal(self.car.position)):
        if(self.carPointRadius is None):
            self.carPointRadius = (((self.car.width**2)+(self.car.length**2))**0.5)/2 #Pythagoras
            self.carPointAngle = np.arctan2(self.car.width, self.car.length) #this is used to make corner point for polygon
        polygonPoints = []
        offsets = [[np.cos(self.carPointAngle+self.car.angle) * self.carPointRadius, np.sin(self.carPointAngle+self.car.angle) * self.carPointRadius],
                    [np.cos(np.pi-self.carPointAngle+self.car.angle) * self.carPointRadius, np.sin(np.pi-self.carPointAngle+self.car.angle) * self.carPointRadius]]
        polygonPoints.append(self.realToPixelPos([self.car.position[0] + offsets[0][0], self.car.position[1] + offsets[0][1]])) #front left
        polygonPoints.append(self.realToPixelPos([self.car.position[0] + offsets[1][0], self.car.position[1] + offsets[1][1]])) #back left
        polygonPoints.append(self.realToPixelPos([self.car.position[0] - offsets[0][0], self.car.position[1] - offsets[0][1]])) #back right
        polygonPoints.append(self.realToPixelPos([self.car.position[0] - offsets[1][0], self.car.position[1] - offsets[1][1]])) #front right
        pygame.draw.polygon(self.window, self.carColor, polygonPoints) #draw car
        #arrow drawing (not needed, just handy to indicate direction of car)
        arrowPoints = [self.realToPixelPos(self.car.position), polygonPoints[1], polygonPoints[2]] #not as efficient as using the line below, but self.pos can vary
        oppositeColor = [255-self.carColor[0], 255-self.carColor[1], 255-self.carColor[1]]
        pygame.draw.polygon(self.window, oppositeColor, arrowPoints) #draw arrow
    
    def drawMouseCone(self, drawPossibleConnections=True, drawConnectionThresholdCircle=False):
        if(self.mouseCone is not None): #if there is a floating cone to be drawn
            conePixelDiam = Map.Cone.coneDiam * self.sizeScale
            conePos = pygame.mouse.get_pos() #update position to match mouse position
            if(self.isInsideWindowPixels(conePos)): #should always be true, right?
                coneColor = self.rightConeColor if self.mouseCone else self.leftConeColor
                if(drawConnectionThresholdCircle):
                    pygame.draw.circle(self.window, coneColor, [int(conePos[0]), int(conePos[1])], self.coneConnectionThreshold * self.sizeScale, self.coneLineWidth) #draw circle with coneConnectionThreshold radius 
                overlapsCone, overlappingCone = self.overlapConeCheck(self.pixelsToRealPos(conePos))
                if(overlapsCone and drawPossibleConnections): #if mouse is hovering over existing cone
                    nearbyConeList = self.distanceToConeSquared(overlappingCone.position, self.right_cone_list if overlappingCone.LorR else self.left_cone_list, False, [overlappingCone.ID], self.coneConnectionThresholdSquared, EXCL_DUBL_CONN, [overlappingCone.ID])
                    overlappingConePixelPos = self.realToPixelPos(overlappingCone.position)
                    for cone in nearbyConeList:
                        pygame.draw.line(self.window, coneColor, overlappingConePixelPos, self.realToPixelPos(cone[0].position), int(self.coneLineWidth/2))
                else:
                    if(drawPossibleConnections):
                        nearbyConeList = self.distanceToConeSquared(self.pixelsToRealPos(conePos), self.right_cone_list if self.mouseCone else self.left_cone_list, False, [], self.coneConnectionThresholdSquared, EXCL_DUBL_CONN, [])
                        for cone in nearbyConeList:
                            pygame.draw.line(self.window, coneColor, conePos, self.realToPixelPos(cone[0].position), int(self.coneLineWidth/2))
                    #pygame.draw.circle(self.window, coneColor, [int(conePos[0]), int(conePos[1])], int(conePixelDiam/2)) #draw cone (as filled circle, not ellipse)
                    conePos = GF.ASA(-(conePixelDiam/2), conePos) #bounding box of ellipse is positioned in topleft corner, so shift cone half a conesize to the topleft.
                    pygame.draw.ellipse(self.window, coneColor, [conePos, [conePixelDiam, conePixelDiam]]) #draw cone
    
    def drawDebugLines(self):
         #debugLines structure: [pos,pos, color_index (0-2)]
        for debugLine in self.debugLines:
            if(abs(debugLine[0]) == 2):
                if(debugLine[0] == 2):
                    pixelRactSize = debugLine[2][0] * self.sizeScale
                    debugLine[1] = GF.ASA(-(pixelRactSize), debugLine[1])
                    pixelRactSize *= 2
                    debugLine[2][0] = pixelRactSize
                    debugLine[0] = -2
                pygame.draw.arc(self.window, self.debugLineColors[(debugLine[3] if (len(debugLine)==4) else 0)], [debugLine[1], [debugLine[2][0], debugLine[2][0]]], debugLine[2][1], debugLine[2][2], self.debugLineWidth)
            else:
                if(debugLine[0] == 1):
                    secondPos = self.realToPixelPos(GF.distAnglePosToPos(debugLine[2][0], debugLine[2][1], self.pixelsToRealPos(debugLine[1]))) #convert
                    debugLine[2] = secondPos
                    debugLine[0] = -1
                pygame.draw.line(self.window, self.debugLineColors[(debugLine[3] if (len(debugLine)==4) else 0)], debugLine[1], debugLine[2], self.debugLineWidth)
    
    def updateViewOffset(self, mousePos=None): #screen dragging
        if(self.movingViewOffset):
            if(mousePos is None):
                mousePos = pygame.mouse.get_pos()
            mouseDelta = [] #init var
            if(self.invertYaxis):
                mouseDelta = [float(mousePos[0] - self.movingViewOffsetMouseStart[0]), float(self.movingViewOffsetMouseStart[1] - mousePos[1])]
            else:
                mouseDelta = [float(mousePos[0] - self.movingViewOffsetMouseStart[0]), float(mousePos[1] - self.movingViewOffsetMouseStart[1])]
            self.viewOffset[0] = self.prevViewOffset[0] + (mouseDelta[0]/self.sizeScale)
            self.viewOffset[1] = self.prevViewOffset[1] + (mouseDelta[1]/self.sizeScale)
    
    def redraw(self):
        self.updateViewOffset()
        self.background()
        self.drawCones(True) #boolean parameter is whether to draw lines between connected cones (track bounds) or not
        #self.drawPathLines(True, True) #boolean parameters are whether to draw the lines between cones (not the line the car follows) and whether to draw circles (conesized ellipses) on the center points of path lines respectively
        self.drawFinishLine()
        self.drawCar()
        self.drawMouseCone(True, False)
        self.drawDebugLines()
        #this section SHOULDN'T be in redraw(), but instead in some form of general update(), but as there currently isn't one yet, and it's only needed for one thing (manual driving), i put it here
        rightNow = time.time()
        self.car.update(rightNow - self.timeSinceLastUpdate)
        self.timeSinceLastUpdate = rightNow
    
    def updateWindowSize(self, drawSize=[1200, 600], drawOffset=[0,0], sizeScale=-1, autoMatchSizeScale=True):
        if(sizeScale > 0):
            self.sizeScale = sizeScale
        elif(autoMatchSizeScale):
            self.sizeScale = min(drawSize[0]/self.drawSize[0], drawSize[1]/self.drawSize[1]) * self.sizeScale #auto update sizeScale to match previous size
        self.drawSize = (int(drawSize[0]), int(drawSize[1]))
        self.drawOffset = (int(drawOffset[0]), int(drawOffset[1]))



class pygamesimLocal(coneConnecter, pygameDrawer):
    def __init__(self, window, drawSize=(1200,600), drawOffset=(0,0), viewOffset=[0,0], carCamOrient=0, sizeScale=30, startWithCarCam=False, invertYaxis=True, importConeLogFilename='', logging=True, logname="coneLog"):
        coneConnecter.__init__(self, importConeLogFilename, logging, logname)
        pygameDrawer.__init__(self, window, drawSize, drawOffset, viewOffset, carCamOrient, sizeScale, startWithCarCam, invertYaxis)

#cursor in the shape of a flag
flagCurs = ("ooo         ooooooooo   ",
            "oo ooooooooo...XXXX..ooo",
            "oo ....XXXX....XXXX....o",
            "oo ....XXXX....XXXX....o",
            "oo ....XXXX.XXX....XX..o",
            "oo XXXX....XXXX....XXXXo",
            "oo XXXX....XXXX....XXXXo",
            "oo XXXX....X...XXXX..XXo",
            "oo ....XXXX....XXXX....o",
            "oo ....XXXX....XXXX....o",
            "ooo....XXXX.ooooooooo..o",
            "oo ooooooooo         ooo",
            "oo                      ",
            "oo                      ",
            "oo                      ",
            "oo                      ",
            "oo                      ",
            "oo                      ",
            "oo                      ",
            "oo                      ",
            "oo                      ",
            "oo                      ",
            "oo                      ",
            "oo                      ")
flagCurs16  =  ("oooooooooooooooo", #1
                "oo ...XXX...XXXo",
                "oo ...XXX...XXXo",
                "oo XXX...XXX...o", #4
                "oo XXX...XXX...o",
                "oo ...XXX...XXXo",
                "oo ...XXX...XXXo",
                "oo XXX...XXX...o", #8
                "oo XXX...XXX...o",
                "oooooooooooooooo",
                "oo              ",
                "oo              ", #12
                "oo              ",
                "oo              ",
                "oo              ",
                "oo              ") #16
global flagCurs24Data, flagCurs16Data, flagCursorSet
flagCurs24Data = ((24,24),(0,23)) + pygame.cursors.compile(flagCurs, 'X', '.', 'o')
flagCurs16Data = ((16,16),(0,15)) + pygame.cursors.compile(flagCurs16, 'X', '.', 'o')
flagCursorSet = False

global windowKeepRunning, windowStarted
windowStarted = False
windowKeepRunning = False

global pygamesimInputLast, oldWindowSize
pygamesimInputLast = None #to be filled
oldWindowSize = []

def pygameInit():
    pygame.init()
    pygame.font.init()
    global window, oldWindowSize
    window = pygame.display.set_mode([1200, 600], pygame.RESIZABLE)
    oldWindowSize = window.get_size()
    pygame.display.set_caption("(pygame) selfdriving sim")
    global windowKeepRunning, windowStarted
    windowStarted = True
    windowKeepRunning = True

def pygameEnd():
    global windowStarted
    if(windowStarted): #if the window never started, quit might error out or something stupid
        print("quitting pygame window...")
        pygame.quit()

def frameRefresh():
    pygame.display.flip() #send (finished) frame to display

def handleMousePress(pygamesimInput, buttonDown, button, pos, eventToHandle):
    if(button==1): #left mouse button
        if(buttonDown): #mouse pressed down
            pygamesimInput.mouseCone = False #left cone
            pygame.event.set_grab(1)
            if(pygame.key.get_pressed()[102]):
                pygame.mouse.set_cursor(flagCurs16Data[0], flagCurs16Data[1], flagCurs16Data[2], flagCurs16Data[3])
        else:           #mouse released
            pygame.event.set_grab(0)
            pygamesimInput.mouseCone = None
            if(pygame.key.get_pressed()[102]):
                pygamesimInput.setFinishCone(False, pygamesimInput.pixelsToRealPos(pos))
                pygame.mouse.set_cursor(flagCurs24Data[0], flagCurs24Data[1], flagCurs24Data[2], flagCurs24Data[3])
            else:
                posToPlace = pygamesimInput.pixelsToRealPos(pos)
                overlaps, overlappingCone = pygamesimInput.overlapConeCheck(posToPlace)
                if(overlaps):
                    pygamesimInput.connectCone(overlappingCone)
                else:
                    newConeID = GF.findMaxAttrIndex((pygamesimInput.right_cone_list + pygamesimInput.left_cone_list), 'ID')[1]
                    aNewCone = Map.Cone(newConeID+1, posToPlace, False, False)
                    pygamesimInput.left_cone_list.append(aNewCone)
                    if(pygame.key.get_pressed()[pygame.K_LSHIFT]):
                        pygamesimInput.connectCone(aNewCone)
    if(button==3): #right mouse button
        if(buttonDown): #mouse pressed down
            pygamesimInput.mouseCone = True  #right cone
            pygame.event.set_grab(1)
            if(pygame.key.get_pressed()[102]):
                pygame.mouse.set_cursor(flagCurs16Data[0], flagCurs16Data[1], flagCurs16Data[2], flagCurs16Data[3])
        else:           #mouse released
            pygame.event.set_grab(0)
            pygamesimInput.mouseCone = None
            if(pygame.key.get_pressed()[102]):
                pygamesimInput.setFinishCone(True, pygamesimInput.pixelsToRealPos(pos))
                pygame.mouse.set_cursor(flagCurs24Data[0], flagCurs24Data[1], flagCurs24Data[2], flagCurs24Data[3])
            else:
                posToPlace = pygamesimInput.pixelsToRealPos(pos)
                overlaps, overlappingCone = pygamesimInput.overlapConeCheck(posToPlace)
                if(overlaps):
                    pygamesimInput.connectCone(overlappingCone)
                else:
                    newConeID = GF.findMaxAttrIndex((pygamesimInput.right_cone_list + pygamesimInput.left_cone_list), 'ID')[1]
                    aNewCone = Map.Cone(newConeID+1, posToPlace, True, False)
                    pygamesimInput.right_cone_list.append(aNewCone)
                    if(pygame.key.get_pressed()[pygame.K_LSHIFT]):
                        pygamesimInput.connectCone(aNewCone)
    elif(button==2): #middle mouse button
        if(buttonDown): #mouse pressed down
            if(not pygamesimInput.carCam):
                pygame.event.set_grab(1)
                pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_HAND)
                pygamesimInput.movingViewOffset = True
                pygamesimInput.movingViewOffsetMouseStart = pygame.mouse.get_pos()
                pygamesimInput.prevViewOffset = (pygamesimInput.viewOffset[0], pygamesimInput.viewOffset[1])
        else:           #mouse released
            pygame.event.set_grab(0)
            pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_ARROW)
            pygamesimInput.updateViewOffset() #update it one last time (or at all, if this hasn't been running in redraw())
            pygamesimInput.movingViewOffset = False

def handleKeyPress(pygamesimInput, keyDown, key, eventToHandle):
    if(key==pygame.K_f): # f
        global flagCursorSet
        if(keyDown):
            if(not flagCursorSet): #in pygame SDL2, holding a button makes it act like a keyboard button, and event gets spammed.
                pygame.event.set_grab(1)
                pygame.mouse.set_cursor(flagCurs24Data[0], flagCurs24Data[1], flagCurs24Data[2], flagCurs24Data[3])
                flagCursorSet = True
        else:
            pygame.event.set_grab(0)
            pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_ARROW)
            flagCursorSet = False
    # elif(key==pygame.K_r): # r
    #     if(keyDown):
    #         pygamesimInput.makePath()
    #         # doesNothing = 0
    #         # while(pygamesimInput.makePath()): #stops when path can no longer be advanced
    #         #     doesNothing += 1  # "python is so versitile, you can do anything" :) haha good joke
    # elif(key==pygame.K_l): # l
    #     if(keyDown):
    #         pygamesimInput.rewriteLogfile()
    elif(key==pygame.K_c): # c
        if(keyDown):
            pygamesimInput.carCam = not pygamesimInput.carCam
            if(pygamesimInput.carCam and pygamesimInput.movingViewOffset): #if you switched to carCam while you were moving viewOffset, just stop moving viewOffset (same as letting go of MMB)
                pygame.event.set_grab(0)
                pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_ARROW)
                pygamesimInput.updateViewOffset() #update it one last time (or at all, if this hasn't been running in redraw())
                pygamesimInput.movingViewOffset = False
            else:
                print("can't switch to car-centered cam, there is no car")

def currentPygamesimInput(pygamesimInputList, mousePos=None, demandMouseFocus=True): #if no pos is specified, retrieve it using get_pos()
    if(len(pygamesimInputList) > 1):
        if(mousePos is None):
            mousePos = pygame.mouse.get_pos()
        global pygamesimInputLast
        if(pygame.mouse.get_focused() or (not demandMouseFocus)):
            for pygamesimInput in pygamesimInputList:
                # localBoundries = [[pygamesimInput.drawOffset[0], pygamesimInput.drawOffset[1]], [pygamesimInput.drawSize[0], pygamesimInput.drawSize[1]]]
                # if(((mousePos[0]>=localBoundries[0][0]) and (mousePos[0]<(localBoundries[0][0]+localBoundries[1][0]))) and ((mousePos[1]>=localBoundries[0][1]) and (mousePos[0]<(localBoundries[0][1]+localBoundries[1][1])))):
                if(pygamesimInput.isInsideWindowPixels(mousePos)):
                    pygamesimInputLast = pygamesimInput
                    return(pygamesimInput)
        if(pygamesimInputLast is None): #if this is the first interaction
            pygamesimInputLast = pygamesimInputList[0]
        return(pygamesimInputLast)
    else:
        return(pygamesimInputList[0])

def handleWindowEvent(pygamesimInputList, eventToHandle):
    global window, oldWindowSize
    if(eventToHandle.type == pygame.QUIT):
        global windowKeepRunning
        windowKeepRunning = False #stop program (soon)
    
    elif(eventToHandle.type == pygame.VIDEORESIZE):
        newSize = eventToHandle.size
        if((oldWindowSize[0] != newSize[0]) or (oldWindowSize[1] != newSize[1])): #if new size is actually different
            print("video resize from", oldWindowSize, "to", newSize)
            correctedSize = [newSize[0], newSize[1]]
            window = pygame.display.set_mode(correctedSize, pygame.RESIZABLE)
            for pygamesimInput in pygamesimInputList:
                localNewSize = [int((pygamesimInput.drawSize[0]*correctedSize[0])/oldWindowSize[0]), int((pygamesimInput.drawSize[1]*correctedSize[1])/oldWindowSize[1])]
                localNewDrawPos = [int((pygamesimInput.drawOffset[0]*correctedSize[0])/oldWindowSize[0]), int((pygamesimInput.drawOffset[1]*correctedSize[1])/oldWindowSize[1])]
                pygamesimInput.updateWindowSize(localNewSize, localNewDrawPos, autoMatchSizeScale=False)
        oldWindowSize = window.get_size() #update size (get_size() returns tuple of (width, height))
    
    elif(eventToHandle.type == pygame.WINDOWSIZECHANGED): # pygame 2.0.1 compatible
        newSize = window.get_size()
        if((oldWindowSize[0] != newSize[0]) or (oldWindowSize[1] != newSize[1])): #if new size is actually different
            print("video resize from", oldWindowSize, "to", newSize)
            correctedSize = [newSize[0], newSize[1]]
            for pygamesimInput in pygamesimInputList:
                localNewSize = [int((pygamesimInput.drawSize[0]*correctedSize[0])/oldWindowSize[0]), int((pygamesimInput.drawSize[1]*correctedSize[1])/oldWindowSize[1])]
                localNewDrawPos = [int((pygamesimInput.drawOffset[0]*correctedSize[0])/oldWindowSize[0]), int((pygamesimInput.drawOffset[1]*correctedSize[1])/oldWindowSize[1])]
                pygamesimInput.updateWindowSize(localNewSize, localNewDrawPos, autoMatchSizeScale=False)
        oldWindowSize = window.get_size() #update size (get_size() returns tuple of (width, height))
    
    elif(eventToHandle.type == pygame.DROPFILE): #drag and drop files to import them
        if((pygame.mouse.get_pos()[0] == 0) and (pygame.mouse.get_pos()[1] == 0) and (len(pygamesimInputList) > 1)):
            print("skipping file import, please make sure to select the pygame window beforehand or something")
        else:
            currentPygamesimInput(pygamesimInputList, None, False).importConeLog(eventToHandle.file, True) #note: drag and drop functionality is a little iffy for multisim applications
    
    elif((eventToHandle.type == pygame.MOUSEBUTTONDOWN) or (eventToHandle.type == pygame.MOUSEBUTTONUP)):
        #print("mouse press", eventToHandle.type == pygame.MOUSEBUTTONDOWN, eventToHandle.button, eventToHandle.pos)
        handleMousePress(currentPygamesimInput(pygamesimInputList, eventToHandle.pos, True), eventToHandle.type == pygame.MOUSEBUTTONDOWN, eventToHandle.button, eventToHandle.pos, eventToHandle)
        
    elif((eventToHandle.type == pygame.KEYDOWN) or (eventToHandle.type == pygame.KEYUP)):
        #print("keypress:", eventToHandle.type == pygame.KEYDOWN, eventToHandle.key, pygame.key.name(eventToHandle.key))
        handleKeyPress(currentPygamesimInput(pygamesimInputList, None, True), eventToHandle.type == pygame.KEYDOWN, eventToHandle.key, eventToHandle)
    
    elif(eventToHandle.type == pygame.MOUSEWHEEL): #scroll wheel (zooming / rotating)
        simToScale = currentPygamesimInput(pygamesimInputList, None, True)
        if(pygame.key.get_pressed()[pygame.K_LCTRL] and simToScale.carCam): #if holding (left) CTRL while in carCam mode, rotate the view
            simToScale.carCamOrient += (eventToHandle.y * np.pi/16)
        else:
            dif = [simToScale.drawSize[0]/simToScale.sizeScale, simToScale.drawSize[1]/simToScale.sizeScale]
            simToScale.sizeScale += eventToHandle.y #zooming
            #if(not simToScale.carCam): #viewOffset is not used in carCam mode, but it won't hurt to change it anyway
            dif[0] -= (simToScale.drawSize[0]/simToScale.sizeScale)
            dif[1] -= (simToScale.drawSize[1]/simToScale.sizeScale)
            simToScale.viewOffset[0] -= dif[0]/2 #equalizes from the zoom to 'happen' from the middle of the screen
            simToScale.viewOffset[1] -= dif[1]/2

def handleAllWindowEvents(pygamesimInput): #input can be pygamesim object, 1D list of pygamesim objects or 2D list of pygamesim objects
    pygamesimInputList = []
    if(type(pygamesimInput) is (pygamesimLocal or pygamesimLocal)): #if it's actually a single input, not a list
        pygamesimInputList = [pygamesimInput] #convert to 1-sizes array
    elif(type(pygamesimInput) is list):
        if(len(pygamesimInput) > 0):
            for entry in pygamesimInput:
                if(type(entry) is list):
                    for subEntry in entry:
                        pygamesimInputList.append(subEntry) #2D lists
                else:
                    pygamesimInputList.append(entry) #1D lists
    #pygamesimInputList = pygamesimInput #assume input is list of pygamesims
    if(len(pygamesimInputList) < 1):
        print("len(pygamesimInputList) < 1")
        global windowKeepRunning
        windowKeepRunning = False
        pygame.event.pump()
        return()
    for eventToHandle in pygame.event.get(): #handle all events
        handleWindowEvent(pygamesimInputList, eventToHandle)
    #the manual keyboard driving (tacked on here, because doing it with the event system would require more variables, and this is temporary anyway)
    carToDrive = currentPygamesimInput(pygamesimInputList, demandMouseFocus=False).car #get the active sim within the window
    pressedKeyList = pygame.key.get_pressed()
    speedAccelVal = 0.015
    steerAccelVal = 0.002
    #first for speed
    if(pressedKeyList[pygame.K_UP]): #accelerate button
        carToDrive.velocity += speedAccelVal #accelerate
    elif(pressedKeyList[pygame.K_DOWN]): #brake/reverse button
        if(carToDrive.velocity > (speedAccelVal*3)): #positive speed
            carToDrive.velocity -= speedAccelVal * 3 #fast brake
        else:                               #near-zero or negative speed
            carToDrive.velocity -= speedAccelVal * 0.5 #reverse accelerate
    else:                           #neither buttons
        if(carToDrive.velocity > speedAccelVal): #positive speed
            carToDrive.velocity -= speedAccelVal/2 #slow brake
        elif(carToDrive.velocity < -speedAccelVal): #negative speed
            carToDrive.velocity += speedAccelVal #brake
        else:                           #near-zero speed
            carToDrive.velocity = 0
    carToDrive.velocity = max(-4, min(8, carToDrive.velocity)) #limit speed
    #now for steering
    if(pressedKeyList[pygame.K_LEFT] and (not pressedKeyList[pygame.K_RIGHT])):
        carToDrive.steering += steerAccelVal
    elif(pressedKeyList[pygame.K_RIGHT] and (not pressedKeyList[pygame.K_LEFT])):
        carToDrive.steering -= steerAccelVal
    else:
        if(carToDrive.steering > steerAccelVal):
            carToDrive.steering -= steerAccelVal*2.5
        elif(carToDrive.steering < -steerAccelVal):
            carToDrive.steering += steerAccelVal*2.5
        else:
            carToDrive.steering = 0
    carToDrive.steering = max(-np.pi/5, min(np.pi/5, carToDrive.steering)) #limit speed





if __name__ == '__main__':
    pygameInit()
    
    sim1 = pygamesimLocal(window) #just a basic class object with all default attributes
    
    while windowKeepRunning:
        handleAllWindowEvents(sim1) #handle all window events like key/mouse presses, quitting and most other things
        sim1.redraw()
        pygame.display.flip() #draw display
    
    pygameEnd()