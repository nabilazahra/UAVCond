from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.shortcuts import render
from django.views.generic import View
import random
import sqlite3
import os.path 
import requests

from rest_framework.views import APIView
from rest_framework.response import Response


User = get_user_model()


# Import MQTT Libraries
import paho.mqtt.client as mqtt
import time
import random

#!!!INSERT STATIC VALUES HERE !!!

motorEffConstant = 94 #from datasheet
emissionFactor = 0.538 #kgCO2/kWh, SEI 2007 Average Generation Mix
staticDischargeHead = 6 #pump static discharge head pressure (m)
staticSuctionHead = 2 #pump static suction head pressure (m)
density = 997 #fluid density (kg/m3)
gravity = 9.81 #gravity (m/s2)

#BEST PRACTICE VALUES 
motorBestPractice = 96 #percent
pumpBestPractice = 85 #percent
pipingBestPractice = 100 #percent
overallBestPractice = (motorBestPractice*pumpBestPractice*pipingBestPractice)/10000

#Default value assigning

x=1 #flow
y=1 #pressure
z=1 #power
c=1 #temperature
d=1 #operatinghour

#START OF MQTT FUNCTIONS

def on_message_flow(client, userdata, msg):
	global x
	#print("Message Recieved: "+msg.payload.decode())
	x = float(msg.payload.decode())
	return x
	
def on_message_pressure(client, userdata, msg):
	global y
	y = float(msg.payload.decode())
	return y

def on_message_power(client, userdata, msg):
	global z
	z = float(msg.payload.decode())
	return z

def on_message_temperature(client, userdata, msg):
	global c
	c = float(msg.payload.decode())
	return c

def on_message_hours(client, userdata, msg):
	global d
	d = float(msg.payload.decode())
	return d

#MQTT AUTHENTICATION

client = mqtt.Client()
client.username_pw_set("strmgqzh", "UX6QWdM_-8Vm")
client.connect('postman.cloudmqtt.com', 11876, 60)


client.message_callback_add("/flow", on_message_flow)
client.message_callback_add("/pressure", on_message_pressure)
client.message_callback_add("/power", on_message_power)
client.message_callback_add("/temperature", on_message_temperature)
client.message_callback_add("/hours", on_message_hours)


client.loop_start()
run = True

#END OF MQTT FUNCTIONS

#FUNCTION FOR WARNING THROUGH TELEGRAM AND AUTHENTICATION

def telegram_bot_sendtext(bot_message):
    
    bot_token = '824161356:AAG0NefinjdMHkFTRvfQA7nBNk9HwU4tFvU'
    bot_chatID = 'chatID'
    send_text = 'https://api.telegram.org/bot' + bot_token + '/sendMessage?chat_id=' + bot_chatID + '&parse_mode=Markdown&text=' + bot_message

    response = requests.get(send_text)

    return response.json()

#END OF FUNCTION FOR WARNING THROUGH TELEGRAM

#START OF PUMP PERFORMANCE PARAMETER CALCULATIONS
def totalHeadCalc(pumpDischargePressure, staticSuctionHead):
    result = pumpDischargePressure + staticSuctionHead
    return result

def powerOutputCalc(density, gravity, totalHead, flow):
    result = (density * gravity * totalHead * flow)/367000
    return result

def effCalc(powerOutput, powerInput):
    result = (powerOutput *100)/powerInput
    return result

def frictionCalc(pumpDischargePressure, staticDischargeHead):
    result = pumpDischargePressure - staticDischargeHead
    return result

def volumeDisplacedCalc (flow, hours):
    result = flow * hours
    return result

def electricityCalc (powerInput, hours):
    result = powerInput * hours
    return result

def pipingEffCalc (pumpDischargePressure, staticDischargeHead):
    loss = (pumpDischargePressure-staticDischargeHead)/pumpDischargePressure
    result = (1-loss)*100
    return result

def gasEmittedCalc (electricity, emissionFactor):
    result = electricity * emissionFactor
    return result

def overallEfficiencyCalc(pumpEfficiency, pipingEfficiency, motorEfficiency):
    result = (pumpEfficiency * pipingEfficiency * motorEfficiency)/10000
    return result

def lossCalc(efficiency):
    result = (100 - efficiency)
    return result

def energyPerformanceIndicator1Calc(electricity, fluidVolume):
    return (electricity/fluidVolume)
 
def energyPerformanceIndicator2Calc(ePI1, staticDischarge, staticSuction):
    result = (ePI1*1000)/(staticDischarge+staticSuction)
    return result 

def energyPerformanceIndicator3Calc(ePI1, emissionFactor):
    result = ePI1*emissionFactor
    return result 

#END OF PUMP PERFORMACE PARAMETER CALCULATIONS

#START OF CLAUSAL PERFORMANCE CHECKS

def performanceClassCheck(overallEfficiency):
    if overallEfficiency > 70:
        return 'A'
    elif overallEfficiency > 65:
        return 'B'
    elif overallEfficiency > 55:
        return 'C'
    elif overallEfficiency > 45:
        return 'D'
    elif overallEfficiency > 35:
        return 'E'
    elif overallEfficiency > 25:
        return 'F'
    else:
        return 'G'

def causeCheck (flow, temperature, pressure):
    if flow > 1.5 and (pressure < 8.5 or pressure > 10.5) and temperature>60:
        return "Pump is overloaded and may Trip"
    elif pressure < 8.2:
        return "There is High Pressure Loss Happening"
    elif temperature > 60 and flow < 1.25:
        return "Pump is Dry Running"
    elif flow <1.23:
        return "There is a flow disturbance"
    else:
        return "No Warning"

def statusCheck (cause, efficiency):
    if cause != "No Warning":
        return "Warning"
    elif efficiency < 50:
        return "Pump might need reparation"
    else:
        return "System is running ok"

#END OF CLAUSAL PERFORMANCE CHECKS

#CLASS BASED VIEW for the /$ endpoint
class HomeView(View):
    def get(self, request, *args, **kwargs):
        return render(request, 'charts.html')


#GENERIC FUNCTION VIEW for the /api/data endpoint
def get_data(request, *args, **kwargs):
    data = {
        "sales": 100,
        "customers": randomScale(),
    }
    return JsonResponse(data) # http response

def randomScale():
    return random.uniform(0, 0.5)

#CLASS BASED VIEW for the /api/chart/data endpoint
class ChartData(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, format=None):
        qs_count = User.objects.all().count()
        client.subscribe("/flow",0)
        client.subscribe("/pressure", 0)
        client.subscribe("/power", 0)
        client.subscribe("/temperature", 0)
        client.subscribe("/hours", 0)
        
        data = {
                "flow": x,
                'pressure': y, #Pump discharge pressure
                'staticdischarge': staticDischargeHead,
                'staticsuction':staticSuctionHead,
                'totalhead': 0,
                "power": z,
                "temperature": c,
                "motoreff": motorEffConstant,
                "emissionfactor": emissionFactor,
                "hours": d,
                "density": density,
                "gravity": gravity,
                "powerOutput": 0,
                "friction":0,
                "volume":0,
                "energyloss": 0,
                "status": 'System is running ok',
                "cause": "System is running ok",
                "efficiency": 0,
                "electricity": 0,
                "piping": 0,
                "overallefficiency": 0,
                "gasemitted": 0,
                'performanceclass': '-',
                'pipingloss': 0,
                'motorloss': 0,
                'motorbestpractice': motorBestPractice,
                'pumpbestpractice': pumpBestPractice,
                'pipingbestpractice': pipingBestPractice,
                'overallbestpractice': overallBestPractice,
                'EPI1': 0,
                'EPI2':0,
                'EPI3':0,
                'EPI4':0,

        }

        data['totalhead'] = (totalHeadCalc(data['pressure'],data['staticsuction']))
        data['powerOutput'] = (powerOutputCalc(data['density'],data['gravity'],data['totalhead'],data['flow']))
        data['efficiency'] = (effCalc(data['powerOutput'],data['power']))
        data['friction'] = (frictionCalc(data['pressure'],data['staticdischarge']))
        data['volume'] = (volumeDisplacedCalc(data['flow'],data['hours']))
        data['electricity'] = (electricityCalc(data['power'],data['hours']))
        data['piping'] = (pipingEffCalc(data['pressure'],data['staticdischarge']))
        data['gasemitted'] = gasEmittedCalc(data['electricity'],data['emissionfactor'])
        data['cause'] = causeCheck(data['flow'], data['temperature'], data['totalhead'])
        data['overallefficiency'] = overallEfficiencyCalc(data['efficiency'],data['piping'], data['motoreff'])
        data['status'] = statusCheck(data['cause'], data['efficiency'])
        data['performanceclass'] = performanceClassCheck(data['overallefficiency'])
        data['energyloss'] = lossCalc(data['efficiency'])
        data['pipingloss'] = lossCalc(data['piping'])
        data['motorloss']= lossCalc(data['motoreff'])
        data['EPI1'] = energyPerformanceIndicator1Calc(data['electricity'],data['volume'])
        data['EPI2'] = energyPerformanceIndicator2Calc(data['EPI1'],data['staticdischarge'],data['staticsuction'])
        data['EPI3'] = energyPerformanceIndicator3Calc(data['EPI1'],data['emissionfactor'])
        data['EPI4'] = energyPerformanceIndicator2Calc(data['EPI3'],data['staticdischarge'],data['staticsuction'])
        

        BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        db_path = os.path.join(BASE_DIR, "database.db")
        sq = sqlite3.connect(db_path)
        r = sq.cursor()
        r.execute ("insert into measured values (?, ?, ?, ?, ?, datetime('now','localtime'));", (data['flow'], data['pressure'], data['power'], data['temperature'], data['hours']))
        sq.commit()
        r.execute("insert into static values (?, ?, ?, ?, ?, ?, datetime('now','localtime'));", (data['motoreff'],data['emissionfactor'],data['staticdischarge'],data['staticsuction'],data['gravity'], data['density']) )
        sq.commit()
        r.execute("insert into bestpractice values (?, ?, ?, ?, datetime('now','localtime'));", (data['motorbestpractice'],data['pumpbestpractice'],data['pipingbestpractice'],data['overallbestpractice']) )
        sq.commit()
        r.execute("insert into efficiency values (?, ?, ?, ?, ?, ?, ?, datetime('now','localtime'));", (data['piping'],data['efficiency'],data['motoreff'],data['overallefficiency'],data['pipingloss'], data['energyloss'],data ['motorloss']) )
        sq.commit()
        r.execute("insert into analytic values (?, ?, ?, ?, ?, ?, datetime('now','localtime'));", (data['totalhead'],data['powerOutput'],data['friction'],data['volume'], data['electricity'],data ['gasemitted']) )
        sq.commit()
        r.execute("insert into EPI values (?, ?, ?, ?, datetime('now','localtime'));", (data['EPI1'],data['EPI2'],data['EPI3'],data['EPI4']) )
        sq.commit()
        r.execute ("insert into status values (?, ?, ?, datetime('now', 'localtime'));", (data['status'], data['cause'],data['performanceclass']))
        sq.commit()
        sq.close()

        #if data['status'] != "System is running ok":
         #  telegram_bot_sendtext("Warning from Pump System: " + data['status'] + " Cause; "+ data['cause'])
        
        return Response(data)