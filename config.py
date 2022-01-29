from pymongo import MongoClient
import os
from dotenv import load_dotenv
import redis

redis_connection = redis.StrictRedis(host='localhost', port=6379, db=0)

load_dotenv()


client = MongoClient(port=27017)
db = client.edmin

SECRET_KEY = os.getenv('SECRET_KEY')
ALGORITHM = os.getenv('ALGORITHM')
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 30
