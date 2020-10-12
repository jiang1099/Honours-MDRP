#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Aug  6 15:43:43 2020

@author: Tristan
"""

# Import data
# TODO: If desired, have the ability to cut out some of the data
# TODO: (Fix) Find all order sequences
# TODO: Find all sequence+restaurant pairs, dominating while calculating
# TODO: Dominate order sequences
# TODO: Create untimed arcs
# TODO: Create model nodes
# TODO: Convert untimed arcs to timed arcs (as variables)
# TODO: Add model constraints
# TODO: Solve linear model
# TODO: Add valid inequality cuts in callback
# TODO: Solve integer model
# TODO: Add illegal path elimination constraints in callback

import math
from collections import defaultdict
import itertools
from time import time
from gurobi import Model, quicksum, GRB

from operator import lt, gt

courierData = {} # x y ontime offtime
orderData = {} # x y placementtime restaurant readytime latestLeavingTime maxClickToDoorArrivalTime
restaurantData = {} # x y

grubhubInstance = '0o50t100s1p125'
fileDirectory = 'MealDeliveryRoutingGithub/public_instances/' + grubhubInstance + '/'
programStartTime = time()

nodeTimeInterval = 8 # minutes between nodes
groupCouriersByOffTime = True

def WithoutLetters(string):
    return string.translate({ord(i): None for i in 'abcdefghijklmnopqrstuvwxyz'})

def OpenFile(fileName):
    with open(fileDirectory + fileName) as file:
        # Get lines, dropping header line
        lines = file.read().splitlines()[1:]
        dataDictionary = {}
        for line in lines:
            data = map(WithoutLetters, line.split('\t'))
            data = list(map(int, data))
            dataDictionary[data[0]] = data[1:]
        return dataDictionary

courierData = OpenFile('couriers.txt')
orderData = OpenFile('orders.txt')
restaurantData = OpenFile('restaurants.txt')
print(str(len(courierData)) + ' couriers')
print(str(len(orderData)) + ' orders')
print(str(len(restaurantData)) + ' restaurants')

def GiveMeAStatusUpdate(label, collectionToDisplayLengthOf):
    print(str(len(collectionToDisplayLengthOf)) + ' ' + label + ' ' + str(time() - programStartTime))

with open(fileDirectory + 'instance_parameters.txt') as instanceParameters:
    instanceParameters.readline().strip()
    parameters = instanceParameters.readline().strip().split('\t')
    travelSpeed = int(parameters[0]) # metres per minute
    pickupServiceTime = int(parameters[1]) # minutes
    dropoffServiceTime = int(parameters[2]) # minutes
    targetClickToDoor = int(parameters[3]) # minutes
    maxClickToDoor = int(parameters[4]) # minutes
    payPerDelivery = int(parameters[5]) # dollars
    minPayPerHour = int(parameters[6]) # dollars

ordersAtRestaurant = {restaurant: [] for restaurant in restaurantData}
for order in orderData:
    ordersAtRestaurant[orderData[order][3]].append(order)

courierGroups = {}
if groupCouriersByOffTime:
    for courier in courierData:
        offTime = courierData[courier][3]
        if offTime not in courierGroups:
            courierGroups[offTime] = [[], offTime]
        courierGroups[offTime][0].append(courier)
else:
    for courier in courierData:
        courierGroups[courier] = [[courier], courierData[courier][3]]
globalOffTime = max(courierGroups[group][1] for group in courierGroups)

def TravelTime(loc1, loc2):
    x1, y1 = loc1[0], loc1[1]
    x2, y2 = loc2[0], loc2[1]
    return math.sqrt((x1-x2)**2 + (y1-y2)**2) / travelSpeed

for order in orderData:
    maxClickToDoorArrivalTime = orderData[order][2] + maxClickToDoor
    travelTime = (pickupServiceTime + dropoffServiceTime) / 2 + TravelTime(restaurantData[orderData[order][3]], orderData[order])
    orderData[order].append(maxClickToDoorArrivalTime - travelTime)
    orderData[order].append(maxClickToDoorArrivalTime)

def CompareOneIndex(op, dictionary, key1, key2, index):
    return op(dictionary[key1][index], dictionary[key2][index])

def CompareTwoIndices(op1, op2, dictionary, key1, key2, index1, index2):
    return CompareOneIndex(op1, dictionary, key1, key2, index1) and CompareOneIndex(op2, dictionary, key1, key2, index2)

def RemoveDominatedSequences(sequences):
    sequencesBySetAndLastOrder = defaultdict(list)
    for sequence in sequences:
        sequencesBySetAndLastOrder[(frozenset(sequence), sequence[-1])].append(sequence)
    dominatedSequences = set()
    for group in sequencesBySetAndLastOrder:
        if len(sequencesBySetAndLastOrder[group]) > 1:
            for (sequence1, sequence2) in itertools.combinations(sequencesBySetAndLastOrder[group],2):
                if CompareTwoIndices(gt, lt, sequences, sequence1, sequence2, 2, 3):
                    dominatedSequences.add(sequence2)
                elif CompareTwoIndices(lt, gt, sequences, sequence1, sequence2, 2, 3):
                    dominatedSequences.add(sequence1)
    for sequence in dominatedSequences:
        del sequences[sequence]
    return sequences

orderDeliverySequences = {} # orderSequence: [restaurant, earliestLeavingTime, latestLeavingTime, totalTravelTime]
sequenceNextRestaurantPairs = {} # (sequence, nextRestaurant): [restaurant, earliestLeavingTime, latestLeavingTime, totalTravelTime]
for restaurant in restaurantData:
    sequenceLength = 1
    calculatedSequences = {}
    for order in ordersAtRestaurant[restaurant]:
        calculatedSequences[(order,)] = [restaurant, orderData[order][4], orderData[order][5], TravelTime(restaurantData[restaurant], orderData[order]) + (pickupServiceTime + dropoffServiceTime) / 2]
    for sequence in calculatedSequences:
        orderDeliverySequences[sequence] = calculatedSequences[sequence]
    while len(calculatedSequences) > 0:
        sequenceLength += 1
        newSequences = {}
        for sequence in calculatedSequences:
            for order in ordersAtRestaurant[restaurant]:
                if order not in sequence:
                    newSequence = sequence + (order,)
                    totalTravelTime = orderDeliverySequences[sequence][3] + dropoffServiceTime + TravelTime(orderData[sequence[-1]], orderData[order])
                    latestLeavingTime = min(orderDeliverySequences[sequence][2], orderData[order][6] - totalTravelTime)
                    earliestLeavingTime = max(orderDeliverySequences[sequence][1], orderData[order][4])
                    if earliestLeavingTime <= latestLeavingTime:
                        newSequences[newSequence] = [restaurant, earliestLeavingTime, latestLeavingTime, totalTravelTime]
        if sequenceLength >= 3:
            newSequences = RemoveDominatedSequences(newSequences)
        calculatedSequences = newSequences
        for sequence in calculatedSequences:
            orderDeliverySequences[sequence] = calculatedSequences[sequence]
        if len(calculatedSequences) == 0:
            break

sequencesByRestaurantThenOrderSet = {}
for sequence in orderDeliverySequences:
    restaurant = orderDeliverySequences[sequence][0]
    if restaurant not in sequencesByRestaurantThenOrderSet:
        sequencesByRestaurantThenOrderSet[restaurant] = defaultdict(list)
    sequencesByRestaurantThenOrderSet[restaurant][frozenset(sequence)].append(sequence)
GiveMeAStatusUpdate('delivery sequences', orderDeliverySequences)

def CheckDominationPairs(sequenceToCheck, nextRestaurant):
    # TODO: Maybe use this function in the previous domination checking function?
    dominatedSequences = []
    for sequence in groupedPairs[(frozenset(sequenceToCheck), nextRestaurant)]:
        if sequence != sequenceToCheck:
            if CompareTwoIndices(lt, gt, sequenceNextRestaurantPairs, (sequenceToCheck, nextRestaurant), (sequence, nextRestaurant), 2, 3):
                return [sequenceToCheck]
            if CompareTwoIndices(gt, lt, sequenceNextRestaurantPairs, (sequenceToCheck, nextRestaurant), (sequence, nextRestaurant), 2, 3):
                dominatedSequences.append(sequence)
    return dominatedSequences

sequenceNextRestaurantPairs = {} # (sequence, nextRestaurant): [restaurant, earliestLeavingTime, latestLeavingTime, totalTravelTime]
groupedPairs = defaultdict(list) # (frozenset(sequence), nextRestaurant): [sequence1, sequence2, sequence3, ...]
# TODO: combine this with sequence generation in an efficient manner
for sequence in orderDeliverySequences:
    finishTime = orderDeliverySequences[sequence][1] + orderDeliverySequences[sequence][3]
    for restaurant in restaurantData:
        arrivalAtRestaurant = finishTime + TravelTime(orderData[sequence[-1]], restaurantData[restaurant]) + (dropoffServiceTime + pickupServiceTime) / 2
        for order in ordersAtRestaurant[restaurant]:
            if orderData[order][5] > arrivalAtRestaurant:
                travelTime = orderDeliverySequences[sequence][3] + TravelTime(orderData[sequence[-1]], restaurantData[restaurant]) + (dropoffServiceTime + pickupServiceTime) / 2
                sequenceNextRestaurantPairs[(sequence, restaurant)] = orderDeliverySequences[sequence][:3] + [travelTime]
                groupedPairs[(frozenset(sequence), restaurant)].append(sequence)
                dominatedSequences = CheckDominationPairs(sequence, restaurant)
                for dominatedSequence in dominatedSequences:
                    del sequenceNextRestaurantPairs[(dominatedSequence, restaurant)]
                    groupedPairs[(frozenset(sequence), restaurant)].remove(dominatedSequence)
                break
GiveMeAStatusUpdate('post-domination pairs', sequenceNextRestaurantPairs)

untimedArcs = set() # {(offTime1, sequence1, nextRestaurant1), (offTime2, sequence2, nextRestaurant2), ...}
# Main untimedArcs
for pair in sequenceNextRestaurantPairs:
    leavingRestaurant, earliestLeavingTime, latestLeavingTime, totalTravelTime = sequenceNextRestaurantPairs[pair]
    earliestArrivalTime = earliestLeavingTime + totalTravelTime
    for group in courierGroups:
        offTime = courierGroups[group][1]
        if offTime > earliestLeavingTime:
            variableForOffTime = False
            for courier in courierGroups[group][0]:
                courierDatum = courierData[courier]
                if earliestArrivalTime > courierDatum[3]: # check that the courier is still in-shift when arriving at next restaurant
                    continue
                commute = TravelTime(courierDatum, restaurantData[leavingRestaurant])
                if courierDatum[2] + commute + pickupServiceTime / 2 < latestLeavingTime:
                    if courierDatum[3] > earliestLeavingTime:
                        for order in ordersAtRestaurant[pair[1]]:
                            orderDatum = orderData[order]
                            if orderDatum[4] < courierDatum[3] and orderDatum[5] > earliestArrivalTime:
                                untimedArcs.add((group,) + pair)
                                variableForOffTime = True
                                break
                if variableForOffTime:
                    break
GiveMeAStatusUpdate('main untimedArcs', untimedArcs)
# Exit untimedArcs
# Create sequence-courier (off time) pairs, with nextRestaurant = 0
for sequence in orderDeliverySequences:
    restaurant, earliestLeavingTime, latestLeavingTime, totalTravelTime = orderDeliverySequences[sequence]
    for group in courierGroups:
        offTime = courierGroups[group][1]
        # off time after earliest ready time
        if offTime > earliestLeavingTime:
            # check that there is a courier that is on for this sequence
            # courier must be able to get to restaurant before latest leaving time
            for courier in courierGroups[group][0]:
                courierDatum = courierData[courier]
                if courierDatum[2] < latestLeavingTime: # added for hopefully a small speed-up?
                    if courierDatum[2] + TravelTime(courierDatum, restaurantData[restaurant]) + pickupServiceTime / 2 < latestLeavingTime:
                        untimedArcs.add((group, sequence, 0))
                        break
GiveMeAStatusUpdate('main + exit untimedArcs', untimedArcs)
# Entry untimedArcs
# Create courier (off time) pairs, with sequence = ()
for group in courierGroups:
    for courier in courierGroups[group][0]:
        for restaurant in restaurantData:
            earliestArrival = courierData[courier][2] + TravelTime(courierData[courier], restaurantData[restaurant]) + pickupServiceTime / 2
            if earliestArrival < courierData[courier][3]:
                for order in ordersAtRestaurant[restaurant]:
                    if orderData[order][5] > courierData[courier][2] and orderData[order][4] < courierData[courier][3]:
                        untimedArcs.add((group, (), restaurant))
GiveMeAStatusUpdate('all untimedArcs', untimedArcs)
untimedArcsByCourierRestaurant = defaultdict(list)
# (offTime, departureRestaurant): [(offTime, sequence1, nextRestaurant1), (offTime, sequence2, nextRestaurant2), ...]
for arc in untimedArcs:
    if arc[1] == ():
        untimedArcsByCourierRestaurant[(arc[0], 0)].append(arc)
    else:
        untimedArcsByCourierRestaurant[(arc[0], orderData[arc[1][0]][3])].append(arc)

nodesInModel = set()
# {(offTime1, restaurant1, time1), (offTime2, restaurant2, time2), ...}
for group in courierGroups:
    offTime = courierGroups[group][1]
    for restaurant in restaurantData:
        earliestArrivalTime = min(courierData[courier][2] + TravelTime(courierData[courier], restaurantData[restaurant]) + pickupServiceTime / 2 for courier in courierGroups[group][0])
        if earliestArrivalTime > offTime:
            continue
        deliverableOrders = set(order for order in ordersAtRestaurant[restaurant] if orderData[order][4] < offTime and orderData[order][5] > earliestArrivalTime)
        if len(deliverableOrders) == 0:
            continue
        latestNodeTime = min(max(orderData[order][5] for order in deliverableOrders), offTime)
        earliestNodeTime = max(min(orderData[order][4] for order in deliverableOrders), earliestArrivalTime)
        if earliestNodeTime > latestNodeTime:
            print('error!', group, restaurant, earliestNodeTime, latestNodeTime, earliestArrivalTime)
        currentTime = earliestNodeTime
        while currentTime < latestNodeTime:
            nodesInModel.add((group, restaurant, currentTime))
            currentTime += nodeTimeInterval
GiveMeAStatusUpdate('nodes generated', nodesInModel)
for group in courierGroups:
    offTime = courierGroups[group][1]
    nodesInModel.add((offTime, 0, 0))
    nodesInModel.add((offTime, 0, globalOffTime))

nodesByOfftimeRestaurantPair = defaultdict(list)
# (offTime, departureRestaurant): [(offTime, departureRestaurant, time1), (offTime, departureRestaurant, time2), ...]
for node in nodesInModel:
    nodesByOfftimeRestaurantPair[node[:2]].append(node)
timedArcs = set()
# An arc is defined by a (courierOffTime, restaurant1, time1, orderSequence, restaurant2, time2) sextuple
# time2 is a function of time1, orderSequence, restaurant2
for pair in untimedArcsByCourierRestaurant:
    offTime, departureRestaurant = pair
    if pair[1] != 0:
        for arc in untimedArcsByCourierRestaurant[pair]:
            sequence = arc[1]
            nextRestaurant = arc[2]
            if nextRestaurant != 0:
                earliestDepartureTime, latestDepartureTime, travelTime = sequenceNextRestaurantPairs[(sequence, nextRestaurant)][1:]
                earliestArrivalTime = earliestDepartureTime + travelTime
                latestArrivalTime = latestDepartureTime + travelTime
                nodesForArrivingPair = nodesByOfftimeRestaurantPair[pair[0], nextRestaurant]
                nodesForLeavingPair = list(node for node in nodesByOfftimeRestaurantPair[pair] if node[2] <= latestDepartureTime)
                if len(nodesForLeavingPair) == 0:
                    # TODO: Find out why this happens, maybe because the sequence is too long, and so is no longer a valid route?
                    continue
                if len(nodesForArrivingPair) == 0: # TODO: rather than add a node, go to the next/first node
                    nodesInModel.add((offTime, nextRestaurant, latestArrivalTime))
                    latestDepartureNodeTime = max(node2[2] for node2 in nodesForLeavingPair)
                    timedArcs.add((offTime, departureRestaurant, latestDepartureNodeTime, sequence, nextRestaurant, latestArrivalTime))
                else:
                    prevArc = None
                    for node in nodesForLeavingPair:
                        if node[2] >= min(node2[2] for node2 in nodesForArrivingPair) - travelTime: # latest permitted leaving time to arrive at one of the arriving nodes
                            arrivalTime = node[2] + travelTime
                            arrivalNodeTime = max(node2[2] for node2 in nodesForArrivingPair if node2[2] <= arrivalTime)
                            if prevArc!=None and arrivalNodeTime==prevArc[-1]:
                                timedArcs.remove(prevArc)
                            prevArc = (offTime, departureRestaurant, node[2], sequence, nextRestaurant, arrivalNodeTime)
                            timedArcs.add(prevArc)
GiveMeAStatusUpdate('pre-domination main timed arcs', timedArcs)

# Waiting arcs
def NodeTime(node):
    return node[2]
for pair in nodesByOfftimeRestaurantPair:
    nodeList = nodesByOfftimeRestaurantPair[pair]
    if len(nodeList) > 0:
        nodeList.sort(key = NodeTime)
        for i in range(1, len(nodeList)):
            timedArcs.add((pair[0], pair[1], nodeList[i-1][2], (), pair[1], nodeList[i][2]))
GiveMeAStatusUpdate('main + waiting arcs', timedArcs)

# Entry arcs
for pair in nodesByOfftimeRestaurantPair:
    if len(nodesByOfftimeRestaurantPair[pair]) > 0:
        earliestNodeTimeAtRestaurant = min(node[2] for node in nodesByOfftimeRestaurantPair[pair])
        timedArcs.add((pair[0], 0, 0, (), pair[1], earliestNodeTimeAtRestaurant))
GiveMeAStatusUpdate('main + waiting + entry arcs', timedArcs)

# Exit arcs
for pair in nodesByOfftimeRestaurantPair:
    if len(nodesByOfftimeRestaurantPair[pair]) > 0 and pair[1] != 0:
        for orderSet in sequencesByRestaurantThenOrderSet[pair[1]]:
            sequences = sequencesByRestaurantThenOrderSet[pair[1]][orderSet]
            latestLeavingTime = max(orderDeliverySequences[sequence][2] for sequence in sequences)
            if min(node[2] for node in nodesByOfftimeRestaurantPair[pair]) > latestLeavingTime: continue
            latestLeavingNodeTime = max(node[2] for node in nodesByOfftimeRestaurantPair[pair] if node[2] < latestLeavingTime)
            for sequence in sequences:
                if orderDeliverySequences[sequence][2] >= latestLeavingNodeTime:
                    timedArcs.add((pair[0], pair[1], latestLeavingNodeTime, sequence, 0, globalOffTime))
GiveMeAStatusUpdate('timed arcs', timedArcs)

print()
m = Model('MDRP')
m.setParam('Method', 2)

arcsByDepartureNode = defaultdict(list)
arcsByArrivalNode = defaultdict(list)
arcsByCourier = defaultdict(list)
arcsByOrder = {o:[] for o in orderData}
outArcsByCourier = defaultdict(list)
for arc in timedArcs:
    (c,r1,t1,s,r2,t2) = arc
    if t2 > t1: # This condition is a hacky solution to the existence of incorrect arcs
        if r1:
            arcsByDepartureNode[(c,r1,t1)].append(arc)
        else:
            if t1 == 0:
                if s != ():
                    print('leaving home arc with orders!', arc)
                outArcsByCourier[c].append(arc)
        if r2:
            arcsByArrivalNode[(c,r2,t2)].append(arc)
        arcsByCourier[c].append(arc)
        for o in arc[3]:
            arcsByOrder[o].append(arc)

arcs = {arc: m.addVar(vtype=GRB.INTEGER) for arc in timedArcs if arc[2] < arc[5]}
GiveMeAStatusUpdate('arcs', arcs)

payments = {group: m.addVar() for group in courierGroups}
GiveMeAStatusUpdate('payments', payments)

m.setObjective(quicksum(payments[c] for c in courierGroups))

flowConstraint = {node:
          m.addConstr(quicksum(arcs[arc] for arc in arcsByDepartureNode[node]) ==
                      quicksum(arcs[arc] for arc in arcsByArrivalNode[node])
          )
      for node in nodesInModel}
GiveMeAStatusUpdate('main flow constrants', flowConstraint)

homeArcs = {c: m.addConstr(quicksum(arcs[arc] for arc in outArcsByCourier[c]) <= len(courierGroups[c])) for c in courierGroups}
GiveMeAStatusUpdate('home constraints', homeArcs)

deliverOrders = {o: m.addConstr(quicksum(arcs[arc] for arc in arcsByOrder[o]) == 1) for o in orderData}
GiveMeAStatusUpdate('order constraints', deliverOrders)

arcsIffLeaveHome = {c: m.addConstr(quicksum(arcs[arc] for arc in arcsByCourier[c]) <= quicksum(arcs[arc] for arc in arcsByCourier[c] if not arc[1] if arc[4]) * len(timedArcs)) for c in courierGroups}
GiveMeAStatusUpdate('deliver only if leave home', arcsIffLeaveHome)

paidPerDelivery = {c: m.addConstr(payments[c] >= quicksum(arcs[arc] * len(arc[3]) * payPerDelivery for arc in arcsByCourier[c])) for c in courierGroups}
GiveMeAStatusUpdate('courier payments per delivery', paidPerDelivery)
paidPerTime = {c: m.addConstr(payments[c] >= quicksum((courierData[courier][3] - courierData[courier][2]) * minPayPerHour / 60 for courier in courierGroups[c][0])) for c in courierGroups}
GiveMeAStatusUpdate('courier payments per time', paidPerTime)

def ArcDeparture(arc):
    return arc[2]
def ArcArrival(arc):
    return arc[5]

# def ComputeAndRemoveIllegalPaths(listOfArcs, courierGroup):
#     arcStats = {} # untimedArc: departureRestaurant, earliestDepartureTime, latestDepartureTime, durationOfTravel, arrivalRestaurant
#     for timedArc in listOfArcs:
#         _, departureRestaurant, _, orderSequence, arrivalRestaurant, _ = timedArc
#         newArc = (departureRestaurant, orderSequence, arrivalRestaurant)
#         if departureRestaurant == 0: # TODO: Confirm that this duration of travel is for the closest courier
#             earliestArrivalTime = min(courierData[courier][2] + TravelTime(courierData[courier], restaurantData[arrivalRestaurant]) for courier in courierGroups[courierGroup][0]) + pickupServiceTime / 2
#             durationOfTravel = min(TravelTime(courierData[courier], restaurantData[arrivalRestaurant]) for courier in courierGroups[courierGroup][0]) + pickupServiceTime / 2
#             earliestDepartureTime = earliestArrivalTime - durationOfTravel
#             latestDepartureTime = courierGroups[group][1] - durationOfTravel
#         elif arrivalRestaurant == 0:
#             _, earliestDepartureTime, latestDepartureTime, durationOfTravel = orderDeliverySequences[orderSequence]
#         else:
#             _, earliestDepartureTime, latestDepartureTime, durationOfTravel = sequenceNextRestaurantPairs[orderSequence, arrivalRestaurant]
#         arcStats[newArc] = (departureRestaurant, earliestDepartureTime, latestDepartureTime, durationOfTravel, arrivalRestaurant)
#     arcsWithTheirPredecessors = defaultdict(list)
#     arcsWithTheirSuccessors = defaultdict(list)
#     for arc1, arc2 in itertools.combinations(arcStats, 2):
#         if arcStats[arc1][1] + arcStats[arc1][3] <= arcStats[arc2][2]: # arc1 arrive before arc2 leaves
#             if arcStats[arc1][4] == arcStats[arc2][0]: # arc1 arrival restaurant is arc2 departure restaurant
#                 arcsWithTheirPredecessors[arc2].append(arc1) # arc1 is a predecessor of arc2
#                 arcsWithTheirSuccessors[arc1].append(arc2)
#         if arcStats[arc2][1] + arcStats[arc2][3] <= arcStats[arc1][2]:
#             if arcStats[arc2][4] == arcStats[arc2][0]:
#                 arcsWithTheirPredecessors[arc1].append(arc2)
#                 arcsWithTheirSuccessors[arc2].append(arc1)
    
#     IPD = Model('Illegal Path Determination')
#     X = {(arc,successor): IPD.addVar(vtype=GRB.BINARY) for arc in arcsWithTheirSuccessors for successor in arcsWithTheirSuccessors[arc]}
#     T = {arc: IPD.addVar() for arc in arcStats}
#     leaveAfterEarlyTime = {arc: IPD.addConstr(T[arc] >= arcStats[arc][1]) for arc in arcStats}
#     leaveBeforeLateTime = {arc: IPD.addConstr(T[arc] <= arcStats[arc][2]) for arc in arcStats}
#     enoughTimeForBothArcs = {(i,j): IPD.addConstr(T[i]+arcStats[i][3] <= T[j]+(arcStats[i][2]+arcStats[i][3]-arcStats[j][1])*(1-X[i,j])) for (i,j) in X}
#     entryArcsUsedOnce = {i: IPD.addConstr(quicksum(X[i,j] for j in arcsWithTheirSuccessors[i]) == 1) for i in arcsWithTheirSuccessors}
#     exitArcsUsedOnce = {j: IPD.addConstr(quicksum(X[i,j] for i in arcsWithTheirPredecessors[j]) == 1) for j in arcsWithTheirPredecessors}
#     IPD.optimize()
#     if infeasible:
#         IPD.computeIIS()
# [k for k in entryArcsUsedOnce if entryArcsUsedOnce[k].IISConstr]        
#         # usedConstrs = []
#         # constrs = IPD.getConstrs()
#         # for i in range(len(IPD.IISCONSTR)):
#         #     if IPD.IISCONSTR[i] == 1:
#         #         usedConstrs.append(constrs[i])
#         IISArcs = []
#         for arc in IISArcs:
#             # find the timed arc that used this untimed arc
#             # determine all possible successor timed arcs to the timed arc *that are not turned on*
#             # store these successor arcs for each untimed arc in this loop
#         # add a constraint: m.addConstr(quicksum(timedArcsUsingTheseUntimedArcs) <= number - 1 + currentlyUnusedSuccessorTimedArcs)
#         return True
#     return False

# def RemoveInvalidRoutes():
#     usedArcs = {arc: arcs[arc].x for arc in arcs if arcs[arc].x > 0 and (arc[3] != () or arc[1] == 0)}
#     usedArcsByGroup = defaultdict(list)
#     for arc in usedArcs:
#         usedArcsByGroup[arc[0]].append(arc)
#     didAddNewConstraints = False
#     for group in courierGroups:
#         didAddNewConstraints = didAddNewConstraints or ComputeAndRemoveIllegalPaths(usedArcsByGroup[group], group)
#     return didAddNewConstraints

m.optimize()

print('Time = ' + str(time() - programStartTime))

# TODO: Remove arcs that go backwards in time
# TODO: Remove duplicate on-off arcs
