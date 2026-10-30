import os, threading, time, datetime, math
from flask import Flask
import telebot

BOT_TOKEN = os.getenv("BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN")
LOT_SIZE = 65
SL_RUPEES = 2000
TRAILING_PTS = 25
INSTRUMENTS = ["NIFTY","BANKNIFTY","SENSEX","NIFTY50","RELIANCE"]
SKILLS = ["trader-scanner","trader-news","trader-entry","trader-exit","trader-timemachine","trader-risk","trader-budget","trader-broker","trader-alerts","trader-analyst","trader-pelosi"]

app = Flask(__name__)
positions = {}

def calculate_vwap(candles):
    tpv = sum(((c['high']+c['low']+c['close'])/3)*c['volume'] for c in candles)
    tv = sum(c['volume'] for c in candles)
    return tpv/tv if tv else 0

def get_historical_data(symbol):
    d = {
        "NIFTY": [{"high":24650,"low":24400,"close":24580,"volume":1200000},{"high":24700,"low":24500,"close":24600,"volume":1500000}],
        "BANKNIFTY": [{"high":52000,"low":51500,"close":51800,"volume":900000},{"high":52200,"low":51700,"close":52000,"volume":1100000}],
        "SENSEX": [{"high":81000,"low":80500,"close":80800,"volume":800000},{"high":81200,"low":80700,"close":81000,"volume":1000000}],
        "NIFTY50": [{"high":24650,"low":24400,"close":24580,"volume":1200000},{"high":24700,"low":24500,"close":24600,"volume":1500000}],
        "RELIANCE": [{"high":2950,"low":2900,"close":2930,"volume":5000000},{"high":2970,"low":2920,"close":2950,"volume
