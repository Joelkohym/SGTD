from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    jsonify,
    flash,
    g,
)
from flask_sqlalchemy import SQLAlchemy

from flask_mysqldb import MySQL
from sqlalchemy import create_engine, text
import requests
import json


from datetime import datetime, timedelta
import pandas as pd
import time
import os

from db_LBO_data_pull import (
    delete_all_rows_vessel_location,
    GET_MPA_VCP_PULL_SGTD,
    get_MPA_vessel_location_data_SQL_data,
    display_lbo_map,
    get_data_from_VF_vessels,
    merged_MPA_VF_ETA_df,
    merge_MPA_vessel_data_df_ETA_df,
    merge_VF_df_ETA_df,
    GET_LBO_GNSS_Data,
)

from db_LBO_GET_GNSS_TOKEN import GET_LBO_GNSS_Token

from db_table_pull import (
    delete_all_rows_table_view,
    PULL_pilotage_service,
    PULL_vessel_due_to_arrive,
    validate_imo,
)
from db_table_view_request import (
    get_data_from_vessel_due_to_arrive_and_depart,
    merge_arrivedepart_VF_df,
    get_data_from_VF_single_vessel_positions,
)
from database import (
    new_registration,
    validate_login,
    receive_details,
    new_vessel_current_position,
    new_pilotage_service,
    new_vessel_due_to_arrive,
)

from flask_swagger_ui import get_swaggerui_blueprint

application = app = Flask(__name__)

# app.config["SQLALCHEMY_DATABASE_URI"] = "mysql://admin:adminAWS@sgtd-digital-enablement-db.cbqefwsjozfo.ap-southeast-1.rds.amazonaws.com/sgtd"
# app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

app.config["MYSQL_HOST"] = os.environ["MYSQL_HOST"]
app.config["MYSQL_USER"] = os.environ["MYSQL_USER"]
app.config["MYSQL_PASSWORD"] = os.environ["MYSQL_PASSWORD"]
app.config["MYSQL_DB"] = os.environ["MYSQL_DB"]


app.secret_key = os.urandom(24)

mysql = MySQL(app)
db_connection_string = os.environ["DB_CONNECTION_STRING"]
# db_connection_string = 'mysql+pymysql://2j104pgpfhay9dokc46k:pscale_pw_fiA5JrG88BcLgKuQmmK9WZHjaOlzf2BkRisjOD6FDn6@aws.connect.psdb.cloud/sgtd?charset=utf8mb4'
engine = create_engine(
    db_connection_string, connect_args={"ssl": {"ssl_ca": "/etc/ssl/cert.pem"}}
)


@app.route("/")
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        msg = ""
        try:
            email = request.form["email"]
            password = request.form["password"]
            login_data = validate_login(email, password)
            print(f"Login data = {login_data}")
            # print(f"Validate_login value returned = {validate_login(email, password)}")
            if len(login_data) == 5:
                id = login_data[0]
                API_KEY = login_data[1]
                pID = login_data[2]
                pitstop = login_data[3]
                gSheet = login_data[4]

                session["loggedin"] = True
                session["id"] = id
                session["email"] = email
                session["participant_id"] = pID
                session["pitstop_url"] = pitstop
                session["api_key"] = API_KEY
                session["gc"] = gSheet
                session["IMO_NOTFOUND"] = []
                session["IMO_FOUND"] = []
                session["LBO_ACCESS_TOKEN"] = []
                session["LBO_REFRESH_TOKEN"] = []
                session["IMO_List"] = []
                session["terms_condition"] = ""
                # {'id': '9445763b-d706-4a40-946d-51c734e93c83', 'name': 'SGTraDex Dummy - Financing Bank', 'data_element': 'sales_invoice_cargotrader_lbs', 'system_id': '9a0c9ff8-06f6-43cf-8c77-c7f3881f96c6'}
                msg = f"Login success for {email}, please enter Vessel IMO number(s)"
                # print(f'session["gc"]  == {session["gc"]}')
                print(f"Login success for {email}, redirect")
                session["terms_condition"] = True
                return (
                    redirect(url_for("home")),
                    303,
                )
                # return render_template('vessel_request.html', msg=msg, email=email)
            else:
                session["terms_condition"] = False
                msg = "Invalid credentials, please try again.."
                print("Invalid credentials, please try again..")
                return render_template("login.html", msg=msg), 401
        except Exception as e:
            msg = f"Log in failed, please contact admin. Error = {e}"
            print(f"Log in failed, please contact admin. Error = {e}")
            return render_template("login.html", msg=msg), 403
        # if request.data['username'] and request.data['password'] in db:
        #   user_data = load_data_from_db()
    if request.method == "GET":
        print("Request method == GET")
        return render_template("login.html")


@app.route("/home", methods=["GET", "POST"])
def home():
    if g.user:
        email = session["email"]
        return render_template(
            "GNSS_request.html", email=email, login_status=session["terms_condition"]
        )
    else:
        msg = "Error while getting to table view, redirecting to login"
        print("Error while getting to table view, redirecting to login")
        return redirect(url_for("login", msg=msg)), 401


@app.route("/table_view", methods=["GET", "POST"])
def table_view():
    if g.user:
        email = session["email"]
        return render_template("table_view.html", email=email)
    else:
        msg = "Error while getting to table view, redirecting to login"
        print("Error while getting to table view, redirecting to login")
        return redirect(url_for("login", msg=msg)), 401


@app.route("/api/table_pull", methods=["GET", "POST"])
def table_pull():
    if g.user:
        if request.method == "POST":
            session["IMO_NOTFOUND"] = []
            session["TABLE_IMO_NOTFOUND"] = []
            # Clear all rows in vessel_movement_UCE and vessel_current_position_UCE table
            print(f'Session gc = {session["gc"]}')
            delete_all_rows_table_view(session["gc"])
            user_vessel_imo = request.form["imo"]

            print(f'session["IMO_List"] = {session["IMO_List"]}')
            try:
                # Split vessel_imo list into invdivual records
                input_list = [int(x) for x in user_vessel_imo.split(",")]
                print(f"Pilotage service input_list from html = {input_list}")
                print("Start PULL_pilotage_service thread...")
                print(datetime.now())
                # ========================              START PULL pilotage_service by vessel imo                   ===========================
                # url_pilotage_service = (
                #     f"{session['pitstop_url']}/api/v1/data/pull/pilotage_service"
                # )
                # PULL_pilotage_service(
                #     url_pilotage_service,
                #     input_list,
                #     session["participant_id"],
                #     session["api_key"],
                # )
                print("End PULL_pilotage_service thread...")
                print(datetime.now())
                # ========================          END PULL pilotage_service                         ===========================

                # ========================          START PULL vessel_due_to_arrive by date            ===========================
                url_vessel_due_to_arrive = (
                    f"{session['pitstop_url']}/api/v1/data/pull/vessel_due_to_arrive"
                )
                print("Start PULL_vessel_due_to_arrive thread...")
                print(datetime.now())
                # threading.Thread(
                #     target=PULL_vessel_due_to_arrive,
                #     args=(
                #         url_vessel_due_to_arrive,
                #         session["participant_id"],
                #         session["api_key"],
                #     ),
                # ).start()
                print("End PULL_vessel_due_to_arrive thread...")
                print(datetime.now())

                # ========================    END PULL vessel_due_to_arrive         ===========================

                return redirect(url_for("table_view_request", imo=user_vessel_imo)), 303
            except Exception as e:
                return (
                    render_template(
                        "table_view.html",
                        msg=f"Invalid IMO. Please ensure at IMO is valid. Error = {e}",
                    ),
                    400,
                )
        else:
            print("TABLE_PULL Method <> POST")
            return redirect(url_for("login")), 301
    else:
        print("TABLE_PULL g.user is not valid")
        return redirect(url_for("login")), 401


@app.route("/table_view_request/<imo>", methods=["GET", "POST"])
def table_view_request(imo):
    if g.user:
        try:
            imo_list = imo.split(",")
            print(f"app.py: table_view_request(imo):IMO ==== {imo}")
            print(f"app.py: table_view_request(imo):IMO list ==== {imo_list}")

            # ======================== START GET MPA Vessel Due to Arrive and Depart by next 99 hours  =============
            MPA_arrive_depart_df = get_data_from_vessel_due_to_arrive_and_depart()

            # Filter MPA_arrive_depart_df
            filtered_arrive_depart_MPA_df = MPA_arrive_depart_df[
                MPA_arrive_depart_df["vesselParticulars.imoNumber"].isin(imo_list)
            ]
            print(
                f"app.py: table_view_request(imo): filtered_arrive_depart_MPA = {filtered_arrive_depart_MPA_df}"
            )

            # =================== Validate arrive_depart_MPA_df NOT empty ===============
            if filtered_arrive_depart_MPA_df.empty:
                msg = "No arrival data from MPA."
                return render_template("table_view.html", msg=msg), 404

            # ======================== START VESSEL FINDER API =============
            VF_Single_Vessel_Positions_df = get_data_from_VF_single_vessel_positions(
                imo
            )

            # =================== Validate NOT df.empty ===============
            if (
                len(filtered_arrive_depart_MPA_df) == 0
                and len(VF_Single_Vessel_Positions_df) == 0
            ):
                msg = "IMO cannot be found, please try another IMO.."
                return render_template("table_view.html", msg=msg), 404

            # =========== Merge filtered_arrive_depart_MPA_df + VesselFinder =========
            render_html = merge_arrivedepart_VF_df(
                filtered_arrive_depart_MPA_df, VF_Single_Vessel_Positions_df
            )
            if render_html == 1:
                return render_template("table_view.html")
            else:
                print(f"app.py: table_view_request(imo): render_html = {render_html}")
                return render_template(render_html)
        except Exception as e:
            return (
                render_template(
                    "table_view.html",
                    msg=f"Something went wrong with the data, please ensure IMO Number is valid. Error = {e}",
                ),
                406,
            )
    else:
        return redirect(url_for("login")), 401


# Make function for logout session
@app.route("/logout")
def logout():
    session.pop("loggedin", None)
    session.pop("id", None)
    session.pop("email", None)
    session.pop("participant_id", None)
    session.pop("pitstop_url", None)
    session.pop("api_key", None)
    session.pop("gc", None)
    session.pop("IMO_FOUND", None)
    session.pop("IMO_NOT_FOUND", None)
    session.pop("LBO_ACCESS_TOKEN", None)
    session.pop("LBO_REFRESH_TOKEN", None)
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    msg = ""
    print(f"request.form = {request.form}")
    if (
        request.method == "POST"
        and "email" in request.form
        and "password" in request.form
    ):
        data = request.form
        print(data)
        r_status = new_registration(data)
        if r_status == 1:
            msg = "You have successfully registered!, please send Admin gsheet credentials file."
            return render_template("login.html", msg=msg)
        else:
            msg = "Your email exists in database! Please reach out to Admin if you need assistance."
            return render_template("login.html", msg=msg), 409
    elif request.method == "POST":
        msg = "Please fill out the form !"
        return render_template("login.html", msg=msg), 406
    if request.method == "GET":
        return render_template("register.html")
    # return render_template("register.html")


# ====================================#################### LBO GNSS MAP ##############################========================================
@app.route("/api/gnss_token", methods=["POST"])
def LBO_GET_GNSS_TOKEN():
    tokens = GET_LBO_GNSS_Token()
    print(tokens)
    if tokens == "0":
        print("Too frequent TOKEN request, please try again later...")
        return render_template(
            "GNSS_request.html",
            msg="Too frequent TOKEN request, please try again later...",
        )

    session["LBO_ACCESS_TOKEN"] = tokens["access_token"]
    session["LBO_REFRESH_TOKEN"] = tokens["refresh_token"]
    return f'Successfuly retrieved token: session["LBO_ACCESS_TOKEN"] = {session["LBO_ACCESS_TOKEN"]}, session["LBO_REFRESH_TOKEN"] = {session["LBO_REFRESH_TOKEN"]}'


@app.route("/lbo_request/<msg>", methods=["GET", "POST"])
def lbo_request(msg):
    if g.user:
        return render_template("GNSS_request.html", msg=msg)
    else:
        return redirect(url_for("login")), 304


@app.route("/api/lbo", methods=["POST"])
def LBO_data_pull():
    if g.user:
        if request.method == "POST":
            session["IMO_NOTFOUND"] = []

            user_vessel_imo = request.form["imo"]
            user_lbo_imei = request.form["lbo_imei"]
            print(f"len(user_vessel_imo) = {len(user_vessel_imo)}")
            if len(user_vessel_imo) == 0 and len(user_lbo_imei) == 0:
                return render_template(
                    "GNSS_request.html",
                    msg="Please enter IMO or IMEI number.",
                )
            if len(user_vessel_imo) > 1:  # get df2
                # Clear all rows in vessel_movement_UCE and vessel_current_position_UCE table
                delete_all_rows_vessel_location(session["gc"])
                try:
                    input_list = [int(x) for x in user_vessel_imo.split(",")]
                    print(
                        f"app.py: LBO_data_pull(): user_vessel_imo from html = {user_vessel_imo}"
                    )
                    print(
                        f"app.py: LBO_data_pull(): split user_vessel_imo input_list from html = {input_list}"
                    )
                    # Loop through input IMO list
                    tic = time.perf_counter()
                    # ============= GET 2 API's from MPA: VCP + VDA ===================
                    # ============= PULL 2 API's from SGTD: VCP + VDA =================
                    GET_MPA_VCP_PULL_SGTD(
                        input_list,
                        session["pitstop_url"],
                        session["gc"],
                        session["participant_id"],
                        session["api_key"],
                        session["IMO_NOTFOUND"],
                    )
                    toc = time.perf_counter()
                    print(
                        f"app.py: LBO_data_pull(): PULL duration for vessel map query {len(input_list)} in {toc - tic:0.4f} seconds"
                    )
                    print(
                        f"app.py: LBO_data_pull(): VESSEL MAP PRINTING IMO_NOTFOUND = {session['IMO_NOTFOUND']}"
                    )

                    # Select MPA_vessel_data
                    MPA_vessel_data_df_SQL_data = get_MPA_vessel_location_data_SQL_data(
                        session["gc"]
                    )
                    MPA_vessel_data_df = pd.DataFrame(MPA_vessel_data_df_SQL_data[0])
                    print(
                        f"app.py: LBO_data_pull(): MPA_vessel_location_data_SQL_data_df VESSEL MAP = {MPA_vessel_data_df.to_string(index=False, header=True)}"
                    )

                    # Get Vessel Finder DF and merge
                    # db_vessel_map.py
                    VF_df = get_data_from_VF_vessels(user_vessel_imo)
                    if type(VF_df) == "list":
                        return (
                            render_template(
                                "GNSS_request.html",
                                msg=f"VesselFinder Account Expired. Please contact admin.",
                            ),
                            406,
                        )
                    print(
                        f"app.py: LBO_data_pull(): VF_df VESSEL MAP = {VF_df.to_string(index=False, header=True)}"
                    )
                    # db_vessel_map.py
                    ETA_df = get_data_from_vessel_due_to_arrive_and_depart()
                    print(f"app.py: LBO_data_pull(): ETA_df VESSEL MAP = {len(ETA_df)}")
                    if MPA_vessel_data_df.empty and VF_df.empty:
                        return (
                            render_template(
                                "GNSS_request.html",
                                msg=f"No data found. Please try again.",
                            ),
                            406,
                        )
                    elif MPA_vessel_data_df.empty:
                        print(
                            f"app.py: LBO_data_pull(): MPA_vessel_location_data_SQL_df==empty, only display VF_df with ETA_df...."
                        )
                        if ETA_df.empty:
                            # ====== VF_df == final_df, ETA_df and MPA_vessel_location_df == empty ==================
                            final_df = VF_df
                            print(
                                f"app.py: LBO_data_pull(): ETA_df == empty, only VF_df"
                            )
                        else:
                            # ====== Merge VF_df with ETA_df ==================
                            final_df = merge_VF_df_ETA_df(VF_df, ETA_df)
                            # ====== Merge VF_df with ETA_df ==================
                            # VF_df["imoNumber"] = VF_df["imoNumber"].astype(int)
                            # ETA_df["vesselParticulars.imoNumber"] = ETA_df[
                            #     "vesselParticulars.imoNumber"
                            # ].astype(int)
                            # VF_ETA_df = pd.merge(
                            #     VF_df,
                            #     ETA_df,
                            #     left_on=VF_df["imoNumber"],
                            #     right_on=ETA_df["vesselParticulars.imoNumber"],
                            #     how="left",
                            # )

                            # VF_ETA_df.rename(
                            #     columns={
                            #         "duetoArriveTime": "ETA - MPA",
                            #         "dueToDepart": "ETD - MPA",
                            #         "locationTo": "DESTINATION - MPA",
                            #         "DESTINATION": "DESTINATION - VesselFinder",
                            #     },
                            #     inplace=True,
                            # )
                            # desired_column_order = [
                            #     "imoNumber",
                            #     "NAME",
                            #     "DESTINATION - VesselFinder",
                            #     "DESTINATION - MPA",
                            #     "ETA - VesselFinder",
                            #     "ETA - MPA",
                            #     "ETD - MPA",
                            #     "callsign",
                            #     "speed",
                            #     "timeStamp",
                            #     "latitudeDegrees",
                            #     "longitudeDegrees",
                            #     "heading",
                            # ]
                            # VF_ETA_df = VF_ETA_df[desired_column_order]
                            # final_df = VF_ETA_df

                    elif VF_df.empty:
                        # =========== Merge MPA_vessel_location_df with ETA_df =================
                        # db_vessel_map.py
                        final_df = merge_MPA_vessel_data_df_ETA_df(
                            MPA_vessel_data_df, ETA_df
                        )

                    else:
                        print(
                            f"app.py: LBO_data_pull(): All DF are not empty, carrying out merged_MPA_VF_df"
                        )
                        # db_vessel_map.py
                        merged_df = merged_MPA_VF_ETA_df(
                            MPA_vessel_data_df, VF_df, ETA_df
                        )
                        print(
                            f"app.py: LBO_data_pull(): merged_df LBO MAP == {merged_df}"
                        )
                        final_df = merged_df
                except Exception as e:
                    return (
                        render_template(
                            "GNSS_request.html",
                            msg=f"Invalid Vessel IMO. Please ensure Vessel IMO is valid. Error = {e}",
                        ),
                        406,
                    )

            # Clear all rows in vessel_movement_UCE and vessel_current_position_UCE table
            # delete_all_rows_vessel_location(session["gc"])

            print(
                f"app.py: LBO_data_pull(): len(user_lbo_imei) = {len(user_lbo_imei )}"
            )
            print(
                f"app.py: LBO_data_pull(): len(user_vessel_imo) = {len(user_vessel_imo)}"
            )

            # Check for GNSS Token
            if len(user_lbo_imei) > 1:
                print(f'session["LBO_ACCESS_TOKEN"]  = {session["LBO_ACCESS_TOKEN"]}')
                if len(session["LBO_ACCESS_TOKEN"]) == 0:
                    return render_template(
                        "GNSS_request.html",
                        msg="Please retrieve a TOKEN first... Token is currently empty.",
                    )

            # display df2 for IMO and GNSS for IMEI
            if len(user_lbo_imei) > 1 or len(user_vessel_imo) > 1:
                print(
                    f"app.py: LBO_data_pull(): len(user_lbo_imei) > 1 and len(user_vessel_imo) > 1:"
                )
                # ============= GET LBO GNSS DATA API's from GETT TECHNOLOGIES ===================

                try:
                    GNSS_df = pd.DataFrame()
                    if len(user_lbo_imei) > 1:
                        print(f"len(user_lbo_imei) > 1 == {len(user_lbo_imei)}")
                        tic = time.perf_counter()
                        GNSS_Data = GET_LBO_GNSS_Data(
                            user_lbo_imei,
                            session["LBO_ACCESS_TOKEN"],
                            session["LBO_REFRESH_TOKEN"],
                        )
                        print(
                            f"app.py: LBO_data_pull(): user_lbo_imei from html = {GNSS_Data}"
                        )
                        GNSS_df = pd.DataFrame(GNSS_Data)
                    # Loop through input IMO list
                    if len(user_vessel_imo) < 2:
                        print(
                            f"app.py: LBO_data_pull(): len(user_vessel_imo) < 2 == {len(user_vessel_imo)}"
                        )
                        final_df = pd.DataFrame()
                    print(f"final_df == {final_df}")
                    print(f"GNSS_df == {GNSS_df}")
                    if final_df.empty and GNSS_df.empty:
                        return (
                            render_template(
                                "GNSS_request.html",
                                msg="No data found. Please try again.",
                            ),
                            406,
                        )

                    display_data = display_lbo_map(GNSS_df, final_df)[1]
                    print(f"app.py: LBO_data_pull(): display_data = {display_data}")
                    # ============= GET 2 API's from MPA: VCP + VDA ===================
                    # ============= PULL 2 API's from SGTD: VCP + VDA =================
                    toc = time.perf_counter()
                    print(
                        f"app.py: LBO_data_pull(): PULL duration for vessel map query {len(user_lbo_imei)} in {toc - tic:0.4f} seconds"
                    )
                    if display_data[0] == 1:
                        print(f"app.py: LBO_data_pull(): LBO GNSS _map return start 1")
                        return render_template(
                            display_data[1],
                        )

                    else:
                        print(f"app.py: LBO_data_pull(): LBO GNSS_map return start 2")
                        print(display_data)
                        return render_template(display_data), 200

                except Exception as e:
                    return (
                        render_template(
                            "GNSS_request.html",
                            msg=f"Invalid IMEI. Please ensure IMEI is valid. Error = {e}",
                        ),
                        406,
                    )
        return render_template("GNSS_request.html"), 403
    return redirect(url_for("login")), 304


####################################  START UPLOAD UCC #############################################
@app.route("/UCC_upload")
def UCC_upload():
    if g.user:
        email = session["email"]
        base_url = session["pitstop_url"]

        config_api_url = (
            f"{base_url}/api/v1/config"  # Replace with the actual API endpoint
        )
        api_key = session["api_key"]  # Replace with your API key
        system_data = get_system_data(config_api_url, api_key)
        participant_data = get_participants(system_data)

        return render_template(
            "UCC_upload.html", email=email, participant_data=participant_data
        )
    else:
        return redirect(url_for("login")), 401


@app.route("/api/triangular_upload/<data>", methods=["POST"])
def triangular_upload(data):
    if g.user:
        if request.method == "POST":
            session["data"] = data
            participant_id_lbs = session["participant_id"]
            participant_sourceSystem_id_lbs = "70a3f53d-f21e-4cae-aa98-9f3eef4abf17"
            base_url = session["pitstop_url"]
            api_key = session["api_key"]
            package_id = create_folder_and_package(
                data,
                participant_id_lbs,
                participant_sourceSystem_id_lbs,
                base_url,
                api_key,
            )
            # Get the list of files from webpage
            files = request.files.getlist("files[]")  # Use "files[]" as the key

            # Iterate for each file in the files list and save them
            for file in files:
                if file and file.filename.endswith(".csv"):  # Check if it's a CSV file
                    print(file.filename)
                    process_file(file, data, package_id, base_url, api_key)
                    # file.save(file.filename)
                else:
                    return (
                        "<h1>Invalid file format. Please upload only CSV files.</h1>",
                        415,
                    )
            return "<h1>Files Uploaded Successfully.!</h1>"
    else:
        return redirect(url_for("login")), 304


####################################  END UPLOAD UCC  ###############################################


##########################################################RECEIVE in MySQL DB#############################################################################################


# https://sgtd-api.onrender.com/api/vessel_due_to_arrive_db/receive/test@sgtradex.com
@app.route("/api/vessel_due_to_arrive_db/receive/<email_url>", methods=["POST"])
def RECEIVE_Vessel_due_to_arrive(email_url):
    email = email_url
    receive_details_data = receive_details(email)
    # print(f"Vessel_current_position_receive:   Receive_details from database.py {receive_details(email)}")
    API_KEY = receive_details_data[1]
    participant_id = receive_details_data[2]
    pitstop_url = receive_details_data[3]
    gsheet_cred_path = receive_details_data[4]

    data = request.data  # Get the raw data from the request body

    print(f"Vessel_due_to_arrive = {data}")

    data_str = data.decode("utf-8")  # Decode data as a UTF-8 string
    # Convert the JSON string to a Python dictionary
    data_dict = json.loads(data_str)
    row_data_vessel_due_to_arrive = data_dict["payload"]
    print(f"row_data_vessel_due_to_arrive = {row_data_vessel_due_to_arrive}")
    # ====================== Store VDA into DB =============================
    result = new_vessel_due_to_arrive(
        row_data_vessel_due_to_arrive, email, gsheet_cred_path
    )
    if result == 1:
        # Append the data as a new row
        return f"vessel_due_to_arrive Data saved to Google Sheets.{row_data_vessel_due_to_arrive}"
    else:
        return f"Email doesn't exists, unable to add data"


@app.route("/api/pilotage_service_db/receive/<email_url>", methods=["POST"])
def RECEIVE_Pilotage_service(email_url):
    email = email_url
    receive_details_data = receive_details(email)
    # print(f"Vessel_current_position_receive:   Receive_details from database.py {receive_details(email)}")
    API_KEY = receive_details_data[1]
    participant_id = receive_details_data[2]
    pitstop_url = receive_details_data[3]
    gsheet_cred_path = receive_details_data[4]

    data = request.data  # Get the raw data from the request body

    print(f"Pilotage service = {data}")

    data_str = data.decode("utf-8")  # Decode data as a UTF-8 string
    # Convert the JSON string to a Python dictionary
    data_dict = json.loads(data_str)
    row_data_pilotage_service = data_dict["payload"][-1]
    print(f"row_data_Pilotage service = {row_data_pilotage_service}")
    # ====================== Store VDA into DB =============================
    result = new_pilotage_service(data, email, gsheet_cred_path)
    if result == 1:
        # Append the data as a new row
        return (
            f"pilotage_service Data saved to Google Sheets.{row_data_pilotage_service}"
        )
    else:
        return f"Email doesn't exists, unable to add data"


# https://sgtd-api.onrender.com/api/vessel_current_position_db/receive/test@sgtradex.com
@app.route("/api/vessel_current_position_db/receive/<email_url>", methods=["POST"])
def RECEIVE_Vessel_current_position(email_url):
    email = email_url
    receive_details_data = receive_details(email)
    # print(f"Vessel_current_position_receive:   Receive_details from database.py {receive_details(email)}")
    API_KEY = receive_details_data[1]
    participant_id = receive_details_data[2]
    pitstop_url = receive_details_data[3]
    gsheet_cred_path = receive_details_data[4]

    data = request.data  # Get the raw data from the request body

    print(f"Vessel_current_position = {data}")

    data_str = data.decode("utf-8")  # Decode data as a UTF-8 string
    # Convert the JSON string to a Python dictionary
    data_dict = json.loads(data_str)
    row_data_vessel_current_position = data_dict["payload"][-1]
    print(f"row_data_vessel_current_position = {row_data_vessel_current_position}")
    result = new_vessel_current_position(
        row_data_vessel_current_position, email, gsheet_cred_path
    )
    if result == 1:
        # Append the data as a new row
        return f"Vessel Current Location Data saved to Google Sheets.{row_data_vessel_current_position}"
    else:
        return f"Email doesn't exists, unable to add data"


# https://sgtd-api.onrender.com/api/vessel_movement_db/receive/test@sgtradex.com


@app.route("/api/others/receive/<email_url>", methods=["POST"])
def RECEIVE_Others(email_url):
    email = email_url
    response_data = {"message": f"Received others from {email_url}"}
    return jsonify(response_data)


##########################################################MySQL DB#############################################################################################


@app.before_request
def before_request():
    g.user = None
    if "email" in session:
        g.user = session["email"]


# ====================================####################MAP DB##############################========================================


@app.after_request
def after_request(response):
    response.headers[
        "Cache-Control"
    ] = "no-cache, no-store, must-revalidate, public, max-age=0"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Configure Swagger UI
SWAGGER_URL = "/swagger"
API_URL = "http://127.0.0.1:5000/swagger.json"
swaggerui_blueprint = get_swaggerui_blueprint(
    SWAGGER_URL, API_URL, config={"app_name": "SGTD Vessel Query API Swagger"}
)
app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)


@app.route("/swagger.json")
def swagger():
    with open("swagger.json", "r") as f:
        return jsonify(json.load(f))


if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True)
