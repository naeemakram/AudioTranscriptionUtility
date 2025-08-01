import os
from openai import OpenAI
import sys
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import time
import threading
import tkinter as tk

api_key = "
"

client = OpenAI(api_key=api_key)

prompt = f"""This is a test prompt"""

response = client.chat.completions.create(
    model="gpt-3.5-turbo",
    messages=[{
        "role":
        "system",
        "content":
        "You are a professional text editor. Format transcribed text with proper punctuation, capitalization, and paragraph breaks."
    }, {
        "role": "user",
        "content": prompt
    }],
    max_tokens=2000,
    temperature=0.1)
