from sqlalchemy import create_engine, text
import pandas as pd
import os
import json
import folium
import leafmap.foliumap as leafmap
import random
import requests
from pprint import pprint
from datetime import datetime, timedelta
import pytz
import time


def merge_VF_df_ETA_df(VF_df, ETA_df):
    VF_df["imoNumber"] = VF_df["imoNumber"].astype(int)
    ETA_df["vesselParticulars.imoNumber"] = ETA_df[
        "vesselParticulars.imoNumber"
    ].astype(int)
    VF_ETA_df = pd.merge(
        VF_df,
        ETA_df,
        left_on=VF_df["imoNumber"],
        right_on=ETA_df["vesselParticulars.imoNumber"],
        how="left",
    )

    VF_ETA_df.rename(
        columns={
            "duetoArriveTime": "ETA - MPA",
            "dueToDepart": "ETD - MPA",
            "locationTo": "DESTINATION - MPA",
            "DESTINATION": "DESTINATION - VesselFinder",
        },
        inplace=True,
    )
    desired_column_order = [
        "imoNumber",
        "NAME",
        "DESTINATION - VesselFinder",
        "DESTINATION - MPA",
        "ETA - VesselFinder",
        "ETA - MPA",
        "ETD - MPA",
        "callsign",
        "speed",
        "timeStamp",
        "latitudeDegrees",
        "longitudeDegrees",
        "heading",
    ]
    VF_ETA_df = VF_ETA_df[desired_column_order]
    return VF_ETA_df


def delete_all_rows_vessel_location(db_creds):
    print(
        "Start of delete_all_rows_vessel_location 3 tables: vessel_movement_UCE, vessel_current_position_UCE, MPA_vessel_data......"
    )
    engine = create_engine(
        db_creds, connect_args={"ssl": {"ssl_ca": "/etc/ssl/cert.pem"}}
    )
    with engine.connect() as conn:
        query_VCP = text("DELETE FROM vessel_current_position_UCE where id > 0")
        result_VCP = conn.execute(query_VCP)
        conn.commit()
        print("Deleted vessel_current_position_UCE where id > 0")
        query_MPA = text("DELETE FROM MPA_vessel_data WHERE id > 0")
        result_MPA = conn.execute(query_MPA)
        conn.commit()
        print("Deleted MPA_vessel_data where id > 0")
        query_pilotage_service = text("DELETE FROM pilotage_service_UCE WHERE id > 0")
        result_pilotage_service = conn.execute(query_pilotage_service)
        conn.commit()
        print("Deleted pilotage_service where id > 0")


# Store data into MPA_vessel_data from GET
def MPA_GET(api_response, gsheet_cred_path):
    data_list = json.loads(api_response)
    print(f"db_Vessel_data_pull.py MPA_GET data_list == {data_list}")
    # print(f"API response = {(data_list)}")
    # print(f"API response[0] = {data_list[0]}")
    vessel_data = data_list[0]["vesselParticulars"]
    # print(f"vessel_data = {vessel_data}")
    print(f"vessel_data['vesselName'] = {vessel_data['vesselName']}")
    print(f"vessel_data['callSign'] = {vessel_data['callSign']}")
    latitude = data_list[0]["latitude"]
    print(f"latitude = {data_list[0]['latitude']}")
    longitude = data_list[0]["longitude"]
    latitude_degrees = data_list[0]["latitudeDegrees"]
    longitude_degrees = data_list[0]["longitudeDegrees"]
    speed = data_list[0]["speed"]
    course = data_list[0]["course"]
    heading = data_list[0]["heading"]
    timestamp = data_list[0]["timeStamp"]

    query = text(
        "INSERT INTO MPA_vessel_data (vesselName, callSign, imoNumber, flag, vesselLength, vesselBreadth, vesselDepth, vesselType, grossTonnage, netTonnage, deadweight, mmsiNumber, yearBuilt, latitude, longitude, latitudeDegrees, longitudeDegrees, speed, course, heading, timeStamp) VALUES (:vesselName, :callSign, :imoNumber, :flag, :vesselLength, :vesselBreadth, :vesselDepth, :vesselType, :grossTonnage, :netTonnage, :deadweight, :mmsiNumber, :yearBuilt, :latitude, :longitude, :latitudeDegrees, :longitudeDegrees, :speed, :course, :heading, :timeStamp)"
    )
    values = {
        "vesselName": vessel_data["vesselName"],
        "callSign": vessel_data["callSign"],
        "imoNumber": vessel_data["imoNumber"],
        "flag": vessel_data["flag"],
        "vesselLength": vessel_data["vesselLength"],
        "vesselBreadth": vessel_data["vesselBreadth"],
        "vesselDepth": vessel_data["vesselDepth"],
        "vesselType": vessel_data["vesselType"],
        "grossTonnage": vessel_data["grossTonnage"],
        "netTonnage": vessel_data["netTonnage"],
        "deadweight": vessel_data["deadweight"],
        "mmsiNumber": vessel_data["mmsiNumber"],
        "yearBuilt": vessel_data["yearBuilt"],
        "latitude": latitude,
        "longitude": longitude,
        "latitudeDegrees": latitude_degrees,
        "longitudeDegrees": longitude_degrees,
        "speed": speed,
        "course": course,
        "heading": heading,
        "timeStamp": timestamp,
    }
    engine_MPA_GET = create_engine(
        gsheet_cred_path, connect_args={"ssl": {"ssl_ca": "/etc/ssl/cert.pem"}}
    )
    with engine_MPA_GET.connect() as conn:
        MPA_Data = conn.execute(query, values)
        conn.commit()
    return MPA_Data


# ============= GET 2 API's from MPA: VCP + VDA ===================
# ============= PULL 2 API's from SGTD: VCP + VDA =================
def GET_MPA_VCP_PULL_SGTD(
    input_list,
    session_pitstop,
    session_gc,
    session_participant_id,
    session_api_key,
    session_imo_not_found,
):
    current_datetime = datetime.now().strftime("%Y-%m-%d")
    for vessel_imo in input_list:
        print(f"db_Vessel_data_pull.py PULL_GET_VCP_VDA_MPA IMO Number = {vessel_imo}")

        # url_vessel_movement = f"{session_pitstop}/api/v1/data/pull/vessel_movement"
        url_vessel_current_position = (
            f"{session_pitstop}/api/v1/data/pull/vessel_current_position"
        )
        url_vessel_due_to_arrive = (
            f"{session_pitstop}/api/v1/data/pull/vessel_due_to_arrive"
        )
        url_MPA_VCP = (
            f"https://sg-mdh-api.mpa.gov.sg/v1/vessel/positions/imonumber/{vessel_imo}"
        )

        ##################### START Make the GET request for MPA_vessel_data table LOCATION VCP ALT  #####################
        API_KEY_MPA = "QgCv2UvINPRfFqbbH3yVHRVVyO8Iv5CG"
        MPA_VCP_GET = requests.get(url_MPA_VCP, headers={"Apikey": API_KEY_MPA})

        # Check the response
        if MPA_VCP_GET.status_code == 200:
            print(
                "db_Vessel_data_pull.py url_MPA_VCP Config Data retrieved successfully!"
            )
            # Store GET data from MPA into MPA_vessel_data table table
            MPA_GET(MPA_VCP_GET.text, session_gc)
        else:
            NOT_FOUND_LIST = session_imo_not_found
            NOT_FOUND_LIST.append(vessel_imo)
            session_imo_not_found = NOT_FOUND_LIST
            print(f"Failed to get Config Data. Status code: {MPA_VCP_GET.status_code}")
        ##################### END Make the GET request for MPA_vessel_data table LOCATION VCP ALT  #####################

        ##################### START PULL SGTD VCP and VDA: Threaded  #####################
        # print("Start PULL_SGTD_VCP_VDA thread...")
        # print(datetime.now())
        # threading.Thread(
        #     target=PULL_VCP_VDA_SGTD,
        #     args=(
        #         session_participant_id,
        #         vessel_imo,
        #         current_datetime,
        #         url_vessel_current_position,
        #         url_vessel_due_to_arrive,
        #         session_api_key,
        #     ),
        # ).start()
        # print("End PULL_SGTD_VCP_VDA  thread...")
        # print(datetime.now())
        ##################### END PULL SGTD VCP and VDA: Threaded  #####################


# Merge database data for MAP
def get_MPA_vessel_location_data_SQL_data(db_creds):
    print("db_Vessel_data_pull: get_map_data(db_creds): Start of get_map_data......")
    engine = create_engine(
        db_creds, connect_args={"ssl": {"ssl_ca": "/etc/ssl/cert.pem"}}
    )
    with engine.connect() as conn:
        # Select MPA_vessel_data
        query = text("select * from MPA_vessel_data")
        result_MPA_vessel_data = conn.execute(query)
        result_all_MPA_vessel_data = result_MPA_vessel_data.fetchall()
        column_names_MPA_vessel_data = result_MPA_vessel_data.keys()
        print(result_all_MPA_vessel_data)
        print(f"length of MPA_vessel_data = {len(result_all_MPA_vessel_data)}")
        MPA_vessel_data_df = pd.DataFrame(
            result_all_MPA_vessel_data, columns=column_names_MPA_vessel_data
        )
        # sorting by first name
        MPA_vessel_data_df.drop_duplicates(
            subset="imoNumber", keep="last", inplace=True
        )
        return [MPA_vessel_data_df]


def get_data_from_VF_vessels(imo_list):
    single_vessel_positions_df = pd.DataFrame()
    print(
        "db_Vessel_map.py: get_data_from_VF_vessels(imo_list): Start of get_data_from_single_vessel_positions............."
    )
    print(f"input_list = {imo_list}")

    api_key = "WS-00555FCD-8CD037"

    base_url = f"https://api.vesselfinder.com/vessels?userkey={api_key}"

    VF_ais_response = requests.get(f"{base_url}&imo={imo_list}")
    VF_ais_data = VF_ais_response.json()

    for entry in VF_ais_data:
        # Access the timestamp and parse it into a datetime object
        print(
            f"db_Vessel_map.py: get_data_from_VF_vessels(imo_list): entry in VF_ais_response = {VF_ais_data}"
        )
        timestamp_str = entry["AIS"]["TIMESTAMP"]
        eta_str = entry["AIS"]["ETA"]
        print(
            f"db_Vessel_map.py: get_data_from_VF_vessels(imo_list): timestamp_str = {timestamp_str}"
        )
        print(
            f"db_Vessel_map.py: get_data_from_VF_vessels(imo_list): eta_str = {eta_str}"
        )
        if timestamp_str == "":
            entry["AIS"]["TIMESTAMP"] = ""
        else:
            timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S UTC")
            # Add 8 hours to the timestamp
            new_timestamp = timestamp + timedelta(hours=8)
            print(
                f"db_Vessel_map.py: get_data_from_VF_vessels(imo_list): New timestamp = {new_timestamp}"
            )
            # Format the new timestamp back into the desired string format
            new_timestamp_str = new_timestamp.strftime("%Y-%m-%d %H:%M:%S")
            print(
                f"db_Vessel_map.py: get_data_from_VF_vessels(imo_list): new_timestamp_str = {new_timestamp_str}"
            )
            entry["AIS"]["TIMESTAMP"] = new_timestamp_str
        if eta_str == "":
            entry["AIS"]["TIMESTAMP"] = ""
        else:
            eta = datetime.strptime(eta_str, "%Y-%m-%d %H:%M:%S")
            # Add 8 hours to the timestamp
            new_eta = eta + timedelta(hours=8)
            print(
                f"db_Vessel_map.py: get_data_from_VF_vessels(imo_list): New ETA = {new_eta}"
            )
            new_eta_str = new_eta.strftime("%Y-%m-%d %H:%M:%S")
            print(
                f"db_Vessel_map.py: get_data_from_VF_vessels(imo_list): new_eta_str = {new_eta_str}"
            )
            entry["AIS"]["ETA"] = new_eta_str

    # Print the updated JSON response

    print(
        f"db_Vessel_map.py: get_data_from_VF_vessels(imo_list): Changed timestamp version: {VF_ais_data}"
    )
    print(
        f"db_Vessel_map.py: get_data_from_VF_vessels(imo_list): Type of VF_ais_response = {type(VF_ais_data)}"
    )

    if VF_ais_response.status_code == 200:
        print(
            "db_Vessel_map.py: get_data_from_VF_vessels(imo_list): converted VF_ais_data"
        )
        if VF_ais_data == {"error": "Expired account!"}:
            VF_ais_data = []
            return ["VesselFinder Expired"]
        else:
            VF_ais_data = VF_ais_data
    else:
        VF_ais_data = pd.DataFrame()
    print(
        f"db_Vessel_map.py: get_data_from_VF_vessels(imo_list): VF_ais_data = {VF_ais_data}"
    )
    if len(VF_ais_data) > 0:
        VF_ais_info = [entry["AIS"] for entry in VF_ais_data]
        single_vessel_positions_df = pd.DataFrame(VF_ais_info)
        print(
            f"db_Vessel_map.py: get_data_from_VF_vessels(imo_list): single_vessel_positions_df = {single_vessel_positions_df}"
        )
        single_vessel_positions_df.rename(
            columns={
                "MMSI": "mmsiNumber",
                "TIMESTAMP": "timeStamp",
                "LATITUDE": "latitudeDegrees",
                "LONGITUDE": "longitudeDegrees",
                "IMO": "imoNumber",
                "CALLSIGN": "callsign",
                "ETA": "ETA - VesselFinder",
                "HEADING": "heading",
                "SPEED": "speed",
                "COURSE": "course",
            },
            inplace=True,
        )
        single_vessel_positions_df.drop(
            columns=[
                "A",
                "B",
                "C",
                "D",
                "ECA",
                "LOCODE",
                "SRC",
                "DRAUGHT",
                "NAVSTAT",
            ],
            inplace=True,
        )
        # Reorder columns in place
        desired_column_order = [
            "NAME",
            "callsign",
            "imoNumber",
            "mmsiNumber",
            "latitudeDegrees",
            "longitudeDegrees",
            "ETA - VesselFinder",
            "DESTINATION",
            "DISTANCE_REMAINING",
            "course",
            "speed",
            "heading",
            "timeStamp",
        ]
        single_vessel_positions_df = single_vessel_positions_df[desired_column_order]
        # print(VF_ais_info)
        print(
            f"db_Vessel_map.py: get_data_from_VF_vessels(imo_list): Final single_vessel_positions_df = {single_vessel_positions_df}"
        )
    return single_vessel_positions_df


def get_data_from_vessel_due_to_arrive_and_depart():
    print("Start of get_data_from_vessel_due_to_arrive_and_depart........")

    # Define your local time zone (UTC+9)
    local_timezone = pytz.timezone("Asia/Singapore")
    # Get the current date and time in UTC
    current_utc_datetime = datetime.now(pytz.utc)

    # Convert the current UTC time to your local time zone
    current_local_datetime = current_utc_datetime.astimezone(local_timezone)
    today_datetime = current_local_datetime.strftime("%Y-%m-%d %H:%M:%S")

    url_MPA_due_to_arrive = f"https://sg-mdh-api.mpa.gov.sg/v1/vessel/duetoarrive/date/{today_datetime}/hours/99"
    url_MPA_due_to_depart = f"https://sg-mdh-api.mpa.gov.sg/v1/vessel/duetodepart/date/{today_datetime}/hours/99"

    API_KEY_MPA = "QgCv2UvINPRfFqbbH3yVHRVVyO8Iv5CG"

    MPA_due_to_arrive_GET = requests.get(
        url_MPA_due_to_arrive, headers={"Apikey": API_KEY_MPA}
    )
    # Check the response
    if MPA_due_to_arrive_GET.status_code == 200:
        print(
            "db_table_view_request.py: get_data_from_vessel_due_to_arrive_and_depart(): Arrive Data retrieved successfully!"
        )
        # query and values
        dueToArrive_Data = json.loads(MPA_due_to_arrive_GET.text)
        arrive_df = pd.json_normalize(dueToArrive_Data)
    else:
        print("Failed to get vessel_due_to_arrive data")

    MPA_due_to_depart_GET = requests.get(
        url_MPA_due_to_depart, headers={"Apikey": API_KEY_MPA}
    )
    # Check the response
    if MPA_due_to_depart_GET.status_code == 200:
        print(
            "db_table_view_request.py: get_data_from_vessel_due_to_arrive_and_depart(): Depart Data retrieved successfully!"
        )
        # query and values
        dueToDepart_Data = json.loads(MPA_due_to_depart_GET.text)
        depart_df = pd.json_normalize(dueToDepart_Data)
    else:
        print("Failed to get vessel_due_to_depart data")

    merged_df = arrive_df.merge(depart_df, on="vesselParticulars.imoNumber", how="left")
    merged_df.drop(
        columns=[
            "vesselParticulars.vesselName_y",
            "vesselParticulars.vesselName_y",
            "vesselParticulars.flag_y",
            "vesselParticulars.callSign_y",
        ],
        inplace=True,
    )
    print(f"get_data_from_vessel_due_to_arrive_and_depart.merge_df = {merged_df}")
    return merged_df


def merge_MPA_vessel_data_df_ETA_df(MPA_vessel_data_df, ETA_df):
    MPA_vessel_data_df_ETA_df = pd.merge(
        MPA_vessel_data_df,
        ETA_df,
        left_on=MPA_vessel_data_df["imoNumber"],
        right_on=ETA_df["vesselParticulars.imoNumber"],
        how="left",
    )
    print(
        f"db_Vessel_map.py: merge_MPA_vessel_data_df_ETA_df(MPA_vessel_data_df, ETA_df): MPA_vessel_data_df merged ETA_df = {MPA_vessel_data_df_ETA_df}"
    )
    MPA_vessel_data_df_ETA_df.to_excel("final_df_ETA_df.xlsx")
    MPA_vessel_data_df_ETA_df.rename(
        columns={
            "vesselName": "NAME",
            "duetoArriveTime": "ETA - MPA",
            "dueToDepart": "ETD - MPA",
            "locationTo": "DESTINATION - MPA",
        },
        inplace=True,
    )
    # Reorder columns in place
    desired_column_order = [
        "NAME",
        "callsign",
        "imoNumber",
        "mmsiNumber",
        "latitudeDegrees",
        "longitudeDegrees",
        "ETA - MPA",
        "ETD - MPA",
        "DESTINATION - MPA",
        "course",
        "speed",
        "heading",
        "timeStamp",
    ]
    MPA_vessel_data_df_ETA_df = MPA_vessel_data_df_ETA_df[desired_column_order]
    return MPA_vessel_data_df_ETA_df


def update_row(row):
    if not pd.isna(row["longitudeDegrees_y"]):
        row["longitudeDegrees"] = row["longitudeDegrees_y"]
        row["latitudeDegrees"] = row["latitudeDegrees_y"]
        row["heading"] = row["heading_y"]
        row["speed"] = row["speed_y"]
        row["timeStamp"] = row["timeStamp_y"]
        row["NAME"] = row["vesselName"]
        row["callsign"] = row["callSignMPA"]
    else:
        row["longitudeDegrees"] = row["longitudeDegreesVF"]
        row["latitudeDegrees"] = row["latitudeDegreesVF"]
        row["heading"] = row["headingVF"]
        row["speed"] = row["speedVF"]
        row["timeStamp"] = row["timeStampVF"]
    return row


def merged_MPA_VF_ETA_df(MPA_vessel_data_df, VF_df, ETA_df):
    print(
        f"db_Vessel_map.py: merged_MPA_VF_ETA_df(MPA_vessel_data_df, VF_df, ETA_df): merged_MPA_VF_ETA_df MPA_vessel_data_df = {MPA_vessel_data_df}"
    )
    print(
        f"db_Vessel_map.py: merged_MPA_VF_ETA_df(MPA_vessel_data_df, VF_df, ETA_df): merged_MPA_VF_ETA_df VF_df= {VF_df}"
    )
    print(
        f"db_Vessel_map.py: merged_MPA_VF_ETA_df(MPA_vessel_data_df, VF_df, ETA_df): MPA dueToArrive/depart df = {ETA_df}"
    )
    MPA_vessel_data_df.rename(
        columns={
            "callsign": "callSignMPA",
        },
        inplace=True,
    )
    pprint(
        f"db_Vessel_map.py: merged_MPA_VF_ETA_df(final_df, VF_df, ETA_df): MPA_vessel_data_df renamed = {MPA_vessel_data_df}"
    )

    ETA_df.to_excel("ETA_df.xlsx")
    MPA_vessel_data_df.to_excel("MPA_vessel_location_data_df..xlsx")

    MPA_vessel_data_df["imoNumber"] = MPA_vessel_data_df["imoNumber"].astype(int)
    VF_df["imoNumber"] = VF_df["imoNumber"].astype(int)
    ETA_df["vesselParticulars.imoNumber"] = ETA_df[
        "vesselParticulars.imoNumber"
    ].astype(int)

    VF_ETA_df = pd.merge(
        VF_df,
        ETA_df,
        left_on=VF_df["imoNumber"],
        right_on=ETA_df["vesselParticulars.imoNumber"],
        how="left",
    )
    print(
        f"db_Vessel_map.py: merged_MPA_VF_ETA_df(final_df, VF_df, ETA_df): VF_df merged ETA_df = {VF_ETA_df}"
    )

    if VF_ETA_df.empty:
        VF_ETA_df = VF_df

    Final_df = VF_ETA_df.merge(
        MPA_vessel_data_df, how="outer", on="imoNumber", suffixes=("VF", "_y")
    )
    Final_df.to_excel("Merged before drop Final_df.xlsx")
    Final_df = Final_df.apply(update_row, axis=1)

    Final_df.to_excel("Final_df.xlsx")
    print(
        f"db_Vessel_map.py: merged_MPA_VF_ETA_df(final_df, VF_df, ETA_df): Final_df = {Final_df}"
    )
    # Reorder columns in place
    if set(["duetoArriveTime", "dueToDepart"]).issubset(Final_df.columns):
        desired_column_order = [
            "imoNumber",
            "NAME",
            "DESTINATION",
            "locationTo",
            "ETA - VesselFinder",
            "duetoArriveTime",
            "dueToDepart",
            "callsign",
            "flag",
            "speed",
            "timeStamp",
            "latitudeDegrees",
            "longitudeDegrees",
            "heading",
        ]
    else:
        desired_column_order = [
            "imoNumber",
            "NAME",
            "DESTINATION",
            "ETA - VesselFinder",
            "callsign",
            "flag",
            "speed",
            "timeStamp",
            "latitudeDegrees",
            "longitudeDegrees",
            "heading",
        ]
    Final_df = Final_df[desired_column_order]
    print(
        f"db_Vessel_map.py: merged_MPA_VF_ETA_df(final_df, VF_df, ETA_df): Final_df = {Final_df}"
    )
    # Rename Final_df
    if set(["duetoArriveTime", "dueToDepart"]).issubset(Final_df.columns):
        Final_df.rename(
            columns={
                "duetoArriveTime": "ETA - MPA",
                "dueToDepart": "ETD - MPA",
                "locationTo": "DESTINATION - MPA",
                "DESTINATION": "DESTINATION - VesselFinder",
            },
            inplace=True,
        )
    else:
        Final_df.rename(
            columns={
                "DESTINATION": "DESTINATION - VesselFinder",
            },
            inplace=True,
        )

    return Final_df


def GET_LBO_GNSS_Data(imeis, access_token, refresh_token):
    access_token = access_token
    refresh_token = refresh_token
    GNSS_URL = "https://hk-open.tracksolidpro.com/route/rest"
    current_utc_datetime = datetime.now(pytz.utc).strftime("%Y-%m-%d %H:%M:%S")
    print(f"imeis = {imeis}")
    pull_params = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_in": 7200,
        "imeis": imeis,
        "method": "jimi.device.location.get",
        "timestamp": current_utc_datetime,
        "app_key": "8FB345B8693CCD00497CDAC6016483DF",
        "sign_method": "md5",
        "v": "0.9",
        "format": "json",
        "map_type": "GOOGLE",
    }
    tic = time.perf_counter()
    GNSS_GET = requests.get(GNSS_URL, params=pull_params)
    if GNSS_GET.status_code == 200:
        # print(f"GNSS_GET.text = {GNSS_GET.text}")
        GNSS_GET_list = json.loads(GNSS_GET.text)
    else:
        print(f"Failed to get GNSS Data. Status code: {GNSS_GET.status_code}")
    toc = time.perf_counter()
    print(f"PULL duration for GNSS Data {len(imeis)} in {toc - tic:0.4f} seconds")

    lbo_result = []

    for item in GNSS_GET_list["result"]:
        # print(f'GNSS_GET_list["result"] = {item}')
        imei = item["imei"]
        lat = item["lat"]
        long = item["lng"]
        direction = item["direction"]
        gps_time = item["gpsTime"]
        lbo_dict = {}
        lbo_dict["imei"] = imei
        lbo_dict["lat"] = lat
        lbo_dict["long"] = long
        lbo_dict["direction"] = direction
        lbo_dict["gpsTime"] = gps_time
        lbo_result.append(lbo_dict)
        # print(f"lbo_result = {lbo_result}")
        # print(f"lbo_dict = {lbo_dict}")

    # Print the dictionary
    # print("lbo_result", lbo_result)
    return lbo_result  # Return the list of dictionaries


def display_lbo_map(df1, df2):
    print(
        "db_GNSS.py: display_lbo_map(df1, df2): Starting display_lbo_map in db_GNSS.py.........."
    )
    with open("templates/Banner.html", "r") as file:
        menu_banner_html = file.read()

    with open("templates/Banner Vessel Map.html", "r") as file:
        menu_banner_body_html = file.read()
    if df1.empty and df2.empty:
        print(
            f"db_GNSS.py: display_lbo_map(df1, df2): disaply map: Empty df1 and df2................"
        )
        current_datetime = datetime.now().strftime("%Y%m%d%H%M%S")
        for f in os.listdir("templates/"):
            if "lbomap.html" in f:
                print(
                    f"db_GNSS.py: display_lbo_map(df1, df2): *lbomap.html file to be removed = {f}"
                )
                os.remove(f"templates/{f}")

        m = leafmap.Map(center=[1.257167, 103.897], zoom=9)
        regions = "templates/SG_anchorages.geojson"
        m.add_geojson(
            regions,
            layer_name="SG Anchorages",
            style={
                "color": (random.choice(colors)),
                "fill": True,
                "fillOpacity": 0.05,
            },
        )
        newHTML = f"templates/{current_datetime}lbomap.html"
        newHTMLwotemp = f"{current_datetime}lbomap.html"
        print(
            f"db_GNSS.py: display_lbo_map(df1, df2): new html file created = {newHTML}"
        )
        m.to_html(newHTML)
        with open(newHTML, "r") as file:
            html_content = file.read()
        html_content = html_content.replace(
            "<style>#map {position:absolute;top:0;bottom:0;right:0;left:0;}</style>",
            menu_banner_html,
        )
        html_content = html_content.replace("<body>", menu_banner_body_html)
        with open(newHTML, "w") as file:
            file.write(html_content)
        return [1, newHTMLwotemp]  # render_template(
        #     newHTMLwotemp,
        #     user=session["email"],
        #     IMO_NOTFOUND=session["IMO_NOTFOUND"],
        # )

    else:
        # Edit here, remove df1 and merge df, keep df2. Alter drop coulmns based on print
        # print(f"df1 LBO_map = {df1}")
        # print(f"df2 Vessel_map = {df2}")
        df = df1
        m = folium.Map(location=[1.257167, 103.897], zoom_start=5)
        color_mapping = {}
        ship_image = "static/images/ship.png"
        # Add several LBO markers to the map
        if not df1.empty:
            for index, row in df.iterrows():
                imo_number = row["imei"]
                # Assign a color to the imoNumber, cycling through the available colors
                if imo_number not in color_mapping:
                    color_mapping[imo_number] = colors[len(color_mapping) % len(colors)]
                icon_color = color_mapping[imo_number]
                icon_html = folium.DivIcon(
                    html=f'<i class="fa fa-arrow-up" style="color: {icon_color}; font-size: 17px; transform: rotate({row["direction"]}deg);"></i>'
                )
                popup_html = f"<b>Vessel Info</b><br>"
                for key, value in row.items():
                    popup_html += f"<b>{key}:</b> {value}<br>"
                folium.Marker(
                    location=[row["lat"], row["long"]],
                    popup=folium.Popup(html=popup_html, max_width=300),
                    icon=icon_html,  # folium.DivIcon(html=icon_html),
                    angle=float(row["direction"]),
                    spin=True,
                ).add_to(m)

        # Add several VESSEL markers to the map
        if not df2.empty:
            for index, row in df2.iterrows():
                imo_number = row["imoNumber"]
                # Assign a color to the imoNumber, cycling through the available colors
                if imo_number not in color_mapping:
                    color_mapping[imo_number] = colors[len(color_mapping) % len(colors)]
                icon_color = color_mapping[imo_number]
                # if int(row["yearBuilt"]) > 2010:
                icon_html = folium.DivIcon(
                    html=f'<i class="fa fa-arrow-circle-up" style="color: {icon_color}; font-size: 20px; transform: rotate({row["heading"]}deg);"></i>'
                )
                # else:
                #     # icon_html = f'<i class="fa fa-ship" style="color: {icon_color}; font-size: {int(row["vesselLength"])/10}px; transform: rotate({row["heading"]}deg);"></i>'
                #     icon_html = folium.CustomIcon(
                #         icon_image=ship_image,
                #         icon_size=(50, 50),  # You can adjust the size
                #         icon_anchor=(25, 25),
                #     )
                popup_html = f"<b>{row['NAME']} ({row['callsign']})</b><br>"
                for key, value in row.items():
                    if (
                        key != "NAME"
                        and key != "callsign"
                        and key != "heading"
                        and key != "latitudeDegrees"
                        and key != "longitudeDegrees"
                    ):
                        popup_html += f"<b>{key}:</b> {value}<br>"
                folium.Marker(
                    location=[row["latitudeDegrees"], row["longitudeDegrees"]],
                    popup=folium.Popup(html=popup_html, max_width=300),
                    icon=icon_html,  # folium.DivIcon(html=icon_html),
                    angle=float(row["heading"]),
                    spin=True,
                ).add_to(m)

        # Geojson url
        geojson_url = "templates/SG_anchorages.geojson"

        # Desired styles
        style = {"fillColor": "red", "color": "blueviolet"}

        # Geojson
        geojson_layer = folium.GeoJson(
            data=geojson_url,
            name="geojson",
            style_function=lambda x: style,
            highlight_function=lambda x: {"fillOpacity": 0.3},
            popup=folium.GeoJsonPopup(fields=["NAME"], aliases=["Name"]),
        ).add_to(m)

        # Add legend
        item_txt = """<br> &nbsp; {item1} &nbsp; <i class="fa fa-arrow-circle-up" style="color:{col1}"></i><br> &nbsp; {item2} &nbsp; <i class="fa fa-arrow-up" style="color:{col2}"></i>"""
        html_itms = item_txt.format(
            item1="Vessel", col1="black", item2="Lighter Boat", col2="black"
        )

        legend_html = """
            <div style="
            position: fixed; 
            bottom: 50px; left: 50px; width: 200px; height: 70px; 
            border:2px solid grey; z-index:9999; 
            
            background-color:white;
            opacity: .85;
            
            font-size:14px;
            font-weight: bold;
            
            ">
            &nbsp; {title} 
            
            {itm_txt}

            </div> """.format(
            title="Legend html", itm_txt=html_itms
        )
        m.get_root().html.add_child(folium.Element(legend_html))

        for f in os.listdir("templates/"):
            # print(f)
            if "lbomap.html" in f:
                print(f"*lbomap.html file to be removed = {f}")
                os.remove(f"templates/{f}")

        current_datetime = datetime.now().strftime("%Y%m%d%H%M%S")
        newHTML = rf"templates/{current_datetime}lbomap.html"
        m.save(newHTML)
        with open(newHTML, "r") as file:
            html_content = file.read()

        # Add the menu banner HTML code to the beginning of the file
        html_content = html_content.replace(
            "<style>#map {position:absolute;top:0;bottom:0;right:0;left:0;}</style>",
            menu_banner_html,
        )
        html_content = html_content.replace("<body>", menu_banner_body_html)

        # Write the modified HTML content back to the file
        with open(newHTML, "w") as file:
            file.write(html_content)

        newHTMLrender = f"{current_datetime}lbomap.html"
        return [2, newHTMLrender]


colors = [
    "red",
    "blue",
    "green",
    "purple",
    "orange",
    "darkred",
    "lightred",
    "beige",
    "darkblue",
    "darkgreen",
    "cadetblue",
    "darkpurple",
    "white",
    "pink",
    "lightblue",
    "lightgreen",
    "gray",
    "black",
    "lightgray",
]
