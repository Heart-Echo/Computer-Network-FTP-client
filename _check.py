import ssl,socket,os,re,time
from typing import Optional,Tuple,List
# read original
with open("ftp_core.py","r",encoding="utf-8") as f:
    c=f.read()
print("lines:",len(c.splitlines()))
print("has_content:",len(c)>0)
