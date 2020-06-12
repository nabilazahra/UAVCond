import paho.mqtt.client as mqtt
import time
import random

def on_connect(client, userdata, flags, rc):
     client.connected_flag=True

def on_message(client, userdata, message):
   print("Message Recieved: "+message.payload.decode())

def on_publish(mosq, obj, mid):
    print("Publish count: " + str(mid))

#MQTT AUTHENTICATION
client = mqtt.Client()
client.username_pw_set("strmgqzh", "UX6QWdM_-8Vm")
client.connect('postman.cloudmqtt.com', 11876, 60)


client.on_connect = on_connect
client.on_message = on_message
client.on_publish = on_publish

client.loop_start()
run = True

#INFINITE LOOP COMING THROUGH

while run:
   client.publish("/flow", random.uniform(1.2, 1.6))
   client.publish("/pressure", random.uniform(7, 8))
   client.publish("/power", random.uniform(0.48, 0.58))
   client.publish("/temperature", random.uniform(40,62))
   client.publish("/hours", 10)
   time.sleep(15)

