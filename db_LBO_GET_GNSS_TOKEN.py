import requests
import time
from datetime import datetime
import pytz
import json


def GET_LBO_GNSS_Token():
    access_token = ""
    refresh_token = ""
    token_dict = {}
    current_utc_datetime = datetime.now(pytz.utc).strftime("%Y-%m-%d %H:%M:%S")
    print(current_utc_datetime)

    GNSS_URL = "https://hk-open.tracksolidpro.com/route/rest"

    access_token_params = {
        "method": "jimi.oauth.token.get",
        "timestamp": current_utc_datetime,
        "app_key": "8FB345B8693CCD00497CDAC6016483DF",
        "sign_method": "md5",
        "v": "0.9",
        "format": "json",
        "user_id": "GETT Technologies Pte Ltd",
        "user_pwd_md5": "e53463411b225eb75d394209ef1f523b",
        "expires_in": "7200",
    }

    tic = time.perf_counter()
    token_GET = requests.get(GNSS_URL, params=access_token_params)

    if token_GET.status_code == 200:
        print("GET GNSS Access Token success.")
        print(token_GET.text)
        token_GET_list = json.loads(token_GET.text)
        if token_GET_list["code"] == 1006:
            print(
                'Too frequent token request, "code":1006,"message":"Illegal access, request frequency is too high","result":null,"data":null}'
            )
            return "0"

        access_token = token_GET_list["result"]["accessToken"]
        refresh_token = token_GET_list["result"]["accessToken"]
        token_dict["access_token"] = access_token
        token_dict["refresh_token"] = refresh_token
        print(token_dict)
    else:
        print(f"Failed to get GNSS Access Token. Status code: {token_GET.status_code}")

    toc = time.perf_counter()
    print(f"PULL duration for GNSS Access Token in {toc - tic:0.4f} seconds")
    print(f"token_dict = {token_dict}")
    return token_dict
