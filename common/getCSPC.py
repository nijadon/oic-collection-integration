import requests
import os
#import logging
from dotenv import load_dotenv

load_dotenv()

url=os.environ.get('OIC_CF_URL')
jwtTokenUrl=os.environ.get('JWT_TOKEN_URL')
jwtClientId=os.environ.get('JWT_CLIENT_ID')
jwtClientSecret=os.environ.get('JWT_CLIENT_SECRET')

def get_CSPC_Id(logger,remoteNodeid,uploadType):

    try:
        """
        # Authorizer needs to be added
        """
        authorizer_headers_dict = {"Content-Type": "application/x-www-form-urlencoded"}
        param_dict = {"client_id":jwtClientId,"client_secret":jwtClientSecret,"grant_type":"client_credentials","scope":"api.customer.assets.manage"}
        r=requests.post(jwtTokenUrl, headers=authorizer_headers_dict,params=param_dict)
        authorization = "Bearer "+r.json()['access_token']
        headers_dict = {"RemoteNodeID": remoteNodeid, "Authorization": authorization}
        #print(headers_dict)
        print("Calling oic mapping service API")
        response = requests.get(url, headers=headers_dict)
        #print(response.headers)
        #print(response.reason)
        #print(response.content)
        if response.status_code==200:
            records=response.json()['records']
            for record in records:
                if(record['UploadType'].upper() == uploadType.upper()):
                    return record['CSPCId']
            logger.error("CSPC Id not found")
        elif response.status_code==403:
            logger.info(f"Error while trying to access get mapping api with status code 403\n{response.reason}")
            
    except Exception as e:
        logger.error("CSPC Id not found")
        return None
    return None
"""
if __name__ == "__main__":
    print("Running")
    uri="CXCA/CXCA/devices/date=20211207/customerId=07071952/1cd94b56-5b15-466e-a3fd-0aa5b4bbcf63_1638835616556_cxdl-ingestion-manifest.json"
    remoteNodeId=uri[uri.rindex("/")+1:].split('_')[0]
    uploadType="DNAC"
    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
    logger = logging.getLogger(__name__)
    print(get_CSPC_Id(logger,remoteNodeId,uploadType))
"""