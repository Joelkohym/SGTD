from sqlalchemy import create_engine, text
import pandas as pd
import json
from datetime import datetime
import requests
import os

# db_connection_string = os.environ['DB_CONNECTION_STRING']
# db_connection_string = "mysql+pymysql://2j104pgpfhay9dokc46k:pscale_pw_fiA5JrG88BcLgKuQmmK9WZHjaOlzf2BkRisjOD6FDn6@aws.connect.psdb.cloud/sgtd?charset=utf8mb4"
db_connection_string = os.environ["DB_CONNECTION_STRING"]
engine = create_engine(
    db_connection_string, connect_args={"ssl": {"ssl_ca": "/etc/ssl/cert.pem"}}
)


# def new_registration(email, password, api_key, participant_id, on_behalf_id, gsheet_cred_path, company):
def new_registration(data):
    print(f"printing data from new_registration: {data}")
    print(f"data['email'] == {data['email']}")
    print(f"data['api_key'] == {data['api_key']}")
    print(f"data['participant_id'] == {data['participant_id']}")
    email = data["email"]
    password = data["password"]
    with engine.connect() as conn:
        query = text("select * from userDB WHERE email = :email")
        values = {"email": email}
        result = conn.execute(query, values)
        result_all = result.all()
        print(result_all)
        print(f"length of result all = {len(result_all)}")
        if len(result_all) == 0:
            query = text(
                "INSERT INTO userDB (email, password, api_key, participant_id, pitstop_url, gsheet_cred_path) VALUES (:email,:password, :api_key, :participant_id, :pitstop_url, :gsheet_cred_path)"
            )
            values = {
                "email": data["email"],
                "password": data["password"],
                "api_key": data["api_key"],
                "participant_id": data["participant_id"],
                "pitstop_url": data["pitstop_url"],
                "gsheet_cred_path": data["gsheet_cred_path"],
            }
            print(query)
            result = conn.execute(query, values)
            conn.commit()
            print(result)
            print("execute success")
            return 1
        else:
            print("User exists, please try again")
            return 0
        # conn.execute(query, email = data['email'],password =data['password'],api_key = data['api_key'],participant_id = data['participant_id'],on_behalf_id_ = data['on_behalf_id_'],gsheet_cred_path = data['gsheet_cred_path'], company_ = data['company_'])


def validate_login(email, password):
    print(f"printing data from validate_login: email = {email}, password = {password}")
    try:
        with engine.connect() as conn:
            query = text(
                "SELECT * FROM userDB WHERE email = :email AND password = :password"
            )
            values = {"email": email, "password": password}
            check_login = conn.execute(query, values)
            login_entry = check_login.all()[0]
            print(f"check_login == {login_entry}")
            print(f"check_login TYPE == {type(login_entry)}")
            print(f"check_login_API == {login_entry[3]}")
            result_login = len(login_entry)
            print(login_entry[3], login_entry[4], login_entry[5])
            print(f"result_login == {result_login}")
            return (
                login_entry[0],
                login_entry[3],
                login_entry[4],
                login_entry[5],
                login_entry[6],
            )
    except:
        return [0]


def receive_details(email):
    with engine.connect() as conn:
        query = text("SELECT * FROM userDB WHERE email = :email")
        values = {"email": email}
        receive_db = conn.execute(query, values)
        receive_data = receive_db.all()[0]
        # print(f"receive_data == {receive_data}, return api ={receive_data[3]}, return pID = {receive_data[4]}, return pitstop = {receive_data[5]}")
    return (
        receive_data[0],
        receive_data[3],
        receive_data[4],
        receive_data[5],
        receive_data[6],
    )


#######################################################        START RECEIVED DATA FROM API     #######################################################
def new_vessel_current_position(data, email, gsheet_cred_path):
    engine_vcp = create_engine(
        gsheet_cred_path, connect_args={"ssl": {"ssl_ca": "/etc/ssl/cert.pem"}}
    )
    with engine_vcp.connect() as conn:
        query_vcp = text(
            """
    INSERT INTO vessel_current_position_UCE (vessel_nm,vessel_imo_no,vessel_call_sign,vessel_flag,vessel_length,vessel_depth,vessel_type,vessel_grosstonnage,vessel_nettonnage,vessel_deadweight,vessel_mmsi_number,vessel_year_built,vessel_latitude,vessel_longitude,vessel_latitude_degrees,vessel_longitude_degrees,vessel_speed,vessel_course,vessel_heading,vessel_time_stamp
    ) VALUES (:vessel_nm,:vessel_imo_no,:vessel_call_sign,:vessel_flag,:vessel_length,:vessel_depth,:vessel_type,:vessel_grosstonnage,:vessel_nettonnage,:vessel_deadweight,:vessel_mmsi_number,:vessel_year_built,:vessel_latitude,:vessel_longitude,:vessel_latitude_degrees,:vessel_longitude_degrees,:vessel_speed,:vessel_course,:vessel_heading,:vessel_time_stamp
    )
"""
        )

        values_vcp = {
            "vessel_nm": data["vessel_particulars"][0]["vessel_nm"],
            "vessel_imo_no": data["vessel_particulars"][0]["vessel_imo_no"],
            "vessel_call_sign": data["vessel_particulars"][0]["vessel_call_sign"],
            "vessel_flag": data["vessel_particulars"][0]["vessel_flag"],
            "vessel_length": data["vessel_length"],
            "vessel_depth": data["vessel_depth"],
            "vessel_type": data["vessel_type"],
            "vessel_grosstonnage": data["vessel_grosstonnage"],
            "vessel_nettonnage": data["vessel_nettonnage"],
            "vessel_deadweight": data["vessel_deadweight"],
            "vessel_mmsi_number": data["vessel_mmsi_number"],
            "vessel_year_built": data["vessel_year_built"],
            "vessel_latitude": data["vessel_latitude"],
            "vessel_longitude": data["vessel_longitude"],
            "vessel_latitude_degrees": data["vessel_latitude_degrees"],
            "vessel_longitude_degrees": data["vessel_longitude_degrees"],
            "vessel_speed": data["vessel_speed"],
            "vessel_course": data["vessel_course"],
            "vessel_heading": data["vessel_heading"],
            "vessel_time_stamp": data["vessel_time_stamp"],
        }

        result = conn.execute(query_vcp, values_vcp)
        conn.commit()
    print("New vessel_current_position execute success")
    return 1


def new_pilotage_service(data, email, gsheet_cred_path):
    engine_pilot = create_engine(
        gsheet_cred_path, connect_args={"ssl": {"ssl_ca": "/etc/ssl/cert.pem"}}
    )
    with engine_pilot.connect() as conn:
        query_pilot = text(
            "INSERT INTO pilotage_service_UCE (     pilotage_cst_dt_time,pilotage_arrival_dt_time,pilotage_onboard_dt_time,pilotage_start_dt_time,pilotage_end_dt_time,pilotage_nm,pilotage_imo,pilotage_loc_to_code,pilotage_loc_from_code) VALUES (:pilotage_cst_dt_time, :pilotage_arrival_dt_time, :pilotage_onboard_dt_time, :pilotage_start_dt_time, :pilotage_end_dt_time, :pilotage_nm, :pilotage_imo, :pilotage_loc_to_code, :pilotage_loc_from_code)"
        )

        values_pilot = {
            "pilotage_cst_dt_time": data["pilotage_cst_dt_time"],
            "pilotage_arrival_dt_time": data["pilotage_arrival_dt_time"],
            "pilotage_onboard_dt_time": data["pilotage_onboard_dt_time"],
            "pilotage_start_dt_time": data["pilotage_start_dt_time"],
            "pilotage_end_dt_time": data["pilotage_end_dt_time"],
            "pilotage_nm": data["pilotage_nm"],
            "pilotage_imo": data["pilotage_imo"],
            "pilotage_loc_to_code": data["pilotage_loc_to_code"],
            "pilotage_loc_from_code": data["pilotage_loc_from_code"],
        }

        result = conn.execute(query_pilot, values_pilot)
        conn.commit()
    print("New pilotage_service execute success")
    return 1


def new_vessel_due_to_arrive(data, email, gsheet_cred_path):
    engine_VDA = create_engine(
        gsheet_cred_path, connect_args={"ssl": {"ssl_ca": "/etc/ssl/cert.pem"}}
    )

    # Clean up entire VDA data array - can be 300+ into proper columns before storing in SQL DB
    # Insert each JSON object into the table
    values = []
    # insert_query = """
    #     INSERT INTO vessel_due_to_arrive_UCE (vessel_name, call_sign, imo_number, flag, due_to_arrive_dt, location_from, location_to)
    #     VALUES (%s, %s, %s, %s, %s, %s, %s)
    #     """
    #    INSERT INTO vessel_due_to_arrive_UCE (vessel_name, call_sign, imo_number, flag, due_to_arrive_dt, location_from, location_to) VALUES (:vessel_name, :call_sign, :imo_number, :flag, :due_to_arrive_dt, :location_from, :location_to)
    query_VDA = text(
        "INSERT INTO vessel_due_to_arrive_UCE (vessel_name, call_sign, imo_number, flag, due_to_arrive_dt, location_from, location_to) VALUES (:vessel_name, :call_sign, :imo_number, :flag, :due_to_arrive_dt, :location_from, :location_to)"
    )

    for item in data:
        vessel_particulars = item["vda_vessel_particulars"]
        vessel_name = vessel_particulars[0]["vessel_nm"]
        call_sign = vessel_particulars[0]["vessel_call_sign"]
        imo_number = vessel_particulars[0]["vessel_imo_no"]
        flag = vessel_particulars[0]["vessel_flag"]
        due_to_arrive_dt = item["vda_vessel_due_to_arrive_dt"]
        due_to_arrive_dt = datetime.fromisoformat(
            due_to_arrive_dt.replace("Z", "+00:00")
        ).strftime("%Y-%m-%d %H:%M:%S")
        location_from = item["vda_vessel_location_from"]
        location_to = item["vda_vessel_location_to"]

        # values = (vessel_name, call_sign, imo_number, flag, due_to_arrive_dt, location_from, location_to)
        # values.append((vessel_name, call_sign, imo_number, flag, due_to_arrive_dt, location_from, location_to))
        values.append(
            {
                "vessel_name": vessel_name,
                "call_sign": call_sign,
                "imo_number": imo_number,
                "flag": flag,
                "due_to_arrive_dt": due_to_arrive_dt,
                "location_from": location_from,
                "location_to": location_to,
            }
        )

    with engine_VDA.connect() as conn:
        result = conn.execute(query_VDA, values)
        conn.commit()
        # result = conn.executemany(insert_query, values)
        # result = conn.execute(query_pilot, values_pilot)

    print("New new_vessel_due_to_arrive execute success")
    return 1


#######################################################        END RECEIVED DATA FROM API     #######################################################
