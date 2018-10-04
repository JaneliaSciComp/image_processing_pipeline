#!/bin/bash
sudo systemctl start mongod
source 'lightsheetInterface/env/bin/activate'
cd lightsheetInterface
python run.py
