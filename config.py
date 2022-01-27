from pymongo import MongoClient


client = MongoClient(port=27017)
db = client.edmin
