#!/bin/sh

AUTH_ENDPOINT_PROD="http://api.int.janelia.org:8030/authenticate"
AUTH_ENDPOINT_DEV="https://jacs-dev.int.janelia.org/SCSW/AuthenticationService/v1/authenticate"
AUTH_ENDPOINT="${AUTH_ENDPOINT_DEV}"

username=$1
password=$2

curl -X POST "${AUTH_ENDPOINT}" -H  "accept: application/json" -H  "content-type: application/json" -d "{  \"username\": \"${username}\",  \"password\": \"${password}\"}"

