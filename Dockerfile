FROM 539909726087.dkr.ecr.us-west-2.amazonaws.com/base-hardened-py:latest-alpine

WORKDIR /oic-collection-integration

RUN apk update && apk add gcc g++ python3-dev libffi-dev make curl
RUN apk --no-cache add libpq

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

RUN apk update && apk add bash

COPY . .
ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=UTF-8
EXPOSE 8080
EXPOSE 8443
CMD [ "./wrapper.sh" ]
