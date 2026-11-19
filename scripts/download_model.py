#!/usr/bin/env python3
"""Pinned official GGUF download with mandatory checksum; no credentials."""
import hashlib
import os
import urllib.request
from pathlib import Path
REVISION='91cad51170dc346986eccefdc2dd33a9da36ead9'
NAME='qwen2.5-1.5b-instruct-q4_k_m.gguf'
SHA='6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e'
URL=f'https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/{REVISION}/{NAME}'
def digest(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for part in iter(lambda:f.read(1024*1024),b''):h.update(part)
 return h.hexdigest()
def main():
 folder=Path(os.environ.get('MODEL_DIR','.models'));folder.mkdir(parents=True,exist_ok=True);target=folder/NAME
 if target.exists() and digest(target)==SHA:print('Pesos verificados:',target);return
 temp=target.with_suffix('.download')
 print('Baixando 1,12 GB do repositório oficial fixado por revisão.')
 urllib.request.urlretrieve(URL,temp)
 if digest(temp)!=SHA:
  temp.unlink();raise SystemExit('Checksum incorreto; download descartado')
 temp.replace(target);print('Pesos verificados:',target)
if __name__=='__main__':main()
