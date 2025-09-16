FROM python:3.9-alpine
RUN  pip install pandas requests
WORKDIR /app
COPY Livetrade.py /app
COPY LIVE.json /app
RUN apk add curl jq 
CMD [ "python3.9" ,"Livetrade.py"]